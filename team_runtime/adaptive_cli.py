"""Adaptive Team CLI. Conversation stays in Codex; this owns durable actions."""
import argparse
import json
from pathlib import Path
import sys

from .adaptive import Adaptive


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="team-next")
    parser.add_argument("--state", required=True, help="Persistent Team state outside the product workspace")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Register the understood goal, reviewed plan and existing authority")
    create.add_argument("--workspace", required=True)
    create.add_argument("--definition-file", type=Path, required=True)
    create.add_argument("--plan-file", type=Path, required=True, help="JSON list of initial work items; may be empty for investigation")
    create.add_argument("--authority-file", type=Path, required=True)
    create.add_argument("--policy-file", type=Path)
    create.add_argument("--operation-id", required=True, help="Stable ID for retries of this create request")
    create.add_argument("--title", default="Team项目")
    for name in ("run", "snapshot", "pause", "cancel", "reconcile"):
        item = commands.add_parser(name)
        item.add_argument("run_id")
    commands.add_parser("list")
    history = commands.add_parser("history")
    history.add_argument("run_id")
    history.add_argument("query")
    history.add_argument("--after", type=int, default=0)
    history.add_argument("--limit", type=int, default=20)
    message = commands.add_parser("message", help="Record a user message without bypassing the work queue")
    message.add_argument("run_id")
    message.add_argument("--file", type=Path, required=True)
    message.add_argument("--operation-id", required=True)
    revise = commands.add_parser("revise")
    revise.add_argument("run_id")
    revise.add_argument("--changes-file", type=Path, required=True)
    revise.add_argument("--operation-id", required=True)
    limits = commands.add_parser("limits")
    limits.add_argument("run_id")
    limits.add_argument("--policy-file", type=Path, required=True)
    limits.add_argument("--reason", required=True)
    limits.add_argument("--operation-id", required=True)
    accept = commands.add_parser("accept")
    accept.add_argument("run_id")
    accept.add_argument("work_id")
    accept.add_argument("--result-hash", required=True)
    accept.add_argument("--reason", required=True)
    accept.add_argument("--actor", choices=["operator", "user"], default="operator")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    engine = Adaptive(args.state)
    def read(path):
        return json.loads(path.read_text(encoding="utf-8-sig")) if path else None
    try:
        if args.command == "create":
            result = engine.create(args.workspace, args.definition_file.read_text(encoding="utf-8-sig"),
                read(args.plan_file), authority=args.authority_file.read_text(encoding="utf-8-sig"),
                policy=read(args.policy_file), operation_id=args.operation_id, title=args.title)
        elif args.command == "run":
            from .adaptive_runner import Runner
            result = Runner(engine, args.run_id).run()
        elif args.command == "snapshot":
            result = engine.snapshot(args.run_id)
        elif args.command == "list":
            result = {"runs": engine.store.list("adaptive-run")}
        elif args.command in {"pause", "cancel"}:
            result = engine.stop(args.run_id, "pause" if args.command == "pause" else "cancel")
        elif args.command == "reconcile":
            from .adaptive_runner import reconcile
            result = reconcile(engine, args.run_id)
        elif args.command == "history":
            result = engine.history(args.run_id, args.query, after=args.after, limit=args.limit)
        elif args.command == "message":
            result = engine.message(args.run_id, args.file.read_text(encoding="utf-8-sig"), operation_id=args.operation_id)
        elif args.command == "revise":
            result = engine.revise(args.run_id, operation_id=args.operation_id, **read(args.changes_file))
        elif args.command == "limits":
            result = engine.amend_policy(args.run_id, read(args.policy_file), args.reason, operation_id=args.operation_id)
        elif args.command == "accept":
            result = engine.accept(args.run_id, args.work_id, args.result_hash, args.reason, actor=args.actor)
        elif args.command == "serve":
            from .adaptive_board import serve
            serve(engine, args.port)
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        if args.command == "run" and result["status"] != "completed":
            return 2
        return 0
    except KeyboardInterrupt:
        if getattr(args, "run_id", None):
            result = engine.stop(args.run_id)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        return 130
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
