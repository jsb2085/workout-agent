from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from typing import Any

from app import db as db_module
from app.schemas.weekly_plan import WeeklyPlan
from app.services import notion, records, weekly_plan as weekly_plan_service


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workout", description="Workout agent CLI")
    sub = parser.add_subparsers(dest="group", required=True)

    notion_parser = sub.add_parser("notion", help="Publish weekly workouts to Notion")
    notion_sub = notion_parser.add_subparsers(dest="command", required=True)

    publish_week = notion_sub.add_parser(
        "publish-week",
        help="Build this week's plan from saved workouts and send it to the Notion template",
    )
    publish_week.add_argument("--email", help="Workout-app user email")
    publish_week.add_argument("--user-id", help="Workout-app user id")
    publish_week.add_argument("--week-start", help="Monday (YYYY-MM-DD). Defaults to this week's Monday.")
    publish_week.add_argument("--week-end", help="Inclusive end date (YYYY-MM-DD). Defaults to Sunday.")
    publish_week.add_argument("--focus", help="Week focus shown in the Notion callout")
    publish_week.add_argument("--notes", help="Notes at the top of the page")
    publish_week.add_argument("--title", help="Override the Notion page title")
    publish_week.add_argument("--no-videos", action="store_true", help="Skip ExerciseDB demo media")
    publish_week.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Notion page payload without creating it",
    )

    publish = notion_sub.add_parser(
        "publish",
        help="Publish an agent-authored weekly plan JSON file to Notion",
    )
    publish.add_argument("--plan", required=True, help="Path to a WeeklyPlan JSON file")
    publish.add_argument("--dry-run", action="store_true")
    publish.add_argument("--no-videos", action="store_true")

    sync = notion_sub.add_parser(
        "sync",
        help="Pull Actual weight / completed from Workout Lifts into the agent",
    )
    sync.add_argument("--email", help="Workout-app user email")
    sync.add_argument("--user-id", help="Workout-app user id")
    sync.add_argument("--week-start", help="Only sync this week (YYYY-MM-DD)")
    sync.add_argument("--dry-run", action="store_true")

    recent = notion_sub.add_parser(
        "recent",
        help="Show the latest actual weight per lift for next-week planning",
    )
    recent.add_argument("--email", help="Workout-app user email")
    recent.add_argument("--user-id", help="Workout-app user id")
    return parser


async def _publish_week(args: argparse.Namespace) -> dict[str, Any]:
    if not args.email and not args.user_id:
        raise SystemExit("Provide --email and/or --user-id")
    week_start = weekly_plan_service.parse_week_start(args.week_start)
    week_end = date.fromisoformat(args.week_end) if args.week_end else None
    async with db_module.SessionLocal() as session:
        user = await records.resolve_user(session, email=args.email, user_id=args.user_id)
        plan = await weekly_plan_service.assemble_weekly_plan(
            session,
            user,
            week_start=week_start,
            week_end=week_end,
            focus=args.focus,
            notes=args.notes,
            include_videos=not args.no_videos,
            title=args.title,
        )
    return await notion.publish_weekly_plan(plan, dry_run=args.dry_run)


async def _publish_plan(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(open(args.plan, encoding="utf-8").read())
    plan = WeeklyPlan.model_validate(raw)
    if not args.no_videos:
        plan = await weekly_plan_service.attach_videos(plan)
    return await notion.publish_weekly_plan(plan, dry_run=args.dry_run)


async def _sync(args: argparse.Namespace) -> dict[str, Any]:
    if not args.email and not args.user_id:
        raise SystemExit("Provide --email and/or --user-id")
    async with db_module.SessionLocal() as session:
        user = await records.resolve_user(session, email=args.email, user_id=args.user_id)
        return await notion.sync_lifts_from_notion(
            session,
            user,
            week_start=args.week_start,
            dry_run=args.dry_run,
        )


async def _recent(args: argparse.Namespace) -> dict[str, Any]:
    if not args.email and not args.user_id:
        raise SystemExit("Provide --email and/or --user-id")
    async with db_module.SessionLocal() as session:
        user = await records.resolve_user(session, email=args.email, user_id=args.user_id)
        rows = await weekly_plan_service.recent_lift_performance(session, user)
    return {"lifts": rows}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.group == "notion" and args.command == "publish-week":
        result = asyncio.run(_publish_week(args))
    elif args.group == "notion" and args.command == "publish":
        result = asyncio.run(_publish_plan(args))
    elif args.group == "notion" and args.command == "sync":
        result = asyncio.run(_sync(args))
    elif args.group == "notion" and args.command == "recent":
        result = asyncio.run(_recent(args))
    else:
        raise SystemExit("Unknown command")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
