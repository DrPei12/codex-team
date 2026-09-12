import hashlib
import json
import unittest

from team_runtime.rules import (
    DEFAULT_POLICY,
    PROPOSAL_SCHEMA,
    ProposalValidationError,
    digest,
    owns,
    validate_policy,
    validate_proposal,
)


def _gate(gate_id="tests", argv=None):
    return {
        "id": gate_id,
        "argv": argv or ["python", "-m", "unittest", "discover", "-s", "tests"],
        "timeout_seconds": 60,
        "description": "run the repository tests",
    }


def _package(package_id="core", *, depends_on=None, write_paths=None):
    return {
        "id": package_id,
        "title": "Core package",
        "goal": "Implement the core behavior",
        "depends_on": [] if depends_on is None else depends_on,
        "write_paths": ["team_runtime"] if write_paths is None else write_paths,
        "acceptance_notes": "Targeted tests pass",
    }


def _proposal(*, questions=None, mode="single-session", packages=None, requirements=None, gates=None):
    if questions is None:
        questions = []
    if packages is None:
        packages = [_package()]
    if requirements is None:
        requirements = [
            {"id": "req-core", "text": "The core behavior works", "owner": packages[0]["id"], "gate_ids": ["tests"]}
        ] if packages else []
    if gates is None:
        gates = [_gate()]
    return {
        "schema_version": "0.2",
        "objective": "Deliver the requested change",
        "questions": questions,
        "assumptions": ["The repository checkout is available"],
        "mode": mode,
        "allocation_reason": "The package boundary matches the requested work",
        "checkpoint": {"title": "Review the result", "requires_user_acceptance": True},
        "requirements": requirements,
        "work_packages": packages,
        "gates": gates,
    }


class ProposalRulesTests(unittest.TestCase):
    def test_schema_closes_every_object_and_requires_every_field(self):
        self.assertFalse(PROPOSAL_SCHEMA["additionalProperties"])
        self.assertEqual(set(PROPOSAL_SCHEMA["required"]), set(PROPOSAL_SCHEMA["properties"]))
        for name in ("checkpoint", "requirements", "work_packages", "gates"):
            if name == "checkpoint":
                nested = PROPOSAL_SCHEMA["properties"][name]
            else:
                nested = PROPOSAL_SCHEMA["properties"][name]["items"]
            self.assertFalse(nested["additionalProperties"])
            self.assertEqual(set(nested["required"]), set(nested["properties"]))

    def test_complete_single_proposal_is_valid(self):
        validate_proposal(_proposal())

    def test_question_draft_may_leave_plan_lists_empty(self):
        validate_proposal(
            _proposal(
                questions=["Which repository layer should change?"],
                packages=[],
                requirements=[],
                gates=[],
            )
        )

    def test_multi_session_requires_two_non_overlapping_packages(self):
        proposal = _proposal(
            mode="multi-session",
            packages=[
                _package("core", write_paths=["team_runtime/core"]),
                _package("ui", depends_on=["core"], write_paths=["team_runtime/ui"]),
            ],
            requirements=[
                {"id": "req-core", "text": "Core works", "owner": "core", "gate_ids": ["tests"]},
                {"id": "req-ui", "text": "UI works", "owner": "ui", "gate_ids": ["tests"]},
            ],
        )
        validate_proposal(proposal)

    def test_unknown_fields_fail_closed_at_all_levels(self):
        proposal = _proposal()
        proposal["unexpected"] = True
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

        proposal = _proposal()
        proposal["gates"][0]["extra"] = "must not be dropped"
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

    def test_requirements_need_existing_owner_and_gate(self):
        proposal = _proposal()
        proposal["requirements"][0]["owner"] = "missing"
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

        proposal = _proposal()
        proposal["requirements"][0]["gate_ids"] = ["missing"]
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

    def test_dag_cycles_and_overlap_fail(self):
        proposal = _proposal(
            mode="multi-session",
            packages=[
                _package("a", depends_on=["b"], write_paths=["src/a"]),
                _package("b", depends_on=["a"], write_paths=["src/b"]),
            ],
            requirements=[
                {"id": "req-a", "text": "A", "owner": "a", "gate_ids": ["tests"]},
                {"id": "req-b", "text": "B", "owner": "b", "gate_ids": ["tests"]},
            ],
        )
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

        proposal = _proposal(
            mode="multi-session",
            packages=[
                _package("a", write_paths=["src"]),
                _package("b", write_paths=["src/nested"]),
            ],
            requirements=[
                {"id": "req-a", "text": "A", "owner": "a", "gate_ids": ["tests"]},
                {"id": "req-b", "text": "B", "owner": "b", "gate_ids": ["tests"]},
            ],
        )
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

    def test_path_safety_and_dot_rule(self):
        proposal = _proposal()
        proposal["work_packages"][0]["write_paths"] = ["../outside"]
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

        proposal = _proposal(mode="multi-session", packages=[_package("a", write_paths=["."]), _package("b", write_paths=[])])
        proposal["requirements"] = [
            {"id": "req-a", "text": "A", "owner": "a", "gate_ids": ["tests"]},
            {"id": "req-b", "text": "B", "owner": "b", "gate_ids": ["tests"]},
        ]
        with self.assertRaises(ProposalValidationError):
            validate_proposal(proposal)

    def test_gate_argv_is_shell_free_but_allows_supported_python_and_node_forms(self):
        for argv in (
            ["python", "-m", "unittest", "discover"],
            ["python", "-m", "pytest", "tests"],
            ["python", "repo-script.py"],
            ["node", "repo-script.js"],
            ["pytest", "-q", "tests"],
            ["cargo", "test"],
        ):
            proposal = _proposal(gates=[_gate(argv=argv)])
            validate_proposal(proposal)

        for argv in (
            ["powershell", "-Command", "Write-Host ok"],
            ["bash", "-c", "echo unsafe"],
            ["python", "-c", "print('unsafe')"],
            ["node", "-e", "console.log('unsafe')"],
            ["python", "../outside.py"],
        ):
            proposal = _proposal(gates=[_gate(argv=argv)])
            with self.assertRaises(ProposalValidationError):
                validate_proposal(proposal)

    def test_gate_module_and_script_options_are_not_interpreter_options(self):
        for argv in (
            ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_core.py", "-v"],
            ["python", "-Imunittest", "discover", "-p", "test_core.py"],
            ["python", "-W", "ignore", "-m", "unittest", "discover", "-p", "test_core.py"],
            ["python", "repo-script.py", "-c", "config", "-p", "value", "--eval=value"],
            ["python", "--", "repo-script.py", "-c", "config"],
            ["node", "repo-script.js", "-e", "value", "-p", "value", "--print=value"],
            ["node", "--", "repo-script.js", "-e", "value"],
            ["node", "--test", "--test-name-pattern", "core", "tests/core.js"],
            ["node", "--check", "repo-script.js"],
        ):
            with self.subTest(argv=argv):
                validate_proposal(_proposal(gates=[_gate(argv=argv)]))

    def test_interpreter_inline_code_and_unsafe_paths_remain_rejected(self):
        for argv in (
            ["python", "-c", "pass"],
            ["python", "-cpass"],
            ["python", "-Icpass"],
            ["python", "-W", "ignore", "-c", "pass"],
            ["node", "-e", "0"],
            ["node", "-p", "0"],
            ["node", "-e0"],
            ["node", "-p0"],
            ["node", "--eval=0"],
            ["node", "--print=0"],
            ["node", "--test-name-pattern", "core", "-e", "0"],
            ["node", "--unknown-option", "value", "-e", "0"],
            ["node", "--require", "setup.js", "repo-script.js"],
            ["cmd.exe", "/c", "echo unsafe"],
            ["C:/Python/python.exe", "repo-script.py"],
            ["python", "C:/outside.py"],
            ["python", "-m", "unittest", "../tests"],
            ["python", "repo-script.py", "../outside"],
            ["node", "../outside.js"],
            ["node", "repo-script.js", "../outside"],
        ):
            with self.subTest(argv=argv), self.assertRaises(ProposalValidationError):
                validate_proposal(_proposal(gates=[_gate(argv=argv)]))

    def test_cross_package_requirement_has_one_existing_acceptance_owner(self):
        proposal = _proposal(
            mode="multi-session",
            packages=[_package("WP1", write_paths=["core"]), _package("WP2", write_paths=["ui"])],
        )
        proposal["requirements"][0]["text"] = "Core and UI work together"
        validate_proposal(proposal)
        for invalid_owner in ("WP1/core-owner", "WP1+WP2", "WP1,WP2"):
            proposal["requirements"][0]["owner"] = invalid_owner
            with self.subTest(owner=invalid_owner), self.assertRaises(ProposalValidationError):
                validate_proposal(proposal)

    def test_owns_uses_bare_subtree_paths_and_rejects_escape(self):
        self.assertTrue(owns("src", ["src"]))
        self.assertTrue(owns("src\\nested\\file.py", ["src"]))
        self.assertTrue(owns("anything/file.py", ["."]))
        self.assertFalse(owns("src2/file.py", ["src"]))
        self.assertFalse(owns("../outside.py", ["."]))
        self.assertFalse(owns("src/file.py", "src"))

    def test_digest_is_sorted_compact_utf8_sha256(self):
        value = {"z": "雪", "a": [2, 1]}
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        self.assertEqual(digest(value), expected)
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_policy_defaults_overrides_and_limits(self):
        self.assertEqual(validate_policy({}), DEFAULT_POLICY)
        policy = validate_policy({"max_subagents_per_session": 0, "network_access": True})
        self.assertEqual(policy["max_subagents_per_session"], 0)
        self.assertTrue(policy["network_access"])
        for bad in (
            {"unknown": 1},
            {"max_sessions": True},
            {"max_repair_attempts": -1},
            {"max_run_seconds": 10, "max_turn_seconds": 11},
            {"network_access": 1},
            {"reasoning": "not-a-level"},
        ):
            with self.assertRaises((ProposalValidationError, TypeError)):
                validate_policy(bad)


if __name__ == "__main__":
    unittest.main()
