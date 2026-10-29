"""ch05 五验收端到端评估。需全服务起(mysql/milvus/app)。"""
import asyncio

import httpx

BASE = "http://localhost:8000"


async def agent(client, msg, cid=None):
    r = await client.post(
        f"{BASE}/api/agent",
        json={"user_id": "eval-ch05", "message": msg, "conversation_id": cid},
    )
    return r.json()


async def main():
    async with httpx.AsyncClient(timeout=120) as c:
        results = []
        b = await agent(c, "订单1001的物流到哪了")
        names = {tc["name"] for tc in b["tool_calls"]}
        results.append(("验收2 物流自调工具", "query_logistics" in names, names))

        b = await agent(c, "我要投诉,你们太差了")
        types = {a["type"] for a in b.get("suggested_actions", [])}
        results.append(("验收3 投诉出两按钮", {"transfer_human", "create_ticket"} <= types, types))

        b = await agent(c, "你好呀")
        results.append(("验收4 闲聊固定话术", not b["tool_calls"] and bool(b["answer"]), b["answer"][:20]))

        b = await agent(c, "我手机尾号1001那个订单发货没?到哪了?")
        results.append(("验收5 ReAct 多步", len(b["tool_calls"]) >= 2, [tc["name"] for tc in b["tool_calls"]]))

        for name, ok, detail in results:
            print(f"{'✅' if ok else '❌'} {name} -> {detail}")
    print("\n验收1(强制检索节点被走到)看 app 日志:问『退货政策是什么』后应见 route=knowledge trace 含 forced_rag=True")


if __name__ == "__main__":
    asyncio.run(main())

