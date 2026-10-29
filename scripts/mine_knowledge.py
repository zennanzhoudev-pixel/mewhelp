"""CLI(可重跑 job):从历史对话挖 QA -> 暂存表 -> 去重 -> 写 knowledge_chunks(pending)。"""
import asyncio

from app.kb import mining


async def main() -> None:
    stats = await mining.mine()
    print(f"挖知识:{stats}")


if __name__ == "__main__":
    asyncio.run(main())

