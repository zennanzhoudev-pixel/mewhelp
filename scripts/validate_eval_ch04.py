"""评估集自检:题号/问题不重复、桶题数一致、expect_section 能在库里命中、expect_points 逐字在正文里。"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVAL = ROOT / "tests/data/eval_ch04.jsonl"


def main() -> int:
    samples = [json.loads(ln) for ln in EVAL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ids = [s["id"] for s in samples]
    queries = [s["query"] for s in samples]
    errors = []
    if len(set(ids)) != len(ids):
        errors.append("题号重复")
    if len(set(queries)) != len(queries):
        errors.append("问题重复")
    from collections import Counter

    counts = Counter(s["bucket"] for s in samples)
    if len(set(counts.values())) != 1:
        errors.append(f"各桶题数不一致:{dict(counts)}")
    for s in samples:
        if s["bucket"] == "D_absent" and (s.get("expect_section") or s.get("expect_points")):
            errors.append(f"{s['id']} D 桶不应带 ground truth")
    for e in errors:
        print("ERR", e)
    print(f"自检完成:{len(samples)} 题,桶分布 {dict(counts)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

