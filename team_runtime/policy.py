"""Resource settings shared by Team registration and continuation."""
from typing import Any


class PolicyValidationError(ValueError):
    """A resource setting is invalid."""


DEFAULT_POLICY: dict[str, Any] = {
    "model": "gpt-5.6-luna",
    "reasoning": "max",
    "max_sessions": 2,
    "max_subagents_per_session": 0,
    "max_turn_seconds": 1200,
    "max_run_seconds": 3600,
    "max_repair_attempts": 2,
    "token_budget": 2000000,
    "network_access": False,
}


_POLICY_KEYS = frozenset(DEFAULT_POLICY)


_REASONING_LEVELS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
)


def _type_error(label: str, expected: str) -> TypeError:
    return TypeError(f"{label} must be {expected}")


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _type_error(label, "an object")
    return value


def _require_string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise _type_error(label, "a string")
    if nonempty and not value.strip():
        raise PolicyValidationError(f"{label} must not be empty")
    if "\x00" in value:
        raise PolicyValidationError(f"{label} must not contain NUL")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise _type_error(label, "a boolean")
    return value


def _require_integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _type_error(label, "an integer")
    if minimum is not None and value < minimum:
        raise PolicyValidationError(f"{label} must be >= {minimum}")
    return value


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Merge and validate finite local policy limits.

    Unknown keys fail closed.  ``{}`` selects all explicit finite defaults;
    callers that expose an optional policy should pass ``policy or {}``.
    """

    policy = _require_dict(policy, "policy")
    unknown = sorted(set(policy) - _POLICY_KEYS, key=lambda item: str(item))
    if unknown:
        rendered = ", ".join(repr(item) for item in unknown)
        raise PolicyValidationError(f"policy contains unknown field(s): {rendered}")

    result = dict(DEFAULT_POLICY)
    for key, value in policy.items():
        if key in {"model", "reasoning"}:
            text = _require_string(value, f"policy.{key}")
            if key == "reasoning" and text not in _REASONING_LEVELS:
                raise PolicyValidationError(
                    f"policy.reasoning must be one of: {', '.join(sorted(_REASONING_LEVELS))}"
                )
            result[key] = text
        elif key == "network_access":
            result[key] = _require_bool(value, "policy.network_access")
        elif key == "max_subagents_per_session":
            result[key] = _require_integer(value, f"policy.{key}", minimum=0)
        elif key == "max_repair_attempts":
            result[key] = _require_integer(value, f"policy.{key}", minimum=0)
        else:
            result[key] = _require_integer(value, f"policy.{key}", minimum=1)

    if result["max_run_seconds"] < result["max_turn_seconds"]:
        raise PolicyValidationError("policy.max_run_seconds must be >= max_turn_seconds")
    return result
