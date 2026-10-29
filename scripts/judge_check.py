"""裁判回归:读台账已处置且有 citations 快照的个案,用快照原样重放,量裁判与人工处置的一致率。"""
import asyncio
import sys

from pydantic import BaseModel, Field

from app.core.llm import get_chat_model
from app.core.prompts import FAITHFULNESS_PROMPT
from app.db import repository


class _FaithJudge(BaseModel):
    faithful: bool = Field(description="是否忠实")
    reason: str = Field(default="")


async def main() -> int:
    rows, _, _ = await repository.list_faith_cases(page=1, size=500)
    usable = [r for r in rows if r.status in ("已解决", "无需解决") and r.citations]
    if not usable:
        print("无已处置且带证据快照的个案,跳过。")
        return 0
    model = get_chat_model(temperature=0.0).with_structured_output(_FaithJudge)
    agree = 0
    for r in usable:
        citations = r.citations or []
        evidence = "\n".join(f"[{c.get('n', i + 1)}] {c.get('question', '')}: {c.get('answer', '')}" for i, c in enumerate(citations))
        expected_faithful = r.status == "无需解决"
        try:
            judge = await (FAITHFULNESS_PROMPT | model).ainvoke({"evidence": evidence, "answer": r.answer})
        except Exception:
            print(f"{r.eval_id}: 调用失败,不计入")
            continue
        ok = judge.faithful == expected_faithful
        agree += ok
        print(f"{'✅' if ok else '❌'} {r.eval_id} 裁判={judge.faithful} 人工处置={r.status}")
    print(f"\n一致率 {agree}/{len(usable)}")
    return 0 if agree == len(usable) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

