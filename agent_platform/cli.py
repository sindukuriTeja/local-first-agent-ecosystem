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
        description="Local-First Agent Ecosystem — Phase 1 CLI",
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

    args = parser.parse_args(argv)

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

        return 0
    finally:
        platform.close()


if __name__ == "__main__":
    raise SystemExit(main())