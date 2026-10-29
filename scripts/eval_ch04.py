"""ch04 四策略分桶评估:检索(Recall@5/MRR)+ 证据覆盖度 + 生成(答案覆盖度/忠实度/拒答率)。
产物落 data/ch04/reports/rag_eval.{txt,json};txt 是运行日志,json 给 RAG 评估页读。
需 Milvus + 已建库 + 聊天上游可用。"""
import asyncio
import json
import pathlib
import sys
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.llm import get_chat_model
from app.core.prompts import FAITHFULNESS_PROMPT, RAG_ANSWER_PROMPT
from app.core import retrieval

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVAL_FILE = ROOT / "tests/data/eval_ch04.jsonl"
OUT_DIR = ROOT / "data/ch04/reports"
OUT_TXT = OUT_DIR / "rag_eval.txt"
OUT_JSON = OUT_DIR / "rag_eval.json"

STRATEGIES = ["vector", "bm25", "hybrid", "hybrid_rerank"]
GRADED_BUCKETS = ["A_policy", "B_model", "C_colloquial", "E_multi"]
RECALL_K = 5
CALL_TIMEOUT = 45.0
GEN_CONCURRENCY = 3

_LINES: list[str] = []
_errs: list[str] = []


def _log(msg: str) -> None:
    print(msg)
    _LINES.append(msg)


def _norm(s: str) -> str:
    return "".join((s or "").split())


class _PointJudge(BaseModel):
    covered: list[str] = Field(default_factory=list, description="答案实际覆盖到的标准要点")


class _FaithJudge(BaseModel):
    faithful: bool = Field(description="回答关键事实是否都被证据支撑")
    reason: str = Field(default="", description="判断依据")


def _load() -> list[dict]:
    samples = [json.loads(ln) for ln in EVAL_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return samples


def _section_matched(sample: dict, hit: dict) -> bool:
    path = hit.get("section_path", "")
    sections = sample.get("expect_section") or []
    return any(s and s in path for s in sections)


def _recall_mrr(sample: dict, hits: list[dict]) -> tuple[float, float]:
    """跨文档题(E_multi)按 expect_sections_all 分组给部分分;其余按 expect_section 命中。"""
    groups = sample.get("expect_sections_all")
    if groups:
        matched_groups = 0
        mrr_sum = 0.0
        for group in groups:
            for rank, h in enumerate(hits[:RECALL_K], start=1):
                if any(alt in h.get("section_path", "") for alt in group):
                    matched_groups += 1
                    mrr_sum += 1.0 / rank
                    break
        recall = matched_groups / len(groups) if groups else 0.0
        mrr = mrr_sum / len(groups) if groups else 0.0
        return recall, mrr
    if not sample.get("expect_section"):
        return 0.0, 0.0
    for rank, h in enumerate(hits[:RECALL_K], start=1):
        if _section_matched(sample, h):
            return 1.0, 1.0 / rank
    return 0.0, 0.0


def _coverage_mech(points: list[str], hits: list[dict]) -> float | None:
    if not points:
        return None
    ev = _norm("\n".join(h.get("answer", "") for h in hits))
    return sum(1 for p in points if _norm(p) in ev) / len(points)


async def _deterministic(samples: list[dict]):
    retrieval_metrics = {b: {s: {"recall_at_5": 0.0, "mrr": 0.0, "n": 0} for s in STRATEGIES} for b in GRADED_BUCKETS}
    coverage = {s: {b: {"value": 0.0, "n": 0} for b in GRADED_BUCKETS} for s in STRATEGIES}
    hits_cache: dict[str, dict[str, list[dict]]] = {}
    for sample in samples:
        bucket = sample["bucket"]
        if bucket not in GRADED_BUCKETS:
            continue
        for strategy in STRATEGIES:
            try:
                hits = await retrieval.search_knowledge(
                    sample["query"], strategy=strategy, top_k=RECALL_K
                )
            except Exception as e:
                _errs.append(f"{sample['id']}/{strategy}: {type(e).__name__}")
                hits = []
            hits_cache.setdefault(sample["id"], {})[strategy] = hits
            recall, mrr = _recall_mrr(sample, hits)
            retrieval_metrics[bucket][strategy]["recall_at_5"] += recall
            retrieval_metrics[bucket][strategy]["mrr"] += mrr
            retrieval_metrics[bucket][strategy]["n"] += 1
            cov = _coverage_mech(sample.get("expect_points", []), hits)
            if cov is not None:
                coverage[strategy][bucket]["value"] += cov
                coverage[strategy][bucket]["n"] += 1
    for bucket in GRADED_BUCKETS:
        for strategy in STRATEGIES:
            m = retrieval_metrics[bucket][strategy]
            m["recall_at_5"] = round(m["recall_at_5"] / m["n"], 4) if m["n"] else 0.0
            m["mrr"] = round(m["mrr"] / m["n"], 4) if m["n"] else 0.0
            c = coverage[strategy][bucket]
            c["value"] = round(c["value"] / c["n"], 4) if c["n"] else None
    return retrieval_metrics, coverage, hits_cache


async def _try(coro, label):
    try:
        return await asyncio.wait_for(coro, CALL_TIMEOUT)
    except Exception as e:
        _errs.append(f"{label}: {type(e).__name__}")
        return None


async def _gen_one(sample: dict, hits: list[dict]):
    evidence = "\n".join(f"[{i+1}] {h['question']}: {h['answer']}" for i, h in enumerate(hits)) or "(无证据)"
    model = get_chat_model()
    answer = await _try(
        (RAG_ANSWER_PROMPT | model).ainvoke({"query": sample["query"], "evidence": evidence}),
        f"gen/{sample['id']}",
    )
    answer_text = answer.content if answer else ""
    return answer_text, evidence


async def _generation(samples: list[dict], hits_cache: dict[str, dict[str, list[dict]]]):
    model = get_chat_model(temperature=0.0)
    # 四策略答案覆盖度(仅线上策略做忠实度与拒答)
    answer_coverage = {s: {b: {"value": 0.0, "n": 0} for b in GRADED_BUCKETS} for s in STRATEGIES}
    faithfulness = {b: {"faithful": 0, "total": 0, "cases": []} for b in GRADED_BUCKETS}
    refusal = {"total": 0, "refused": 0}
    sem = asyncio.Semaphore(GEN_CONCURRENCY)

    async def run_one(sample, strategy):
        async with sem:
            hits = (hits_cache.get(sample["id"], {}) or {}).get(strategy, [])
            answer, evidence = await _gen_one(sample, hits)
            if answer is None:
                return
            if sample["bucket"] in GRADED_BUCKETS and sample.get("expect_points"):
                judge = await _try(
                    (model.with_structured_output(_PointJudge)).invoke(
                        f"用户问题:{sample['query']}\n\n客服回答:\n{answer}\n\n标准要点:{sample['expect_points']}"
                    ),
                    f"judge/{sample['id']}/{strategy}",
                )
                if judge:
                    covered = {_norm(p) for p in judge.covered}
                    score = sum(1 for p in sample["expect_points"] if _norm(p) in covered) / len(sample["expect_points"])
                    answer_coverage[strategy][sample["bucket"]]["value"] += score
                    answer_coverage[strategy][sample["bucket"]]["n"] += 1
            if strategy == "hybrid_rerank" and sample["bucket"] in GRADED_BUCKETS:
                faith = await _try(
                    (FAITHFULNESS_PROMPT | model.with_structured_output(_FaithJudge)).ainvoke(
                        {"evidence": evidence, "answer": answer}
                    ),
                    f"faith/{sample['id']}",
                )
                if faith:
                    faithfulness[sample["bucket"]]["total"] += 1
                    if faith.faithful:
                        faithfulness[sample["bucket"]]["faithful"] += 1
                    else:
                        faithfulness[sample["bucket"]]["cases"].append(
                            {"id": sample["id"], "query": sample["query"], "answer": answer, "reason": faith.reason}
                        )
            if sample["bucket"] == "D_absent":
                refusal["total"] += 1
                low = ("没有查到" in answer) or ("拒答" in answer) or ("联系人工" in answer)
                if low:
                    refusal["refused"] += 1

    for strategy in STRATEGIES:
        await asyncio.gather(*(run_one(s, strategy) for s in samples), return_exceptions=True)
    for s in STRATEGIES:
        for b in GRADED_BUCKETS:
            c = answer_coverage[s][b]
            c["value"] = round(c["value"] / c["n"], 4) if c["n"] else None
    refusal_rate = round(refusal["refused"] / refusal["total"], 4) if refusal["total"] else None
    return answer_coverage, faithfulness, refusal_rate
def _write_report(retrieval_metrics, coverage, generation, meta):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "meta": meta,
        "retrieval": retrieval_metrics,
        "evidence_coverage": coverage,
        "generation": generation,
    }
    OUT_TXT.write_text("\n".join(_LINES) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


async def main() -> int:
    samples = _load()
    _log(f"评估集 {len(samples)} 题;策略 {STRATEGIES};Recall@{RECALL_K}")
    retrieval_metrics, coverage, hits_cache = await _deterministic(samples)
    _log("\n== 段1 检索(MRR / Recall@%d)==" % RECALL_K)
    for bucket in GRADED_BUCKETS:
        row = {s: f"{retrieval_metrics[bucket][s]['mrr']:.3f}" for s in STRATEGIES}
        _log(f"  {bucket}: " + ", ".join(f"{s}={v}" for s, v in row.items()))
    _log("\n== 段2 证据覆盖度 ==")
    for strategy in STRATEGIES:
        row = {b: coverage[strategy][b]["value"] for b in GRADED_BUCKETS}
        _log(f"  {strategy}: " + ", ".join(f"{b}={v}" for b, v in row.items()))
    generation = None
    try:
        answer_coverage, faithfulness, refusal_rate = await _generation(samples, hits_cache)
        generation = {
            "answer_coverage": answer_coverage,
            "faithfulness": faithfulness,
            "refusal_rate": refusal_rate,
        }
        _log("\n== 段3 生成(答案覆盖度 / 忠实度 / 拒答率)==")
        _log(f"  拒答率={refusal_rate}")
    except Exception as e:
        _log(f"[生成段未完成] {type(e).__name__}: {e}")
    if _errs:
        _log("\n== 失败/跳过 ==")
        for e in _errs:
            _log(f"  {e}")
    meta = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(samples),
        "strategies": STRATEGIES,
        "recall_k": RECALL_K,
    }
    _write_report(retrieval_metrics, coverage, generation, meta)
    _log(f"\n报告已落盘:{OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

