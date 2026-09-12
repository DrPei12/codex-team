"""Validation and canonicalisation rules for Team Auto proposals.

The proposal is model output, so this module is deliberately stricter than a
normal dataclass parser.  It rejects unknown fields instead of dropping them,
checks the graph and ownership invariants, and keeps gate commands as argv
without ever interpreting them through a shell.

This module only uses the Python standard library.  Gate validation is a
syntax/safety gate; the controller still has to present the command to a user
for review and execute it with ``shell=False``.  A valid gate is not a claim
that its command is sandboxed or that its executable is available.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


__all__ = [
    "DEFAULT_POLICY",
    "PROPOSAL_SCHEMA",
    "ProposalValidationError",
    "digest",
    "owns",
    "validate_policy",
    "validate_proposal",
]


class ProposalValidationError(ValueError):
    """Raised when model output violates the Team Auto proposal contract."""


_SCHEMA_VERSION = "0.2"

# These are deliberately finite local defaults selected for this experiment.
# They are policy values, rather than general-purpose scheduling constants.
DEFAULT_POLICY: dict[str, Any] = {
    "model": "gpt-5.6-luna",
    "reasoning": "max",
    "max_sessions": 2,
    "max_subagents_per_session": 1,
    "max_turn_seconds": 1200,
    "max_run_seconds": 3600,
    "max_repair_attempts": 2,
    "token_budget": 200000,
    "network_access": False,
}

_POLICY_KEYS = frozenset(DEFAULT_POLICY)
_REASONING_LEVELS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
)


def _string_schema(*, min_length: int = 1) -> dict[str, Any]:
    return {"type": "string", "minLength": min_length}


def _array_schema(items: dict[str, Any], *, min_items: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "array", "items": items}
    if min_items is not None:
        result["minItems"] = min_items
    return result


_CHECKPOINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": _string_schema(),
        "requires_user_acceptance": {"type": "boolean"},
    },
    "required": ["title", "requires_user_acceptance"],
    "additionalProperties": False,
}

_REQUIREMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": _string_schema(),
        "text": _string_schema(),
        "owner": {
            **_string_schema(),
            "description": (
                "Exactly one existing work_packages id, for example WP1. "
                "Do not use WP1/core-owner, combined ids, or invent another owner format. "
                "For a requirement spanning multiple packages, choose one work package "
                "responsible for its overall acceptance."
            ),
        },
        "gate_ids": _array_schema(_string_schema(), min_items=1),
    },
    "required": ["id", "text", "owner", "gate_ids"],
    "additionalProperties": False,
}

_WORK_PACKAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": _string_schema(),
        "title": _string_schema(),
        "goal": _string_schema(),
        "depends_on": _array_schema(_string_schema()),
        "write_paths": _array_schema(_string_schema()),
        "acceptance_notes": _string_schema(),
    },
    "required": [
        "id",
        "title",
        "goal",
        "depends_on",
        "write_paths",
        "acceptance_notes",
    ],
    "additionalProperties": False,
}

_GATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": _string_schema(),
        "argv": _array_schema(_string_schema(), min_items=1),
        "timeout_seconds": {"type": "integer", "minimum": 1},
        "description": _string_schema(),
    },
    "required": ["id", "argv", "timeout_seconds", "description"],
    "additionalProperties": False,
}

# Keep this object directly usable as an OpenAI/Codex outputSchema.  Every
# object in the schema is closed and every declared field is required.  The
# cross-field rules (DAG, ownership, question draft semantics, and gate
# command safety) are implemented by validate_proposal below.
PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string", "const": _SCHEMA_VERSION},
        "objective": _string_schema(),
        "questions": _array_schema(_string_schema()),
        "assumptions": _array_schema(_string_schema()),
        "mode": {"type": "string", "enum": ["single-session", "multi-session"]},
        "allocation_reason": _string_schema(),
        "checkpoint": _CHECKPOINT_SCHEMA,
        "requirements": _array_schema(_REQUIREMENT_SCHEMA),
        "work_packages": _array_schema(_WORK_PACKAGE_SCHEMA),
        "gates": _array_schema(_GATE_SCHEMA),
    },
    "required": [
        "schema_version",
        "objective",
        "questions",
        "assumptions",
        "mode",
        "allocation_reason",
        "checkpoint",
        "requirements",
        "work_packages",
        "gates",
    ],
    "additionalProperties": False,
}


_SLUG_RE = re.compile(r"^[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*$", re.ASCII)
_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$", re.ASCII)

# Names that can directly interpret a shell command.  The aliases include the
# common Windows and POSIX spellings.  Wrappers such as env/xargs/busybox are
# blocked as well because they can trivially launch one of these interpreters.
_SHELL_COMMANDS = frozenset(
    {
        "bash",
        "bash.exe",
        "busybox",
        "cmd",
        "cmd.exe",
        "command",
        "command.com",
        "csh",
        "csh.exe",
        "dash",
        "dash.exe",
        "env",
        "env.exe",
        "fish",
        "fish.exe",
        "ksh",
        "ksh.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "sh",
        "sh.exe",
        "tcsh",
        "tcsh.exe",
        "wsl",
        "wsl.exe",
        "xargs",
        "zsh",
        "zsh.exe",
        "git-bash",
        "git-bash.exe",
        "msys",
        "msys.exe",
        "cygwin",
        "cygwin.exe",
    }
)

_PYTHON_COMMANDS = frozenset({"python", "python.exe", "py", "py.exe"})
_PYTHON_COMMAND_RE = re.compile(r"^(?:python(?:3(?:\.\d+)?)?|py)(?:\.exe)?$", re.ASCII)
_NODE_COMMANDS = frozenset({"node", "node.exe", "nodejs", "nodejs.exe"})
_INLINE_INTERPRETERS = frozenset(
    {
        "awk",
        "bun",
        "deno",
        "gawk",
        "lua",
        "perl",
        "php",
        "r",
        "rscript",
        "ruby",
    }
)
_INLINE_FLAGS = frozenset(
    {
        "-c",
        "--command",
        "--code",
        "-e",
        "--eval",
        "--evaluate",
        "-p",
        "--print",
        "-r",
        "--require",
    }
)


def _type_error(label: str, expected: str) -> TypeError:
    return TypeError(f"{label} must be {expected}")


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _type_error(label, "an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise _type_error(label, "a list")
    return value


def _require_string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise _type_error(label, "a string")
    if nonempty and not value.strip():
        raise ProposalValidationError(f"{label} must not be empty")
    if "\x00" in value:
        raise ProposalValidationError(f"{label} must not contain NUL")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise _type_error(label, "a boolean")
    return value


def _require_integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _type_error(label, "an integer")
    if minimum is not None and value < minimum:
        raise ProposalValidationError(f"{label} must be >= {minimum}")
    return value


def _check_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected, key=lambda item: str(item))
    if missing:
        raise ProposalValidationError(f"{label} missing required field(s): {', '.join(missing)}")
    if unknown:
        rendered = ", ".join(repr(item) for item in unknown)
        raise ProposalValidationError(f"{label} contains unknown field(s): {rendered}")


def _require_unique(values: list[str], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ProposalValidationError(f"{label} contains duplicate value: {value!r}")
        seen.add(value)


def _require_slug(value: Any, label: str) -> str:
    value = _require_string(value, label)
    if not _SLUG_RE.fullmatch(value):
        raise ProposalValidationError(
            f"{label} must be an ASCII slug (letters, digits, '-' or '_')"
        )
    return value


def _normalise_repo_path(value: Any, *, allow_dot: bool = True) -> str | None:
    """Return a case-folded slash path, or ``None`` for unsafe input.

    The proposal protocol has no glob syntax.  A bare path owns the path and
    its descendants; callers compare the returned canonical forms with the
    tree helpers below.  Backslashes are accepted as Windows separators so
    the same rule works in the Windows experiment checkout.
    """

    if not isinstance(value, str) or not value:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    candidate = value.replace("\\", "/")
    if not candidate or candidate.startswith("/") or candidate.startswith("//"):
        return None
    if re.match(r"^[A-Za-z]:", candidate, re.ASCII):
        return None
    # ':' is an alternate-data-stream separator on Windows and is not needed
    # by a repository-relative ownership declaration.
    if ":" in candidate:
        return None
    if any(mark in candidate for mark in "*?[]"):
        return None
    parts = candidate.split("/")
    if any(part == ".." for part in parts):
        return None
    # Redundant separators and ``.`` segments do not escape the repository,
    # so canonicalise them just as the Git-facing ownership checks do.
    parts = [part for part in parts if part not in {"", "."}]
    if not parts:
        return "." if allow_dot else None
    # ``casefold`` gives deterministic Windows-style case-insensitive
    # ownership checks while retaining Unicode repository names.
    return "/".join(part.casefold() for part in parts)


def _safe_repo_path(value: Any, label: str, *, allow_dot: bool = True) -> str:
    result = _normalise_repo_path(value, allow_dot=allow_dot)
    if result is None:
        raise ProposalValidationError(
            f"{label} must be a safe repository-relative path without glob or '..'"
        )
    return result


def _path_covers(root: str, path: str) -> bool:
    return root == "." or root == path or path.startswith(root + "/")


def _trees_overlap(left: str, right: str) -> bool:
    return _path_covers(left, right) or _path_covers(right, left)


def owns(path: str, roots: list[str]) -> bool:
    """Return whether a safe repository path belongs to one of ``roots``.

    Roots are bare paths, so ``owns('src/a.py', ['src'])`` is true while
    ``owns('src2/a.py', ['src'])`` is false.  Invalid or non-list input returns
    false because this helper is also used at controller boundaries; full
    proposal validation raises a diagnostic error instead.
    """

    if not isinstance(roots, list):
        return False
    canonical_path = _normalise_repo_path(path, allow_dot=True)
    if canonical_path is None:
        return False
    for root in roots:
        canonical_root = _normalise_repo_path(root, allow_dot=True)
        if canonical_root is not None and _path_covers(canonical_root, canonical_path):
            return True
    return False


def _validate_string_list(values: Any, label: str) -> list[str]:
    values = _require_list(values, label)
    result = [_require_string(value, f"{label}[{index}]") for index, value in enumerate(values)]
    return result


def _validate_requirement(value: Any, index: int) -> dict[str, Any]:
    item = _require_dict(value, f"requirements[{index}]")
    _check_exact_keys(item, {"id", "text", "owner", "gate_ids"}, f"requirements[{index}]")
    requirement_id = _require_slug(item["id"], f"requirements[{index}].id")
    _require_string(item["text"], f"requirements[{index}].text")
    _require_string(item["owner"], f"requirements[{index}].owner")
    gate_ids = _validate_string_list(item["gate_ids"], f"requirements[{index}].gate_ids")
    if not gate_ids:
        raise ProposalValidationError(f"requirements[{index}].gate_ids must not be empty")
    for gate_index, gate_id in enumerate(gate_ids):
        _require_slug(gate_id, f"requirements[{index}].gate_ids[{gate_index}]")
    _require_unique(gate_ids, f"requirements[{index}].gate_ids")
    return {
        "id": requirement_id,
        "text": item["text"],
        "owner": item["owner"],
        "gate_ids": gate_ids,
    }


def _validate_package(value: Any, index: int, *, allow_dot: bool) -> tuple[dict[str, Any], list[str]]:
    item = _require_dict(value, f"work_packages[{index}]")
    expected = {"id", "title", "goal", "depends_on", "write_paths", "acceptance_notes"}
    _check_exact_keys(item, expected, f"work_packages[{index}]")
    package_id = _require_slug(item["id"], f"work_packages[{index}].id")
    _require_string(item["title"], f"work_packages[{index}].title")
    _require_string(item["goal"], f"work_packages[{index}].goal")
    depends_on = _validate_string_list(item["depends_on"], f"work_packages[{index}].depends_on")
    for dep_index, dependency in enumerate(depends_on):
        _require_slug(dependency, f"work_packages[{index}].depends_on[{dep_index}]")
    _require_unique(depends_on, f"work_packages[{index}].depends_on")
    if package_id in depends_on:
        raise ProposalValidationError(f"work_packages[{index}] cannot depend on itself")

    write_paths = _require_list(item["write_paths"], f"work_packages[{index}].write_paths")
    canonical_paths: list[str] = []
    for path_index, path in enumerate(write_paths):
        canonical = _safe_repo_path(
            path,
            f"work_packages[{index}].write_paths[{path_index}]",
            allow_dot=allow_dot,
        )
        if canonical == "." and not allow_dot:
            raise ProposalValidationError("'.' write path is only allowed for single-session")
        if any(_trees_overlap(canonical, previous) for previous in canonical_paths):
            raise ProposalValidationError(
                f"work_packages[{index}].write_paths contains overlapping paths"
            )
        canonical_paths.append(canonical)
    _require_string(item["acceptance_notes"], f"work_packages[{index}].acceptance_notes")
    return (
        {
            "id": package_id,
            "title": item["title"],
            "goal": item["goal"],
            "depends_on": depends_on,
            "write_paths": write_paths,
            "acceptance_notes": item["acceptance_notes"],
        },
        canonical_paths,
    )


def _command_basename(command: Any) -> str:
    command = _require_string(command, "gate.argv[0]")
    if any(char.isspace() for char in command):
        raise ProposalValidationError("gate.argv[0] must be one executable argv item")
    candidate = command.replace("\\", "/")
    if candidate.startswith("/") or candidate.startswith("//") or re.match(
        r"^[A-Za-z]:", candidate, re.ASCII
    ):
        raise ProposalValidationError("gate executable must not be an absolute path")
    if any(part == ".." for part in candidate.split("/")):
        raise ProposalValidationError("gate executable path contains an unsafe segment")
    if any(mark in candidate for mark in "*?[]") or ":" in candidate:
        raise ProposalValidationError("gate executable path contains an unsafe character")
    parts = [part for part in candidate.split("/") if part not in {"", "."}]
    if not parts:
        raise ProposalValidationError("gate executable path is empty")
    return parts[-1].casefold()


def _reject_control_argv(argv: list[Any], label: str) -> list[str]:
    result: list[str] = []
    for index, value in enumerate(argv):
        text = _require_string(value, f"{label}[{index}]", nonempty=False)
        if any(ord(char) < 32 or ord(char) == 127 for char in text):
            raise ProposalValidationError(f"{label}[{index}] contains a control character")
        result.append(text)
    return result


def _path_like_is_safe(value: str) -> None:
    """Reject explicit absolute/traversal path arguments in a gate."""

    if value in {".", ".."} or "/" in value or "\\" in value:
        _safe_repo_path(value, "gate path argument", allow_dot=True)
    elif re.match(r"^[A-Za-z]:", value, re.ASCII) or value.startswith("~"):
        raise ProposalValidationError("gate path arguments must stay repository-relative")


def _validate_python_argv(argv: list[str]) -> None:
    tokens = argv[1:]
    if not tokens:
        raise ProposalValidationError("python gate must run a repository script or -m module")
    index = 0
    script: str | None = None
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            if index + 1 >= len(tokens):
                raise ProposalValidationError("python -- requires a repository script")
            index += 1
            script = tokens[index]
            break
        # Python short options can be grouped (-Imunittest, -IcCODE).
        # Parse only interpreter options, stopping at -m or the script; the
        # remaining argv belongs to that module/script, including -c and -p.
        if token.startswith("-") and not token.startswith("--") and token != "-":
            option_index = 1
            while option_index < len(token):
                option = token[option_index]
                if option == "c":
                    raise ProposalValidationError("python inline-code flags are not allowed")
                if option == "m":
                    token = "-m" + token[option_index + 1 :]
                    break
                if option in {"W", "X", "Q"}:
                    if option_index + 1 == len(token):
                        index += 1
                        if index >= len(tokens):
                            raise ProposalValidationError(f"python option -{option} requires a value")
                    break
                option_index += 1
        if token == "-m" or token.startswith("-m") and len(token) > 2:
            module = token[2:] if len(token) > 2 else None
            if module is None:
                index += 1
                if index >= len(tokens):
                    raise ProposalValidationError("python -m requires a module")
                module = tokens[index]
            if not _MODULE_RE.fullmatch(module):
                raise ProposalValidationError("python -m module must be an identifier")
            # Module arguments are still argv.  Check explicit path-shaped
            # values for traversal, but do not reinterpret option values.
            for argument in tokens[index + 1 :]:
                _path_like_is_safe(argument)
            return
        if len(tokens) == 1 and token in {"--version", "-V", "-v", "-h", "--help"}:
            return
        if token.startswith("-"):
            # A handful of Python options consume one value; skipping that
            # value prevents it from being mistaken for the script path.
            if token == "--check-hash-based-pycs":
                index += 1
                if index >= len(tokens):
                    raise ProposalValidationError(f"python option {token!r} requires a value")
            index += 1
            continue
        script = token
        break
    if script is None:
        raise ProposalValidationError("python gate must run a repository script or -m module")
    canonical = _safe_repo_path(script, "python script", allow_dot=False)
    # Python can execute extensionless repository tools too; safety comes from
    # the repository-relative path check rather than a filename suffix.
    if canonical == ".":
        raise ProposalValidationError("python script must be a repository file path")
    for argument in tokens[index + 1 :]:
        if not argument.startswith("-"):
            _path_like_is_safe(argument)


def _validate_node_argv(argv: list[str]) -> None:
    tokens = argv[1:]
    if not tokens:
        raise ProposalValidationError("node gate must run a repository script or --test")
    test_mode = False
    script: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        lower = token.casefold()
        if (
            lower in {"-e", "-p", "--eval", "--print", "-r", "--require"}
            or lower.startswith(("--eval=", "--print=", "--require="))
            or token.startswith(("-e", "-p", "-r")) and not token.startswith("--")
        ):
            raise ProposalValidationError("node inline-code flags are not allowed")
        if lower == "--test" or lower.startswith("--test="):
            test_mode = True
            index += 1
            continue
        if len(tokens) == 1 and lower in {"--version", "-v", "-h", "--help"}:
            return
        if token == "--":
            if index + 1 < len(tokens):
                index += 1
                script = tokens[index]
            break
        if token.startswith("-"):
            # Consume supported value-taking runtime options so their values
            # cannot masquerade as a script and hide a later inline flag.
            if lower in {
                "--test-name-pattern", "--test-skip-pattern", "--test-reporter",
                "--test-reporter-destination", "--test-concurrency", "--test-timeout",
                "--test-shard", "--conditions", "--input-type",
                "--inspect-port", "--title", "--stack-trace-limit", "--disable-warning",
            } or token == "-C":
                index += 1
                if index >= len(tokens):
                    raise ProposalValidationError(f"node option {token!r} requires a value")
                _path_like_is_safe(tokens[index])
            elif "=" not in token and lower not in {
                "--check", "-c", "--no-warnings", "--trace-warnings",
                "--trace-deprecation", "--no-deprecation", "--throw-deprecation",
                "--enable-source-maps", "--expose-gc",
                "--experimental-test-coverage", "--test-only", "--test-force-exit",
                "--watch", "--watch-preserve-output", "--inspect", "--inspect-brk",
            }:
                raise ProposalValidationError(f"unsupported node interpreter option: {token!r}")
            index += 1
            continue
        script = token
        break

    if script is None:
        if test_mode:
            return
        raise ProposalValidationError("node gate must run a repository script or --test")
    canonical = _safe_repo_path(script, "node script", allow_dot=False)
    if canonical == ".":
        raise ProposalValidationError("node script must be a repository file path")
    for argument in tokens[index + 1 :]:
        if not argument.startswith("-"):
            _path_like_is_safe(argument)


def _validate_gate_argv(value: Any, index: int) -> list[str]:
    argv = _require_list(value, f"gates[{index}].argv")
    if not argv:
        raise ProposalValidationError(f"gates[{index}].argv must not be empty")
    result = _reject_control_argv(argv, f"gates[{index}].argv")
    command = _command_basename(result[0])
    if command in _SHELL_COMMANDS:
        raise ProposalValidationError(f"shell interpreter is not allowed in gates: {result[0]!r}")

    if command in _PYTHON_COMMANDS or _PYTHON_COMMAND_RE.fullmatch(command):
        _validate_python_argv(result)
    elif command in _NODE_COMMANDS:
        _validate_node_argv(result)
    else:
        # Reject inline evaluation for the other well-known interpreters too.
        if command in _INLINE_INTERPRETERS:
            for token in result[1:]:
                lower = token.casefold()
                if lower in _INLINE_FLAGS or lower.startswith("--eval="):
                    raise ProposalValidationError("inline interpreter code is not allowed in gates")
        # The first command is still argv and is never shell-expanded.  Check
        # obvious path-shaped arguments for absolute/traversal escapes while
        # leaving normal test/build CLI values alone.
        for token in result[1:]:
            if token.startswith("-"):
                continue
            _path_like_is_safe(token)
    return result


def _validate_gate(value: Any, index: int) -> dict[str, Any]:
    item = _require_dict(value, f"gates[{index}]")
    expected = {"id", "argv", "timeout_seconds", "description"}
    _check_exact_keys(item, expected, f"gates[{index}]")
    gate_id = _require_slug(item["id"], f"gates[{index}].id")
    argv = _validate_gate_argv(item["argv"], index)
    timeout_seconds = _require_integer(
        item["timeout_seconds"], f"gates[{index}].timeout_seconds", minimum=1
    )
    _require_string(item["description"], f"gates[{index}].description")
    return {
        "id": gate_id,
        "argv": argv,
        "timeout_seconds": timeout_seconds,
        "description": item["description"],
    }


def _validate_package_graph(packages: list[dict[str, Any]]) -> None:
    package_ids = [package["id"] for package in packages]
    _require_unique(package_ids, "work_packages.id")
    package_set = set(package_ids)
    for package in packages:
        for dependency in package["depends_on"]:
            if dependency not in package_set:
                raise ProposalValidationError(
                    f"work package {package['id']!r} depends on unknown package {dependency!r}"
                )

    # Kahn's algorithm gives a small, deterministic cycle check and also
    # catches a dependency that was accidentally omitted from the package set.
    indegree = {package_id: 0 for package_id in package_ids}
    children: dict[str, list[str]] = {package_id: [] for package_id in package_ids}
    for package in packages:
        for dependency in package["depends_on"]:
            indegree[package["id"]] += 1
            children[dependency].append(package["id"])
    ready = [package_id for package_id in package_ids if indegree[package_id] == 0]
    visited: list[str] = []
    while ready:
        current = ready.pop(0)
        visited.append(current)
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if len(visited) != len(package_ids):
        raise ProposalValidationError("work_packages.depends_on must form an acyclic graph")

def _validate_cross_references(
    requirements: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    gates: list[dict[str, Any]],
) -> None:
    package_ids = {package["id"] for package in packages}
    gate_ids = {gate["id"] for gate in gates}
    requirement_ids = [requirement["id"] for requirement in requirements]
    _require_unique(requirement_ids, "requirements.id")
    for requirement in requirements:
        if requirement["owner"] not in package_ids:
            raise ProposalValidationError(
                f"requirement {requirement['id']!r} owner {requirement['owner']!r} is not a work package"
            )
        missing = [gate_id for gate_id in requirement["gate_ids"] if gate_id not in gate_ids]
        if missing:
            raise ProposalValidationError(
                f"requirement {requirement['id']!r} references unknown gate(s): {', '.join(missing)}"
            )


def _check_ownership(packages: list[dict[str, Any]], canonical_paths: list[list[str]]) -> None:
    for left_index, left_package in enumerate(packages):
        for right_index in range(left_index + 1, len(packages)):
            for left_path in canonical_paths[left_index]:
                for right_path in canonical_paths[right_index]:
                    if _trees_overlap(left_path, right_path):
                        raise ProposalValidationError(
                            "different work packages cannot own overlapping path trees: "
                            f"{left_package['id']!r} and {packages[right_index]['id']!r}"
                        )


def validate_proposal(proposal: dict[str, Any]) -> None:
    """Validate a model proposal and raise on the first contract violation."""

    proposal = _require_dict(proposal, "proposal")
    top_level = {
        "schema_version",
        "objective",
        "questions",
        "assumptions",
        "mode",
        "allocation_reason",
        "checkpoint",
        "requirements",
        "work_packages",
        "gates",
    }
    _check_exact_keys(proposal, top_level, "proposal")
    if proposal["schema_version"] != _SCHEMA_VERSION:
        raise ProposalValidationError("proposal.schema_version must be '0.2'")
    _require_string(proposal["objective"], "proposal.objective")
    questions = _validate_string_list(proposal["questions"], "proposal.questions")
    _validate_string_list(proposal["assumptions"], "proposal.assumptions")
    mode = _require_string(proposal["mode"], "proposal.mode")
    if mode not in {"single-session", "multi-session"}:
        raise ProposalValidationError("proposal.mode must be single-session or multi-session")
    _require_string(proposal["allocation_reason"], "proposal.allocation_reason")

    checkpoint = _require_dict(proposal["checkpoint"], "proposal.checkpoint")
    _check_exact_keys(
        checkpoint,
        {"title", "requires_user_acceptance"},
        "proposal.checkpoint",
    )
    _require_string(checkpoint["title"], "proposal.checkpoint.title")
    _require_bool(
        checkpoint["requires_user_acceptance"],
        "proposal.checkpoint.requires_user_acceptance",
    )

    raw_requirements = _require_list(proposal["requirements"], "proposal.requirements")
    requirements = [_validate_requirement(item, index) for index, item in enumerate(raw_requirements)]
    raw_packages = _require_list(proposal["work_packages"], "proposal.work_packages")
    packages: list[dict[str, Any]] = []
    canonical_paths: list[list[str]] = []
    for index, item in enumerate(raw_packages):
        package, paths = _validate_package(item, index, allow_dot=mode == "single-session")
        packages.append(package)
        canonical_paths.append(paths)
    raw_gates = _require_list(proposal["gates"], "proposal.gates")
    gates = [_validate_gate(item, index) for index, item in enumerate(raw_gates)]

    package_ids = [package["id"] for package in packages]
    _require_unique(package_ids, "work_packages.id")
    gate_ids = [gate["id"] for gate in gates]
    _require_unique(gate_ids, "gates.id")
    requirement_ids = [requirement["id"] for requirement in requirements]
    _require_unique(requirement_ids, "requirements.id")

    if packages:
        if mode == "single-session" and len(packages) != 1:
            raise ProposalValidationError("single-session proposals must contain exactly one work package")
        if mode == "multi-session" and len(packages) < 2:
            raise ProposalValidationError("multi-session proposals must contain at least two work packages")
        # Check dependency references and cycles even for a question draft that
        # already contains a partial package outline.
        _validate_package_graph(packages)
        _check_ownership(packages, canonical_paths)
    elif mode == "multi-session" and not questions:
        # The complete-plan branch below emits the more useful non-empty
        # package diagnostic; this branch is kept explicit for readability.
        raise ProposalValidationError("multi-session proposals need work packages")

    if not questions:
        if not requirements or not packages or not gates:
            raise ProposalValidationError(
                "a proposal without questions must contain requirements, work packages, and gates"
            )
        _validate_cross_references(requirements, packages, gates)
    elif requirements and packages and gates:
        # A question draft may intentionally leave all plan lists empty.  If
        # the model supplied a complete outline as well, enforce its refs too.
        _validate_cross_references(requirements, packages, gates)


def digest(value: Any) -> str:
    """Return the protocol digest of a JSON value.

    Canonical JSON uses sorted object keys, compact separators, UTF-8, and no
    non-standard NaN/Infinity values.  List order remains meaningful.
    """

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("value must be JSON serializable with finite numbers") from exc
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Merge and validate finite local policy limits.

    Unknown keys fail closed.  ``{}`` selects all explicit finite defaults;
    callers that expose an optional policy should pass ``policy or {}``.
    """

    policy = _require_dict(policy, "policy")
    unknown = sorted(set(policy) - _POLICY_KEYS, key=lambda item: str(item))
    if unknown:
        rendered = ", ".join(repr(item) for item in unknown)
        raise ProposalValidationError(f"policy contains unknown field(s): {rendered}")

    result = dict(DEFAULT_POLICY)
    for key, value in policy.items():
        if key in {"model", "reasoning"}:
            text = _require_string(value, f"policy.{key}")
            if key == "reasoning" and text not in _REASONING_LEVELS:
                raise ProposalValidationError(
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
        raise ProposalValidationError("policy.max_run_seconds must be >= max_turn_seconds")
    return result
