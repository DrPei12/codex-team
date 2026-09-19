"""Resource settings remain explicit after removing the old proposal format."""
import pytest
from team_runtime.policy import DEFAULT_POLICY, PolicyValidationError, validate_policy


def test_defaults_and_overrides():
    assert validate_policy({}) == DEFAULT_POLICY
    settings = validate_policy({"network_access": False, "model": "configured-model",
                                "max_sessions": 3, "token_budget": 90000})
    assert settings["model"] == "configured-model"
    assert settings["max_sessions"] == 3
    assert settings["token_budget"] == 90000
    assert settings["network_access"] is False
    assert settings["max_subagents_per_session"] == 0
    settings["model"] = "changed copy"
    assert DEFAULT_POLICY["model"] == "gpt-5.6-luna"


@pytest.mark.parametrize("bad", [
    {"unknown": 1}, {"max_sessions": True}, {"max_sessions": 0},
    {"max_repair_attempts": -1}, {"max_run_seconds": 10, "max_turn_seconds": 11},
    {"network_access": 1}, {"reasoning": "not-a-level"}, {"model": ""},
    {"model": "bad\x00value"}, {"token_budget": 1.5}, {"max_turn_seconds": float("inf")},
])
def test_invalid_resource_limits(bad):
    with pytest.raises((PolicyValidationError, TypeError)):
        validate_policy(bad)
