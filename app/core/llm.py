from langchain_openai import ChatOpenAI

from app.config import settings


def get_chat_model(
    streaming: bool = False, temperature: float | None = None
) -> ChatOpenAI:
    """直连聊天上游。地址、模型名、密钥全从 .env 来,换上游不动这里。
    temperature 默认 0.3;评估裁判等需确定性时显式传 0。"""
    return ChatOpenAI(
        model=settings.chat_model,
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        streaming=streaming,
        temperature=0.3 if temperature is None else temperature,
    )
