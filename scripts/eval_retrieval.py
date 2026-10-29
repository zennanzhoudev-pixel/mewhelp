"""验收1 eval:对换说法的问题跑向量检索,核对是否召回期望内容。
需已建库并向量化 + 嵌入上游可用(真实嵌入)。"""
import asyncio
import json
import pathlib
import sys

from app.core import retrieval

SAMPLES = pathlib.Path(__file__).parent.parent / "tests/data/retrieval_samples.json"


async def main() -> int:
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    failures = 0
    for s in samples:
        hits = await retrieval.search_knowledge(s["query"])
        top = hits[0] if hits else None
        blob = (top["question"] + " " + top["answer"]) if top else ""
        ok = bool(top) and s["expect_answer_contains"] in blob
        failures += not ok
        print(f"{'✅' if ok else '❌'} {s['query']} -> {(top or {}).get('question', '无结果')}")
    print(f"\n召回正确 {len(samples) - failures}/{len(samples)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

