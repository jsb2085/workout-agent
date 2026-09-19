from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from app.graph.planner import run_week
from app.schemas.weekly_plan import WeeklyPlan
from app.services import weekly_plan as weekly_plan_service


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workout",
        description="Pull Notion, plan a week with LangGraph (gpt-5.6-luna), push it back.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pull = sub.add_parser("pull", help="Read Notion data the graph needs to plan a week")
    pull.add_argument("--week-start", help="Monday of the week to plan (default: this Monday)")
    pull.add_argument("--week-end")

    push = sub.add_parser("push", help="Write the graph's WeeklyPlan JSON back to Notion")
    push.add_argument("--plan", required=True, help="Path to plan JSON, or - for stdin")
    push.add_argument("--dry-run", action="store_true")
    push.add_argument("--no-videos", action="store_true")

    run = sub.add_parser("run", help="Pull Notion, run the planner graph, push the week")
    run.add_argument("--week-start", help="Monday of the week to plan (default: this Monday)")
    run.add_argument("--week-end")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--no-videos", action="store_true")
    run.add_argument("--no-push", action="store_true", help="Return the plan without writing Notion")
    return parser


def _read_plan(path: str) -> WeeklyPlan:
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    return WeeklyPlan.model_validate(json.loads(raw))


async def _pull(args: argparse.Namespace) -> dict[str, Any]:
    start = weekly_plan_service.parse_week_start(args.week_start)
    end = weekly_plan_service.week_end_for(start, args.week_end)
    context = await weekly_plan_service.pull_context(week_start=start, week_end=end)
    return context.model_dump(mode="json")


async def _push(args: argparse.Namespace) -> dict[str, Any]:
    plan = _read_plan(args.plan)
    return await weekly_plan_service.push_plan(
        plan,
        dry_run=args.dry_run,
        include_videos=not args.no_videos,
    )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    return await run_week(
        week_start=args.week_start,
        week_end=args.week_end,
        dry_run=args.dry_run,
        include_videos=not args.no_videos,
        push=not args.no_push,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    commands = {"pull": _pull, "push": _push, "run": _run}
    result = asyncio.run(commands[args.command](args))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
