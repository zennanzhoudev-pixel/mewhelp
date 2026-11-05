"""短信验证码发送适配层。

console 模式只把验证码写进服务端日志,用于本地/测试;webhook 模式 POST 到企业短信
网关,避免把某一家云厂商 SDK 写死。生产必须配置真实网关并关闭 debug 返回。
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def send_login_code(phone: str, code: str) -> None:
    text = f"【MewHelp】登录验证码 {code},{settings.sms_code_ttl_seconds // 60} 分钟内有效。"
    provider = (settings.sms_provider or "console").lower()
    if provider == "console":
        logger.warning("SMS console phone=%s code=%s", phone, code)
        return
    if provider != "webhook" or not settings.sms_webhook_url:
        raise RuntimeError("短信网关未配置")
    headers = {"Content-Type": "application/json"}
    if settings.sms_webhook_token:
        headers["Authorization"] = f"Bearer {settings.sms_webhook_token}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            settings.sms_webhook_url,
            headers=headers,
            json={"phone": phone, "text": text, "purpose": "login"},
        )
        resp.raise_for_status()
