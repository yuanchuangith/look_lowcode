"""Small diagnosis policy: configured databases default to development."""
from __future__ import annotations

import re
from typing import Any

ENVIRONMENTS = {"development", "test", "staging", "production", "unknown"}
_ALIASES = {
    "开发": "development", "dev": "development", "development": "development",
    "测试": "test", "test": "test", "qa": "test",
    "预发布": "staging", "staging": "staging", "uat": "staging",
    "生产": "production", "正式": "production", "线上": "production",
    "prod": "production", "production": "production",
}
_WORD = r"production|development|staging|预发布|生产|正式|线上|开发|测试|prod|test|dev|uat|qa"
_DECLARATION = re.compile(
    r"(?:当前|目前|现在|本机|这个|我)?\s*(?:配置(?:的)?(?:数据库|连接|库)?|连接|数据库|库)"
    r"\s*(?:连接的?是|指向|属于|就是|是|为)(?:的)?\s*(?P<environment>" + _WORD + r")(?:环境|库)?", re.I,
)
_TARGET = re.compile(
    r"(?P<zh>预发布|生产|正式|线上|开发|测试)(?:的)?(?:环境|库|报错|异常)"
    r"|(?:排查|检查|核查)\s*(?P<short>生产|正式|线上|开发|测试)(?!订单|计划|任务)"
    r"|(?<![a-zA-Z0-9_])(?P<en>production|development|staging|prod|test|dev|uat|qa)(?![a-zA-Z0-9_])", re.I,
)


def database_label(config: Any) -> dict:
    environment = getattr(config, "environment", "development")
    return {"database_environment": environment,
            "database_basis": "default_development" if environment == "development" else "configuration"}


def diagnosis_environment(text: str, context: dict | None, configured: str = "development") -> dict:
    previous = (context or {}).get("environment") or {}
    if not isinstance(previous, dict):
        raise ValueError("context.environment must be an object")
    allowed = {"target_environment", "database_environment", "database_basis", "reference_only"}
    if set(previous) - allowed:
        raise ValueError("context.environment has unsupported fields")
    for field in ("target_environment", "database_environment"):
        if field in previous and previous[field] not in ENVIRONMENTS:
            raise ValueError(f"context.environment.{field} is invalid")
    if "reference_only" in previous and not isinstance(previous["reference_only"], bool):
        raise ValueError("context.environment.reference_only must be a boolean")
    if previous.get("database_basis") not in (None, "default_development", "configuration", "user_declared"):
        raise ValueError("context.environment.database_basis is invalid")

    # Parse request prose only; stack frames and fenced logs are evidence, not declarations.
    request = re.split(r"```|\n\s*at\s|\n.*(?:Exception:|日志[:：])", text, maxsplit=1)[0]
    source = previous.get("database_environment", configured) if previous.get("database_basis") == "user_declared" else configured
    basis = "user_declared" if previous.get("database_basis") == "user_declared" else "default_development" if configured == "development" else "configuration"
    declarations = list(_DECLARATION.finditer(request))
    declared = {_ALIASES[m["environment"].lower()] for m in declarations
                if not re.search(r"不是|并非|不要|别把", request[max(0, m.start() - 4):m.start()])}
    if len(declared) == 1:
        source, basis = declared.pop(), "user_declared"
    ambiguous = len(declared) > 1
    target_text = _DECLARATION.sub("", request)
    reference_parts = re.split(r"(?:先|仅|只)?参考|对照", target_text, maxsplit=1)
    explicit_reference = len(reference_parts) > 1 and not re.search(r"不要|不能|禁止|无需", reference_parts[0][-4:])
    target_text = reference_parts[0]
    correction = re.search(r"(?:不是|并非).{0,12}[,，]\s*(?:而)?是(" + _WORD + r")", target_text, re.I)
    target_text = re.sub(r"(?:不是|并非|非)(?:生产|正式|线上|开发|测试|预发布)(?:环境|库)?", "", target_text)
    targets = {_ALIASES[next(g for g in match.groups() if g).lower()] for match in _TARGET.finditer(target_text)}
    if correction:
        targets = {_ALIASES[correction[1].lower()]}
    ambiguous = ambiguous or len(targets) > 1
    target = next(iter(targets)) if len(targets) == 1 else previous.get("target_environment", source)
    reference = explicit_reference or (not targets and previous.get("reference_only", False))
    record = {"target_environment": target, "database_environment": source, "database_basis": basis, "reference_only": reference}
    blocked = ambiguous or source == "unknown" or (target != source and not reference)
    return {**record, "status": "blocked" if blocked else "reference_only" if reference else "matched",
            "reason": "environment_ambiguous" if ambiguous else "environment_unknown" if source == "unknown" else "environment_mismatch" if blocked else None,
            "record": record, "runtime_verified": False}
