"""Skill 机制(简化版):skills/ 目录下每个 .md 是一个指令包,按意图注入 system。
文件名约定:技能名用英文 slug,与 INTENT_SKILL 映射对应。"""
import pathlib

from app.config import settings

# 意图 -> 技能文件名(skills/ 目录下,不含 .md)
INTENT_SKILL: dict[str, str] = {
    "退款退货": "refund-policy",
    "售后": "aftersales",
    "物流": "logistics",
}


def load_skills() -> dict[str, str]:
    if not settings.skills_enabled:
        return {}
    d = pathlib.Path(settings.skills_dir)
    if not d.is_dir():
        return {}
    out: dict[str, str] = {}
    for f in sorted(d.glob("*.md")):
        out[f.stem] = f.read_text(encoding="utf-8")
    return out


def skill_for_intent(intent: str) -> str:
    name = INTENT_SKILL.get(intent)
    if not name:
        return ""
    return load_skills().get(name, "")

