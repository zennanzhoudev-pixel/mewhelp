from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- ch01 聊天上游(跟着账号走,故意不给默认值,缺了在启动就报 Field required)----
    chat_model: str
    chat_base_url: str
    chat_api_key: str
    token_budget: int = 2000

    # ---- ch02 数据库 ----
    database_url: str = "mysql+asyncmy://root:root@localhost:3306/mewhelp"
    test_database_url: str = "mysql+asyncmy://root:root@localhost:3306/mewhelp_test"

    # ---- ch03 知识库检索 ----
    # 嵌入上游真名带 BAAI/ 前缀;写成 bge-m3 不会在启动报错,而是首次调嵌入时报 Model does not exist。
    embed_base_url: str = "https://api.siliconflow.cn/v1"
    embed_api_key: str
    embed_model: str = "BAAI/bge-m3"
    milvus_uri: str = "http://localhost:19530"  # ch04: Milvus Lite -> Standalone
    retrieval_top_k: int = 3
    retrieval_min_score: float = 0.4

    # ---- ch04 混合检索 + 重排 ----
    rerank_base_url: str = "https://api.siliconflow.cn/v1"
    rerank_api_key: str
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    recall_top_k: int = 50      # dense/BM25 各召回 Top-50
    rerank_top_k: int = 10      # 精排出 Top-10
    rerank_min_score: float = 0.3  # 重排最高分低于此 -> 检索证据低,拒答

    # ---- ch05 图编排 ----
    max_agent_steps: int = 6    # ReAct 环最大步数(封顶,超则兜底)
    # token 花销不在环里卡:那是成本控制,归 ch09 与 Langfuse 一起看
    checkpointer_db_path: str = "data/ch05_checkpoints.sqlite"


settings = Settings()
