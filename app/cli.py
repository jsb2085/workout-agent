from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from app.schemas.weekly_plan import WeeklyPlan
from app.services import notion, weekly_plan as weekly_plan_service


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workout", description="Notion-backed workout agent CLI")
    sub = parser.add_subparsers(dest="group", required=True)
    notion_parser = sub.add_parser("notion", help="Read and publish Notion workout data")
    notion_sub = notion_parser.add_subparsers(dest="command", required=True)

    publish_week = notion_sub.add_parser("publish-week", help="Build this week's page from Notion lift rows")
    publish_week.add_argument("--athlete")
    publish_week.add_argument("--week-start")
    publish_week.add_argument("--week-end")
    publish_week.add_argument("--focus")
    publish_week.add_argument("--notes")
    publish_week.add_argument("--title")
    publish_week.add_argument("--no-videos", action="store_true")
    publish_week.add_argument("--dry-run", action="store_true")

    publish = notion_sub.add_parser("publish", help="Publish a WeeklyPlan JSON file")
    publish.add_argument("--plan", required=True)
    publish.add_argument("--dry-run", action="store_true")
    publish.add_argument("--no-videos", action="store_true")

    recent = notion_sub.add_parser("recent", help="Latest actual/goal weight per lift")
    recent.add_argument("--athlete")

    lifts = notion_sub.add_parser("lifts", help="List Notion lift rows")
    lifts.add_argument("--athlete")
    lifts.add_argument("--date-from")
    lifts.add_argument("--date-to")
    return parser


async def _publish_week(args: argparse.Namespace) -> dict[str, Any]:
    who = notion._require_athlete(args.athlete)
    start = weekly_plan_service.parse_week_start(args.week_start)
    end = weekly_plan_service.week_end_for(start, args.week_end)
    plan = await weekly_plan_service.assemble_weekly_plan(
        athlete=who,
        week_start=start,
        week_end=end,
        focus=args.focus,
        notes=args.notes,
        title=args.title,
        include_videos=not args.no_videos,
    )
    return await notion.publish_weekly_plan(plan, dry_run=args.dry_run)


async def _publish_plan(args: argparse.Namespace) -> dict[str, Any]:
    plan = WeeklyPlan.model_validate(json.loads(open(args.plan, encoding="utf-8").read()))
    if not args.no_videos:
        plan = await weekly_plan_service.attach_videos(plan)
    return await notion.publish_weekly_plan(plan, dry_run=args.dry_run)


async def _recent(args: argparse.Namespace) -> dict[str, Any]:
    return {"lifts": await notion.NotionStore().recent_performance(args.athlete)}


async def _lifts(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "lifts": await notion.NotionStore().list_lifts(
            athlete=args.athlete,
            date_from=args.date_from,
            date_to=args.date_to,
        )
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    commands = {
        "publish-week": _publish_week,
        "publish": _publish_plan,
        "recent": _recent,
        "lifts": _lifts,
    }
    if args.group != "notion" or args.command not in commands:
        raise SystemExit("Unknown command")
    result = asyncio.run(commands[args.command](args))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
