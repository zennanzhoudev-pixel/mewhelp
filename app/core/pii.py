"""PII 脱敏:入库/审计前对手机号、邮箱、带前缀订单号打码。"""
import re

from app.config import settings

_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_ORDER_NO = re.compile(r"\b((?:SO|MH|T)[A-Z0-9]{8,})\b")


def mask_text(text: str) -> str:
    if not text or not settings.pii_mask_enabled:
        return text
    text = _PHONE.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], text)
    text = _EMAIL.sub(lambda m: _mask_email(m.group()), text)
    text = _ORDER_NO.sub(lambda m: m.group()[:2] + "****" + m.group()[-3:], text)
    return text


def mask_value(value):
    """递归脱敏:dict/list 里的字符串值打码,非字符串原样返回。"""
    if not settings.pii_mask_enabled:
        return value
    if isinstance(value, dict):
        return {k: mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_value(v) for v in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return (local[:2] if len(local) > 2 else local) + "***@" + domain

