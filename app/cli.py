"""Command-line interface for running the pipeline without the web UI.

Examples:
    python -m app.cli run --topic "ELSS vs PPF for tax saving"
    python -m app.cli review
    python -m app.cli approve 3
    python -m app.cli publish 3
    python -m app.cli analytics 1
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from .db import init_db, session_scope
from .models import ContentItem, ItemStatus, PipelineRun
from .orchestrator import Orchestrator


def _run(args: argparse.Namespace) -> None:
    orch = Orchestrator()
    run_id = orch.run_cycle(topic=args.topic, items_per_run=args.count)
    with session_scope() as session:
        run = session.get(PipelineRun, run_id)
        print(f"\n✅ Cycle #{run_id} — status: {run.status.value}")
        print(f"   Focus: {(run.research or {}).get('recommended_focus', '')}\n")
        for item in run.items:
            v = item.verification or {}
            print(f"  [{item.id}] {item.platform:10s} {item.status.value:15s} "
                  f"score={v.get('score','—')}  {item.title}")
    print("\nReview items in the dashboard, or: python -m app.cli approve <id>")


def _review(_: argparse.Namespace) -> None:
    with session_scope() as session:
        items = session.scalars(
            select(ContentItem).where(ContentItem.status == ItemStatus.PENDING_REVIEW)
        ).all()
        if not items:
            print("Nothing awaiting review.")
            return
        print("Awaiting review:")
        for item in items:
            print(f"  [{item.id}] {item.platform:10s} {item.title}")


def _approve(args: argparse.Namespace) -> None:
    Orchestrator().approve(args.item_id, args.note)
    print(f"✓ Approved item {args.item_id}")


def _reject(args: argparse.Namespace) -> None:
    Orchestrator().reject(args.item_id, args.note)
    print(f"✗ Rejected item {args.item_id}")


def _publish(args: argparse.Namespace) -> None:
    ref = Orchestrator().publish_item(args.item_id)
    print(f"🚀 Published item {args.item_id} → {ref}")


def _analytics(args: argparse.Namespace) -> None:
    insight = Orchestrator().collect_analytics(args.run_id)
    print(f"\n📊 {insight.headline}\n")
    print("Recommendations:")
    for rec in insight.recommendations:
        print(f"  • {rec}")
    print("\nNext topic ideas:")
    for topic in insight.next_topic_suggestions:
        print(f"  • {topic}")


def main() -> None:
    init_db()
    parser = argparse.ArgumentParser(prog="byf", description="BYF marketing pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run a full pipeline cycle")
    p_run.add_argument("--topic", default=None, help="Seed topic (optional)")
    p_run.add_argument("--count", type=int, default=4, help="Number of content items")
    p_run.set_defaults(func=_run)

    sub.add_parser("review", help="List items awaiting review").set_defaults(func=_review)

    p_ap = sub.add_parser("approve", help="Approve an item")
    p_ap.add_argument("item_id", type=int)
    p_ap.add_argument("--note", default=None)
    p_ap.set_defaults(func=_approve)

    p_rj = sub.add_parser("reject", help="Reject an item")
    p_rj.add_argument("item_id", type=int)
    p_rj.add_argument("--note", default=None)
    p_rj.set_defaults(func=_reject)

    p_pub = sub.add_parser("publish", help="Publish an approved item")
    p_pub.add_argument("item_id", type=int)
    p_pub.set_defaults(func=_publish)

    p_an = sub.add_parser("analytics", help="Collect analytics for a run")
    p_an.add_argument("run_id", type=int)
    p_an.set_defaults(func=_analytics)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
