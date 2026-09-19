"""Native observations retain useful evidence without credential values."""
from team_runtime.redaction import redact


def test_nested_credentials_and_nonsecret_evidence():
    source = {"authorization": "private", "nested": [
        {"message": "failed with Bearer abc.def-token", "tokens": 123, "goal": "保留原始证据"},
        {"api_key": "private", "message": "api_key=private"}]}
    result = redact(source)
    assert result["authorization"] == "[REDACTED]"
    assert result["nested"][0] == {"message": "failed with [REDACTED]",
                                  "tokens": 123, "goal": "保留原始证据"}
    assert result["nested"][1] == {"api_key": "[REDACTED]", "message": "[REDACTED]"}
    assert source["authorization"] == "private"
