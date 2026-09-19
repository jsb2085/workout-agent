from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.weekly_plan import PlannedCardio, PlannedDay, PlannedLift, WeeklyPlan

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_TEMPLATE_VERSION = "2026-03-11"
CHILDREN_PAGE_SIZE = 100

TITLE_ALIASES = ("Name", "Title", "Week name")
WEEK_ALIASES = ("Week", "Week of", "Dates", "Date")
STATUS_ALIASES = ("Status",)
FOCUS_ALIASES = ("Focus", "Goal")
ATHLETE_ALIASES = ("Athlete", "Person", "Who")


class NotionError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _rich(content: str, *, bold: bool = False, italic: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": {"content": (content or "")[:2000]},
            "annotations": {"bold": bold, "italic": italic},
        }
    ]


def _paragraph(content: str, *, italic: bool = False) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich(content, italic=italic)}}


def _heading(content: str, level: int = 2) -> dict[str, Any]:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": _rich(content, bold=True)}}


def _callout(content: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {"rich_text": _rich(content), "icon": {"type": "emoji", "emoji": "🎯"}},
    }


def _todo(content: str, *, checked: bool = False) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": _rich(content), "checked": checked},
    }


def _media_block(url: str, media_kind: str | None) -> dict[str, Any]:
    if media_kind == "video" or (url or "").endswith(".mp4"):
        return {"object": "block", "type": "video", "video": {"type": "external", "external": {"url": url}}}
    if media_kind == "gif" or (url or "").endswith(".gif"):
        return {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": url}}}
    return {"object": "block", "type": "bookmark", "bookmark": {"url": url}}


def _lift_label(lift: PlannedLift) -> str:
    parts = [lift.lift]
    details: list[str] = []
    if lift.sets:
        details.append(f"{lift.sets}x")
    if lift.reps is not None:
        details.append(f"{lift.reps} reps")
    if lift.goal_weight:
        details.append(f"@ {lift.goal_weight}")
    if details:
        parts.append("— " + " ".join(details))
    if lift.exercise_name and lift.exercise_name.casefold() != lift.lift.casefold():
        parts.append(f"({lift.exercise_name})")
    return " ".join(parts)


def _cardio_label(item: PlannedCardio) -> str:
    parts = [item.kind.title()]
    if item.distance:
        parts.append(item.distance)
    if item.reps:
        parts.append(f"{item.reps} reps")
    return " ".join(parts)


def _day_blocks(day: PlannedDay) -> list[dict[str, Any]]:
    heading = f"{day.date.strftime('%A')} {day.date.day}"
    if day.focus:
        heading = f"{heading} — {day.focus}"
    blocks: list[dict[str, Any]] = [_heading(heading, 2)]
    if not day.lifts and not day.cardio:
        blocks.append(_paragraph("Rest / no sessions planned", italic=True))
    for lift in day.lifts:
        blocks.append(_todo(_lift_label(lift), checked=lift.completed))
        if lift.demo_url:
            blocks.append(_media_block(lift.demo_url, lift.media_kind))
        if lift.notes:
            blocks.append(_paragraph(lift.notes, italic=True))
    for cardio in day.cardio:
        blocks.append(_todo(_cardio_label(cardio), checked=cardio.completed))
    extras: list[str] = []
    if day.protein_goal is not None:
        extras.append(f"Protein {day.protein_goal}g")
    if day.steps_goal is not None:
        extras.append(f"Steps {day.steps_goal:,}")
    if extras:
        blocks.append(_paragraph(" · ".join(extras)))
    if day.notes:
        blocks.append(_paragraph(day.notes))
    return blocks


def build_page_children(plan: WeeklyPlan) -> list[dict[str, Any]]:
    """Designed weekly-workout template body: goal, checkable lifts, demo media."""
    blocks: list[dict[str, Any]] = [_heading(plan.title, 1)]
    if plan.focus:
        blocks.append(_callout(plan.focus))
    if plan.notes:
        blocks.append(_paragraph(plan.notes))
    blocks.append(
        _paragraph(
            "Check off lifts as you go. Demo media is from ExerciseDB — tap to play.",
            italic=True,
        )
    )
    for day in plan.days:
        blocks.extend(_day_blocks(day))
    return blocks


def _find_property(schema: dict[str, Any], aliases: tuple[str, ...], *types: str) -> str | None:
    properties = schema.get("properties") or {}
    by_name = {name.casefold(): (name, prop) for name, prop in properties.items()}
    for alias in aliases:
        match = by_name.get(alias.casefold())
        if match and (not types or match[1].get("type") in types):
            return match[0]
    if types:
        for name, prop in properties.items():
            if prop.get("type") in types:
                return name
    return None


def build_page_properties(plan: WeeklyPlan, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or {"properties": {"Name": {"type": "title"}}}
    properties: dict[str, Any] = {}
    title_name = _find_property(schema, TITLE_ALIASES, "title") or "Name"
    properties[title_name] = {"title": [{"type": "text", "text": {"content": plan.title[:2000]}}]}

    week_name = _find_property(schema, WEEK_ALIASES, "date")
    if week_name:
        properties[week_name] = {
            "date": {"start": plan.week_start.isoformat(), "end": plan.week_end.isoformat()}
        }
    status_name = _find_property(schema, STATUS_ALIASES, "select", "status")
    if status_name:
        status_type = (schema.get("properties") or {}).get(status_name, {}).get("type", "select")
        properties[status_name] = {status_type: {"name": "Planned"}}
    focus_name = _find_property(schema, FOCUS_ALIASES, "rich_text")
    if focus_name and plan.focus:
        properties[focus_name] = {"rich_text": _rich(plan.focus)}
    athlete_name = _find_property(schema, ATHLETE_ALIASES, "rich_text")
    if athlete_name and plan.athlete:
        properties[athlete_name] = {"rich_text": _rich(plan.athlete)}
    return properties


def page_url(page: dict[str, Any]) -> str:
    return str(page.get("url") or "")


class NotionClient:
    def __init__(self, *, token: str | None = None, version: str | None = None):
        settings = get_settings()
        self.token = token if token is not None else settings.notion_token
        self.version = version or settings.notion_version or NOTION_VERSION
        self.timeout = settings.notion_timeout_seconds

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise NotionError(
                "NOTION_TOKEN is not set. Create an integration at https://www.notion.so/my-integrations "
                "and share the Weekly Workouts database with it.",
                400,
            )
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.version,
            "Content-Type": "application/json",
        }

    async def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{NOTION_API}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise NotionError("Notion request timed out", 504) from exc
        except httpx.HTTPError as exc:
            raise NotionError("Notion request failed", 502) from exc
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400:
            message = "Notion request failed"
            if isinstance(body, dict):
                message = str(body.get("message") or body.get("code") or message)
            raise NotionError(message, 502 if response.status_code >= 500 else response.status_code)
        return body

    async def retrieve_database(self, database_id: str) -> dict[str, Any]:
        return await self.request("GET", f"/databases/{database_id}")

    async def create_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/pages", payload)

    async def append_children(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.request("PATCH", f"/blocks/{block_id}/children", {"children": children})

    async def list_children(self, block_id: str) -> list[dict[str, Any]]:
        body = await self.request("GET", f"/blocks/{block_id}/children?page_size=10")
        return list((body or {}).get("results") or [])


def _chunk(items: list[dict[str, Any]], size: int = CHILDREN_PAGE_SIZE) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


async def publish_weekly_plan(
    plan: WeeklyPlan,
    *,
    dry_run: bool = False,
    client: NotionClient | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    children = build_page_children(plan)
    schema: dict[str, Any] | None = None
    notion = client or NotionClient()
    if not dry_run:
        if not settings.notion_database_id:
            raise NotionError(
                "NOTION_DATABASE_ID is not set. Create a Weekly Workouts database and share it with the integration.",
                400,
            )
        try:
            schema = await notion.retrieve_database(settings.notion_database_id)
        except NotionError:
            schema = None
    properties = build_page_properties(plan, schema)
    preview = {
        "parent": {"database_id": settings.notion_database_id or "<NOTION_DATABASE_ID>"},
        "properties": properties,
        "children": children,
        "title": plan.title,
    }
    if dry_run:
        return {"dry_run": True, "url": None, "page_id": None, **preview}

    create_payload: dict[str, Any] = {
        "parent": {"database_id": settings.notion_database_id},
        "properties": properties,
    }
    template_id = settings.notion_template_id
    if template_id:
        create_payload["template"] = {"type": "template_id", "template_id": template_id}
        if settings.notion_data_source_id:
            create_payload["parent"] = {
                "type": "data_source_id",
                "data_source_id": settings.notion_data_source_id,
            }
        notion.version = settings.notion_version or NOTION_TEMPLATE_VERSION
    else:
        first, rest = (children[:CHILDREN_PAGE_SIZE], children[CHILDREN_PAGE_SIZE:])
        create_payload["children"] = first
        rest_chunks = _chunk(rest)
        page = await notion.create_page(create_payload)
        for extra in rest_chunks:
            await notion.append_children(page["id"], extra)
        return {
            "dry_run": False,
            "url": page_url(page),
            "page_id": page.get("id"),
            "title": plan.title,
            "week_start": plan.week_start.isoformat(),
            "week_end": plan.week_end.isoformat(),
        }

    page = await notion.create_page(create_payload)
    await _wait_for_template(notion, page["id"])
    for extra in _chunk(children):
        await notion.append_children(page["id"], extra)
    return {
        "dry_run": False,
        "url": page_url(page),
        "page_id": page.get("id"),
        "title": plan.title,
        "week_start": plan.week_start.isoformat(),
        "week_end": plan.week_end.isoformat(),
        "used_template": True,
    }


async def _wait_for_template(notion: NotionClient, page_id: str, *, attempts: int = 20) -> None:
    for _ in range(attempts):
        try:
            children = await notion.list_children(page_id)
        except NotionError:
            children = []
        if children:
            return
        await asyncio.sleep(0.4)
