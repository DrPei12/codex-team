"""Remove credential-like values from native event observations."""
import re


_SECRET_KEY = re.compile(r"(?i)^(?:password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie|credential)s?$")
_SECRETS = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}|(?i:Bearer\s+[A-Za-z0-9._~+/-]+=*)|(?i:(?:password|api[_-]?key|access[_-]?token|refresh[_-]?token|secret)\s*[=:]\s*[^\s,;]+)")


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SECRET_KEY.match(key) else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _SECRETS.sub("[REDACTED]", value)
    return value
