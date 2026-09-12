"""Command line for the local Codex Team controller."""
import argparse
import json
from pathlib import Path
import sys
import time

from .engine import Engine


def main(argv=None):
    parser=argparse.ArgumentParser(prog='python -m team_runtime')
    parser.add_argument('--state',required=True,help='Controller state directory outside the product repository')
    sub=parser.add_subparsers(dest='command',required=True)
    proposal=sub.add_parser('propose',help='Clarify a natural language goal and prepare a real model-generated plan')
    proposal.add_argument('--repo',required=True)
    proposal.add_argument('--brief-file',type=Path,required=True)
    proposal.add_argument('--answers-file',type=Path)
    proposal.add_argument('--policy-file',type=Path)
    approve=sub.add_parser('approve',help='Authorize the reviewed exact proposal')
    approve.add_argument('plan_id');approve.add_argument('--digest',required=True)
    for name in ('run','resume','pause','cancel','snapshot','watch'):
        item=sub.add_parser(name);item.add_argument('run_id',nargs='?' if name=='snapshot' else None)
    steer=sub.add_parser('steer');steer.add_argument('run_id');steer.add_argument('package_id');steer.add_argument('message')
    request=sub.add_parser('request');request.add_argument('run_id');request.add_argument('from_package');request.add_argument('to_package');request.add_argument('question')
    answer=sub.add_parser('answer');answer.add_argument('run_id');answer.add_argument('request_id');answer.add_argument('answer')
    accept=sub.add_parser('accept');accept.add_argument('run_id');accept.add_argument('--digest',required=True)
    notes=sub.add_parser('notes',help='Read current working notes with links to original evidence')
    notes.add_argument('run_id');notes.add_argument('package_id')
    history=sub.add_parser('history',help='Search append-only run history')
    history.add_argument('run_id');history.add_argument('query');history.add_argument('--package')
    history.add_argument('--limit',type=int,default=20)
    limits=sub.add_parser('limits',help='Authorize a versioned resource amendment for a stopped run')
    limits.add_argument('run_id');limits.add_argument('--digest',required=True);limits.add_argument('--policy-file',type=Path,required=True)
    supervise=sub.add_parser('supervise',help='Independently review direction at a stopped checkpoint')
    supervise.add_argument('run_id')
    reconciliation=sub.add_parser('reconcile',help='Recover a stale controller state from native observations and exact source')
    reconciliation.add_argument('run_id')
    qualification=sub.add_parser('requalify',help='Recheck an updated interpreter while preserving its old evidence')
    qualification.add_argument('run_id')
    replacement=sub.add_parser('replace-session',help='Transfer a stopped package using notes and original history')
    replacement.add_argument('run_id');replacement.add_argument('package_id');replacement.add_argument('--reason',required=True)
    server=sub.add_parser('serve');server.add_argument('--port',type=int,default=8765)
    args=parser.parse_args(argv)
    engine=Engine(args.state)
    def emit(value): print(json.dumps(value,ensure_ascii=False,indent=2),flush=True)
    def read(path): return json.loads(path.read_text(encoding='utf-8')) if path else None
    try:
        if args.command=='serve':
            from .board import serve
            serve(engine,port=args.port);return 0
        if args.command=='propose':
            emit(engine.propose(args.repo,args.brief_file.read_text(encoding='utf-8'),
                answers=read(args.answers_file),policy=read(args.policy_file)))
        elif args.command=='approve':emit(engine.approve(args.plan_id,args.digest))
        elif args.command=='snapshot':emit(engine.snapshot(args.run_id))
        elif args.command=='steer':emit(engine.steer(args.run_id,args.package_id,args.message))
        elif args.command=='request':emit(engine.request_collaboration(args.run_id,args.from_package,args.to_package,args.question))
        elif args.command=='answer':emit(engine.resolve_request(args.run_id,args.request_id,args.answer))
        elif args.command=='accept':emit(engine.accept_checkpoint(args.run_id,args.digest))
        elif args.command=='notes':emit(engine.get_note(args.run_id,args.package_id))
        elif args.command=='history':emit(engine.search_history(args.run_id,args.query,package_id=args.package,limit=args.limit))
        elif args.command=='limits':emit(engine.amend_limits(args.run_id,read(args.policy_file),args.digest))
        elif args.command=='supervise':emit(engine.supervise(args.run_id))
        elif args.command=='reconcile':emit(engine.reconcile(args.run_id))
        elif args.command=='requalify':emit(engine.requalify(args.run_id))
        elif args.command=='replace-session':emit(engine.replace_session(args.run_id,args.package_id,args.reason))
        elif args.command in {'run','resume','watch'}:
            if args.command=='run':emit(engine.start(args.run_id))
            elif args.command=='resume':emit(engine.resume(args.run_id))
            cursor=0
            while True:
                for event in engine.store.events(args.run_id,after=cursor):
                    emit(event);cursor=event['seq']
                record=engine.store.get('run',args.run_id)
                if not record:raise ValueError('Unknown run')
                if record['data']['status'] in {'completed','awaiting-user','blocked','paused','cancelled'}:
                    emit(record)
                    return 0 if record['data']['status'] in {'completed','awaiting-user'} else 2
                time.sleep(1)
        else:emit(getattr(engine,args.command)(args.run_id))
        return 0
    except KeyboardInterrupt:
        if hasattr(args,'run_id') and args.run_id:
            emit(engine.pause(args.run_id))
        return 130
    except Exception as exc:
        emit({'error':str(exc),'status':'failed'})
        return 1


if __name__=='__main__':
    sys.exit(main())
