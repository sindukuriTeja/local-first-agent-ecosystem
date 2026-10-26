"""Command-line interface for the platform.

Run from the project root:

    python -m agent_platform.cli ask --user admin "What is the status of matter X?"
    python -m agent_platform.cli ingest --user admin --file path/to/doc.pdf
    python -m agent_platform.cli approvals
    python -m agent_platform.cli approve --id <approval_id> --user reviewer --decision approved
    python -m agent_platform.cli audit --actor agent_7_drafting
    python -m agent_platform.cli agents
    python -m agent_platform.cli models
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .platform import create_platform


def _print_result(result) -> None:
    print(f"\n=== {result.agent_id} [{result.status}] ({result.latency_ms} ms) ===")
    if result.answer:
        print(result.answer)
    if result.sources:
        print("\nSources:")
        for s in result.sources:
            print(f"  - {s}")
    if result.approval_id:
        print(f"\nApproval required: {result.approval_id}")
    if result.error:
        print(f"\nError: {result.error}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-platform",
        description="Local-First Agent Ecosystem — Phase 1+2 CLI",
    )
    parser.add_argument("--config", default=None, help="path to settings.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ask
    p_ask = sub.add_parser("ask", help="route a request through the Orchestrator")
    p_ask.add_argument("--user", required=True)
    p_ask.add_argument("request")
    p_ask.add_argument("--tenant", default="default")

    # ingest
    p_ing = sub.add_parser("ingest", help="ingest a document via Agent 4")
    p_ing.add_argument("--user", required=True)
    p_ing.add_argument("--file", required=True)
    p_ing.add_argument("--sensitivity", default="internal")
    p_ing.add_argument("--tenant", default="default")

    # agents
    sub.add_parser("agents", help="list all agents")

    # models
    sub.add_parser("models", help="list Ollama models")

    # approvals
    p_ap = sub.add_parser("approvals", help="list pending approvals")
    p_ap.add_argument("--kind", default=None)

    # approve
    p_appr = sub.add_parser("approve", help="decide an approval")
    p_appr.add_argument("--id", required=True)
    p_appr.add_argument("--user", required=True)
    p_appr.add_argument("--decision", required=True,
                        choices=["approved", "rejected", "corrected"])
    p_appr.add_argument("--note", default="")

    # audit
    p_audit = sub.add_parser("audit", help="query the audit log")
    p_audit.add_argument("--actor", default=None)
    p_audit.add_argument("--action", default=None)
    p_audit.add_argument("--user", default=None)
    p_audit.add_argument("--limit", type=int, default=50)

    # learn (Phase 2: self-learning)
    sub.add_parser("learn", help="run one budgeted self-learning pass")
    sub.add_parser("learning", help="show the self-learning dashboard")

    # reviewer (Phase 2: web UI)
    p_rev = sub.add_parser("reviewer", help="open the reviewer web UI")
    p_rev.add_argument("--port", type=int, default=8000)
    p_rev.add_argument("--open", action="store_true",
                       help="open the browser after starting")

    args = parser.parse_args(argv)

    # The `reviewer` command starts the web server (which builds the
    # platform lazily), so it is dispatched before the CLI builds its own
    # platform instance. (Previously this subcommand was dead code — main()
    # never routed to it, so `cli reviewer` silently exited.)
    if args.cmd == "reviewer":
        return _run_reviewer(args)

    platform = create_platform(config_path=args.config)

    try:
        if args.cmd == "ask":
            result = platform.handle_request(args.user, args.request, args.tenant)
            _print_result(result)
            return 0 if result.ok or result.status == "needs_approval" else 1

        if args.cmd == "ingest":
            if not os.path.isfile(args.file):
                print(f"File not found: {args.file}", file=sys.stderr)
                return 2
            result = platform.run_agent(
                "agent_4_document_intake_ocr", args.user,
                f"Ingest document {os.path.basename(args.file)}",
                args.tenant, state={"files": [args.file],
                                    "sensitivity": args.sensitivity},
            )
            _print_result(result)
            return 0 if result.ok else 1

        if args.cmd == "agents":
            for aid, agent in platform.agents.items():
                print(f"{aid:40s} {agent.name}")
            return 0

        if args.cmd == "models":
            models = platform.services.ollama.list_models()
            if not models:
                print("No Ollama models found. Is Ollama running? "
                      "Try: ollama pull llama3.1:8b")
                return 1
            for m in models:
                print(m)
            return 0

        if args.cmd == "approvals":
            pending = platform.pending_approvals(args.kind)
            if not pending:
                print("No pending approvals.")
                return 0
            for a in pending:
                print(f"{a.id}  [{a.kind}]  {a.title}  (by {a.requested_by})")
            return 0

        if args.cmd == "approve":
            try:
                decision = platform.decide_approval(
                    args.id, args.decision, args.user, args.note
                )
            except PermissionError as e:
                print(f"Permission denied: {e}", file=sys.stderr)
                return 1
            if decision is None:
                print(f"Approval {args.id} not found.", file=sys.stderr)
                return 1
            print(f"Approval {args.id} -> {decision.status} (by {args.user})")
            return 0

        if args.cmd == "audit":
            entries = platform.audit_query(args.actor, args.action, args.user,
                                           args.limit)
            for e in entries:
                print(json.dumps(e, ensure_ascii=False))
            return 0

        if args.cmd == "learn":
            report = platform.learn()
            if "error" in report:
                print(f"Learning: {report['error']}", file=sys.stderr)
                return 1
            print(f"\n=== Learning run {report['run_id']} ===")
            print(f"  trajectories processed : {report['trajectories_processed']}")
            print(f"  candidates mined       : {report['candidates_mined']}")
            print(f"  verified passed        : {report['verified_passed']}")
            print(f"  regression passed      : {report['regression_passed']}")
            print(f"  promoted               : {report['promoted']}")
            print(f"  rejected               : {report['rejected']}")
            print(f"  budget used            : {report['budget_used']}/{report['budget_limit']}")
            print(f"  hold-out accuracy      : {report['holdout_accuracy']:.2%}")
            for n in report["notes"]:
                print(f"  · {n}")
            return 0

        if args.cmd == "learning":
            dash = platform.learning_dashboard()
            if "error" in dash:
                print(f"Learning: {dash['error']}", file=sys.stderr)
                return 1
            print(json.dumps(dash, indent=2, ensure_ascii=False))
            return 0

        return 0
    finally:
        platform.close()


def _run_reviewer(args) -> int:
    """Start the FastAPI server and (optionally) open the reviewer UI."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required: pip install fastapi uvicorn python-multipart",
              file=sys.stderr)
        return 2
    # Honour --config by pointing the server's lazy platform at it.
    if getattr(args, "config", None):
        os.environ["LFAE_CONFIG"] = args.config
    url = f"http://127.0.0.1:{args.port}/reviewer"
    print(f"Starting reviewer console at {url}  (Ctrl-C to stop)")
    if args.open:
        import threading
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    # Pass the real FastAPI app (not the module-level lazy proxy): uvicorn
    # detects ASGI2 vs ASGI3 by calling the app with just `scope`, and the
    # proxy's __call__ is not an async callable, so uvicorn would wrap it
    # as ASGI2 and every request would 500.
    from .server import get_app
    uvicorn.run(get_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())