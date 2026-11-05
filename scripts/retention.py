"""ch11 数据保留期清理:按 RETENTION_DAYS_* 删除过期数据(依赖顺序先子后父)。
用法:uv run python scripts/retention.py(可挂 cron/定时任务)。"""
import asyncio

from app.core import retention


async def main() -> None:
    done = await retention.run_retention()
    print("已清理:", done or "无(未配置保留期)")


if __name__ == "__main__":
    asyncio.run(main())

