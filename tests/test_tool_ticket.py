from app.tools.business import create_ticket


def test_conversation_id_hidden_from_model_schema():
    # create_ticket.args 是暴露给 LLM 的 model-facing schema(InjectedToolArg 从这里剔除);
    # get_input_schema() 返回完整输入 schema(含 injected),不该用它断言「模型看不到」。
    assert "description" in create_ticket.args and "ticket_type" in create_ticket.args
    assert "conversation_id" not in create_ticket.args


async def test_create_ticket_injects_conversation_id_and_writes(db_session_factory, db_clean):
    from sqlalchemy import select

    from app.db.models import Conversation, Ticket

    async with db_session_factory() as s:
        conv = Conversation(user_id="u1")
        s.add(conv)
        await s.commit()
        cid = conv.id
    r = await create_ticket.ainvoke(
        {"description": "商品损坏要退货", "ticket_type": "售后", "conversation_id": cid}
    )
    assert r["ticket_no"].startswith("T")
    async with db_session_factory() as s:
        t = await s.get(Ticket, r["ticket_no"])
        assert t is not None and t.conversation_id == cid

