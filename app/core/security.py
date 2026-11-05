"""JWT 签发/校验、口令散列与 RBAC 角色(纯 stdlib,HS256)。"""
import base64
import hashlib
import hmac
import json
import os
import time

from app.config import settings

ROLES = ("admin", "agent", "viewer")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2_sha256${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def create_token(user_id: int, tenant_id: str, roles: list[str],
                 expire_minutes: int | None = None) -> str:
    now = int(time.time())
    exp = now + (expire_minutes or settings.jwt_expire_minutes) * 60
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(user_id), "tenant": tenant_id, "roles": roles, "iat": now, "exp": exp}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    sig = _b64url(hmac.new(settings.jwt_secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"


def decode_token(token: str) -> dict | None:
    try:
        h, p, sig = token.split(".")
        expected = _b64url(hmac.new(settings.jwt_secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(p))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

