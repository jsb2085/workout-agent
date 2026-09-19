from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.weekly_plan import PlannedCardio, PlannedDay, PlannedLift, WeeklyPlan

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_TEMPLATE_VERSION = "2026-03-11"
CHILDREN_PAGE_SIZE = 100

TITLE_ALIASES = ("Name", "Title", "Week name", "Lift", "Exercise")
WEEK_ALIASES = ("Week", "Week of", "Dates")
STATUS_ALIASES = ("Status",)
FOCUS_ALIASES = ("Focus", "Goal")
LIFT_DATE_ALIASES = ("Date",)
GOAL_WEIGHT_ALIASES = ("Goal weight", "Goal", "Planned weight")
ACTUAL_WEIGHT_ALIASES = ("Actual weight", "Actual", "Weight")
REPS_ALIASES = ("Reps",)
COMPLETED_ALIASES = ("Completed", "Done")
WEEK_START_ALIASES = ("Week start",)
DISTANCE_ALIASES = ("Distance",)
CARDIO_KIND_ALIASES = ("Cardio", "Cardio kind")
PROTEIN_GOAL_ALIASES = ("Protein goal",)
PROTEIN_ACTUAL_ALIASES = ("Protein actual",)
STEPS_GOAL_ALIASES = ("Steps goal",)
STEPS_ACTUAL_ALIASES = ("Steps actual",)
SPRINT_ALIASES = ("Sprint",)
RUN_ALIASES = ("Run",)
WALK_ALIASES = ("Walk",)
CARDIO_REPS_ALIASES = ("Cardio reps",)
CARDIO_DONE_ALIASES = ("Cardio completed",)
DESCRIPTION_ALIASES = ("Description", "Notes", "Details")
TARGET_ALIASES = ("Target", "Target value")
METRIC_ALIASES = ("Metric", "Lift", "Category")
DEADLINE_ALIASES = ("Deadline", "Due", "By")
GOAL_STATUS_ALIASES = ("Status",)
EQUIPMENT_ALIASES = ("Equipment", "Gear")
DEFAULT_ALIASES = ("Default", "Primary")
HEIGHT_ALIASES = ("Height",)
BODY_WEIGHT_ALIASES = ("Weight", "Body weight")
SQUAT_ALIASES = ("Squat",)
BENCH_ALIASES = ("Bench", "Bench press")
DEADLIFT_ALIASES = ("Deadlift",)
OHP_ALIASES = ("Overhead press", "OHP", "Press")


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


def _callout(content: str, *, emoji: str = "🎯", color: str = "default") -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich(content),
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    }


def _quote(content: str) -> dict[str, Any]:
    return {"object": "block", "type": "quote", "quote": {"rich_text": _rich(content, italic=True)}}


def _divider() -> dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def _bulleted(content: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich(content)},
    }


def _toggle(title: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {"rich_text": _rich(title, bold=True), "children": children},
    }


def _toc() -> dict[str, Any]:
    return {"object": "block", "type": "table_of_contents", "table_of_contents": {"color": "gray"}}


def _todo(content: str, *, checked: bool = False) -> dict[str, Any]:
    return {"object": "block", "type": "to_do", "to_do": {"rich_text": _rich(content), "checked": checked}}


def _media_block(url: str, media_kind: str | None) -> dict[str, Any]:
    if media_kind == "video" or (url or "").endswith(".mp4"):
        return {"object": "block", "type": "video", "video": {"type": "external", "external": {"url": url}}}
    if media_kind == "gif" or (url or "").endswith(".gif"):
        return {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": url}}}
    return {"object": "block", "type": "bookmark", "bookmark": {"url": url}}


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


def _plain(prop: dict[str, Any] | None) -> str | None:
    if not prop:
        return None
    kind = prop.get("type")
    if kind in {"title", "rich_text"}:
        parts = prop.get(kind) or []
        text = "".join(str(part.get("plain_text") or part.get("text", {}).get("content") or "") for part in parts)
        return text.strip() or None
    if kind == "number":
        value = prop.get("number")
        return None if value is None else str(value)
    if kind == "checkbox":
        return "true" if prop.get("checkbox") else "false"
    if kind == "date":
        return (prop.get("date") or {}).get("start")
    if kind == "select" and prop.get("select"):
        return prop["select"].get("name")
    if kind == "status" and prop.get("status"):
        return prop["status"].get("name")
    return None


def _write_value(prop_schema: dict[str, Any], value: Any) -> dict[str, Any] | None:
    kind = prop_schema.get("type")
    if value is None or value == "":
        if kind == "title":
            return {"title": []}
        if kind == "rich_text":
            return {"rich_text": []}
        if kind == "number":
            return {"number": None}
        if kind == "checkbox":
            return {"checkbox": False}
        if kind == "date":
            return {"date": None}
        if kind == "select":
            return {"select": None}
        if kind == "status":
            return {"status": None}
        return None
    if kind == "title":
        return {"title": [{"type": "text", "text": {"content": str(value)[:2000]}}]}
    if kind == "rich_text":
        return {"rich_text": _rich(str(value))}
    if kind == "number":
        try:
            return {"number": float(str(value).replace(",", ""))}
        except ValueError:
            return None
    if kind == "checkbox":
        if isinstance(value, bool):
            checked = value
        else:
            checked = str(value).lower() not in {"false", "0", "no", ""}
        return {"checkbox": checked}
    if kind == "date":
        return {"date": {"start": str(value)[:10]}}
    if kind == "select":
        return {"select": {"name": str(value)}}
    if kind == "status":
        return {"status": {"name": str(value)}}
    return None


def _prop(schema: dict[str, Any], aliases: tuple[str, ...], *types: str) -> tuple[str, dict[str, Any]] | None:
    name = _find_property(schema, aliases, *types)
    if not name:
        return None
    return name, (schema.get("properties") or {}).get(name) or {}


def _read(props: dict[str, Any], schema: dict[str, Any], aliases: tuple[str, ...], *types: str) -> str | None:
    name = _find_property(schema, aliases, *types) or _find_property({"properties": props}, aliases)
    if not name:
        return None
    return _plain(props.get(name))


def _as_bool(value: str | None) -> bool:
    return (value or "").lower() in {"true", "1", "yes"}


def _as_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


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
                "NOTION_TOKEN is not set. Create an integration and share the workout databases with it.",
                400,
            )
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.version,
            "Content-Type": "application/json",
        }

    async def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method, f"{NOTION_API}{path}", headers=self._headers(), json=payload
                )
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

    async def retrieve_page(self, page_id: str) -> dict[str, Any]:
        return await self.request("GET", f"/pages/{page_id}")

    async def create_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/pages", payload)

    async def create_database(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/databases", payload)

    async def update_page(self, page_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PATCH", f"/pages/{page_id}", payload)

    async def append_children(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.request("PATCH", f"/blocks/{block_id}/children", {"children": children})

    async def list_children(self, block_id: str) -> list[dict[str, Any]]:
        body = await self.request("GET", f"/blocks/{block_id}/children?page_size=10")
        return list((body or {}).get("results") or [])

    async def query_database(self, database_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor = None
        while True:
            body = dict(payload or {})
            if cursor:
                body["start_cursor"] = cursor
            page = await self.request("POST", f"/databases/{database_id}/query", body)
            results.extend(page.get("results") or [])
            if not page.get("has_more"):
                return results
            cursor = page.get("next_cursor")

    async def search_pages(self, *, page_size: int = 10) -> list[dict[str, Any]]:
        body = await self.request(
            "POST",
            "/search",
            {
                "page_size": page_size,
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            },
        )
        return list((body or {}).get("results") or [])


def default_lift_schema() -> dict[str, Any]:
    return {
        "properties": {
            "Name": {"type": "title"},
            "Date": {"type": "date"},
            "Goal weight": {"type": "rich_text"},
            "Actual weight": {"type": "rich_text"},
            "Reps": {"type": "number"},
            "Completed": {"type": "checkbox"},
            "Week start": {"type": "date"},
        }
    }


def default_log_schema() -> dict[str, Any]:
    return {
        "properties": {
            "Name": {"type": "title"},
            "Date": {"type": "date"},
            "Sprint": {"type": "checkbox"},
            "Run": {"type": "checkbox"},
            "Walk": {"type": "checkbox"},
            "Distance": {"type": "rich_text"},
            "Cardio reps": {"type": "number"},
            "Cardio completed": {"type": "checkbox"},
            "Protein goal": {"type": "number"},
            "Protein actual": {"type": "number"},
            "Steps goal": {"type": "number"},
            "Steps actual": {"type": "number"},
        }
    }


def parse_lift_page(page: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    props = page.get("properties") or {}
    schema = schema or {"properties": {name: {"type": value.get("type")} for name, value in props.items()}}
    return {
        "id": page.get("id"),
        "url": page_url(page),
        "lift": _read(props, schema, TITLE_ALIASES, "title", "rich_text"),
        "date": (_read(props, schema, LIFT_DATE_ALIASES, "date") or "")[:10] or None,
        "goal_weight": _read(props, schema, GOAL_WEIGHT_ALIASES, "rich_text", "number"),
        "actual_weight": _read(props, schema, ACTUAL_WEIGHT_ALIASES, "rich_text", "number"),
        "reps": _as_int(_read(props, schema, REPS_ALIASES, "number", "rich_text")),
        "completed": _as_bool(_read(props, schema, COMPLETED_ALIASES, "checkbox")),
        "week_start": (_read(props, schema, WEEK_START_ALIASES, "date") or "")[:10] or None,
    }


def parse_log_page(page: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    props = page.get("properties") or {}
    schema = schema or {"properties": {name: {"type": value.get("type")} for name, value in props.items()}}
    sprint = _as_bool(_read(props, schema, SPRINT_ALIASES, "checkbox"))
    run = _as_bool(_read(props, schema, RUN_ALIASES, "checkbox"))
    walk = _as_bool(_read(props, schema, WALK_ALIASES, "checkbox"))
    kind = "sprint" if sprint else "run" if run else "walk" if walk else None
    return {
        "id": page.get("id"),
        "url": page_url(page),
        "date": (_read(props, schema, LIFT_DATE_ALIASES, "date") or "")[:10] or None,
        "sprint": sprint,
        "run": run,
        "walk": walk,
        "cardio_kind": kind,
        "distance": _read(props, schema, DISTANCE_ALIASES, "rich_text"),
        "cardio_reps": _as_int(_read(props, schema, CARDIO_REPS_ALIASES, "number", "rich_text")),
        "cardio_completed": _as_bool(_read(props, schema, CARDIO_DONE_ALIASES, "checkbox")),
        "protein_goal": _as_int(_read(props, schema, PROTEIN_GOAL_ALIASES, "number", "rich_text")),
        "protein_actual": _as_int(_read(props, schema, PROTEIN_ACTUAL_ALIASES, "number", "rich_text")),
        "steps_goal": _as_int(_read(props, schema, STEPS_GOAL_ALIASES, "number", "rich_text")),
        "steps_actual": _as_int(_read(props, schema, STEPS_ACTUAL_ALIASES, "number", "rich_text")),
    }


def _fill(
    schema: dict[str, Any],
    data: dict[str, Any],
    mapping: list[tuple[tuple[str, ...], tuple[str, ...], str]],
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for aliases, types, key in mapping:
        if key not in data:
            continue
        found = _prop(schema, aliases, *types)
        if not found:
            continue
        name, prop_schema = found
        written = _write_value(prop_schema, data.get(key))
        if written is not None:
            properties[name] = written
    return properties


def build_lift_properties(data: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or default_lift_schema()
    return _fill(
        schema,
        data,
        [
            (TITLE_ALIASES, ("title",), "lift"),
            (LIFT_DATE_ALIASES, ("date",), "date"),
            (GOAL_WEIGHT_ALIASES, ("rich_text", "number"), "goal_weight"),
            (ACTUAL_WEIGHT_ALIASES, ("rich_text", "number"), "actual_weight"),
            (REPS_ALIASES, ("number", "rich_text"), "reps"),
            (COMPLETED_ALIASES, ("checkbox",), "completed"),
            (WEEK_START_ALIASES, ("date",), "week_start"),
        ],
    )


def build_log_properties(data: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or default_log_schema()
    payload = dict(data)
    if "name" not in payload and payload.get("date"):
        payload["name"] = str(payload.get("date"))
    return _fill(
        schema,
        payload,
        [
            (TITLE_ALIASES, ("title",), "name"),
            (LIFT_DATE_ALIASES, ("date",), "date"),
            (SPRINT_ALIASES, ("checkbox",), "sprint"),
            (RUN_ALIASES, ("checkbox",), "run"),
            (WALK_ALIASES, ("checkbox",), "walk"),
            (DISTANCE_ALIASES, ("rich_text",), "distance"),
            (CARDIO_REPS_ALIASES, ("number", "rich_text"), "cardio_reps"),
            (CARDIO_DONE_ALIASES, ("checkbox",), "cardio_completed"),
            (PROTEIN_GOAL_ALIASES, ("number", "rich_text"), "protein_goal"),
            (PROTEIN_ACTUAL_ALIASES, ("number", "rich_text"), "protein_actual"),
            (STEPS_GOAL_ALIASES, ("number", "rich_text"), "steps_goal"),
            (STEPS_ACTUAL_ALIASES, ("number", "rich_text"), "steps_actual"),
        ],
    )


def default_goal_schema() -> dict[str, Any]:
    return {
        "properties": {
            "Name": {"type": "title"},
            "Description": {"type": "rich_text"},
            "Target": {"type": "rich_text"},
            "Metric": {"type": "rich_text"},
            "Deadline": {"type": "date"},
            "Status": {"type": "select"},
        }
    }


def default_location_schema() -> dict[str, Any]:
    return {
        "properties": {
            "Name": {"type": "title"},
            "Description": {"type": "rich_text"},
            "Equipment": {"type": "rich_text"},
            "Default": {"type": "checkbox"},
        }
    }


def default_stats_schema() -> dict[str, Any]:
    return {
        "properties": {
            "Name": {"type": "title"},
            "Date": {"type": "date"},
            "Height": {"type": "rich_text"},
            "Weight": {"type": "rich_text"},
            "Squat": {"type": "rich_text"},
            "Bench": {"type": "rich_text"},
            "Deadlift": {"type": "rich_text"},
            "Overhead press": {"type": "rich_text"},
        }
    }


def parse_goal_page(page: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    props = page.get("properties") or {}
    schema = schema or {"properties": {name: {"type": value.get("type")} for name, value in props.items()}}
    return {
        "id": page.get("id"),
        "url": page_url(page),
        "name": _read(props, schema, TITLE_ALIASES, "title", "rich_text"),
        "description": _read(props, schema, DESCRIPTION_ALIASES, "rich_text"),
        "target": _read(props, schema, TARGET_ALIASES, "rich_text", "number"),
        "metric": _read(props, schema, METRIC_ALIASES, "rich_text", "select"),
        "deadline": (_read(props, schema, DEADLINE_ALIASES, "date") or "")[:10] or None,
        "status": _read(props, schema, GOAL_STATUS_ALIASES, "select", "status", "rich_text"),
    }


def parse_location_page(page: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    props = page.get("properties") or {}
    schema = schema or {"properties": {name: {"type": value.get("type")} for name, value in props.items()}}
    return {
        "id": page.get("id"),
        "url": page_url(page),
        "name": _read(props, schema, TITLE_ALIASES, "title", "rich_text"),
        "description": _read(props, schema, DESCRIPTION_ALIASES, "rich_text"),
        "equipment": _read(props, schema, EQUIPMENT_ALIASES, "rich_text"),
        "is_default": _as_bool(_read(props, schema, DEFAULT_ALIASES, "checkbox")),
    }


def parse_stats_page(page: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    props = page.get("properties") or {}
    schema = schema or {"properties": {name: {"type": value.get("type")} for name, value in props.items()}}
    return {
        "id": page.get("id"),
        "url": page_url(page),
        "name": _read(props, schema, TITLE_ALIASES, "title", "rich_text"),
        "date": (_read(props, schema, LIFT_DATE_ALIASES, "date") or "")[:10] or None,
        "height": _read(props, schema, HEIGHT_ALIASES, "rich_text", "number"),
        "weight": _read(props, schema, BODY_WEIGHT_ALIASES, "rich_text", "number"),
        "squat": _read(props, schema, SQUAT_ALIASES, "rich_text", "number"),
        "bench": _read(props, schema, BENCH_ALIASES, "rich_text", "number"),
        "deadlift": _read(props, schema, DEADLIFT_ALIASES, "rich_text", "number"),
        "overhead_press": _read(props, schema, OHP_ALIASES, "rich_text", "number"),
    }


def build_goal_properties(data: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or default_goal_schema()
    return _fill(
        schema,
        data,
        [
            (TITLE_ALIASES, ("title",), "name"),
            (DESCRIPTION_ALIASES, ("rich_text",), "description"),
            (TARGET_ALIASES, ("rich_text", "number"), "target"),
            (METRIC_ALIASES, ("rich_text", "select"), "metric"),
            (DEADLINE_ALIASES, ("date",), "deadline"),
            (GOAL_STATUS_ALIASES, ("select", "status", "rich_text"), "status"),
        ],
    )


def build_location_properties(data: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or default_location_schema()
    return _fill(
        schema,
        data,
        [
            (TITLE_ALIASES, ("title",), "name"),
            (DESCRIPTION_ALIASES, ("rich_text",), "description"),
            (EQUIPMENT_ALIASES, ("rich_text",), "equipment"),
            (DEFAULT_ALIASES, ("checkbox",), "is_default"),
        ],
    )


def build_stats_properties(data: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or default_stats_schema()
    payload = dict(data)
    if "name" not in payload and payload.get("date"):
        payload["name"] = str(payload.get("date"))
    return _fill(
        schema,
        payload,
        [
            (TITLE_ALIASES, ("title",), "name"),
            (LIFT_DATE_ALIASES, ("date",), "date"),
            (HEIGHT_ALIASES, ("rich_text", "number"), "height"),
            (BODY_WEIGHT_ALIASES, ("rich_text", "number"), "weight"),
            (SQUAT_ALIASES, ("rich_text", "number"), "squat"),
            (BENCH_ALIASES, ("rich_text", "number"), "bench"),
            (DEADLIFT_ALIASES, ("rich_text", "number"), "deadlift"),
            (OHP_ALIASES, ("rich_text", "number"), "overhead_press"),
        ],
    )


def _in_range(value: str | None, start: str | None, end: str | None) -> bool:
    if not value:
        return False
    day = value[:10]
    if start and day < start[:10]:
        return False
    if end and day > end[:10]:
        return False
    return True


class NotionStore:
    def __init__(self, client: NotionClient | None = None):
        self.client = client or NotionClient()
        self._schemas: dict[str, dict[str, Any]] = {}

    async def schema(self, database_id: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if database_id in self._schemas:
            return self._schemas[database_id]
        try:
            schema = await self.client.retrieve_database(database_id)
        except NotionError:
            schema = fallback
        self._schemas[database_id] = schema
        return schema

    async def list_lifts(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        settings = get_settings()
        if not settings.notion_lifts_database_id:
            raise NotionError("NOTION_LIFTS_DATABASE_ID is not set", 400)
        schema = await self.schema(settings.notion_lifts_database_id, default_lift_schema())
        pages = await self.client.query_database(settings.notion_lifts_database_id)
        rows = [parse_lift_page(page, schema) for page in pages]
        if date_from or date_to:
            rows = [row for row in rows if _in_range(row.get("date"), date_from, date_to)]
        rows.sort(key=lambda row: row.get("date") or "", reverse=True)
        return rows

    async def get_lift(self, item_id: str) -> dict[str, Any]:
        page = await self.client.retrieve_page(item_id)
        schema = default_lift_schema()
        settings = get_settings()
        if settings.notion_lifts_database_id:
            schema = await self.schema(settings.notion_lifts_database_id, default_lift_schema())
        return parse_lift_page(page, schema)

    async def create_lift(self, data: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        if not settings.notion_lifts_database_id:
            raise NotionError("NOTION_LIFTS_DATABASE_ID is not set", 400)
        payload = dict(data)
        schema = await self.schema(settings.notion_lifts_database_id, default_lift_schema())
        page = await self.client.create_page(
            {
                "parent": {"database_id": settings.notion_lifts_database_id},
                "properties": build_lift_properties(payload, schema),
            }
        )
        return parse_lift_page(page, schema)

    async def update_lift(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        schema = default_lift_schema()
        if settings.notion_lifts_database_id:
            schema = await self.schema(settings.notion_lifts_database_id, default_lift_schema())
        page = await self.client.update_page(item_id, {"properties": build_lift_properties(data, schema)})
        return parse_lift_page(page, schema)

    async def delete_lift(self, item_id: str) -> str:
        await self.client.update_page(item_id, {"archived": True})
        return "deleted"

    async def recent_performance(self) -> list[dict[str, Any]]:
        rows = await self.list_lifts()
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = (row.get("lift") or "").casefold()
            if not key or key in latest:
                continue
            latest[key] = row
        return list(latest.values())

    async def list_logs(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        settings = get_settings()
        if not settings.notion_logs_database_id:
            raise NotionError("NOTION_LOGS_DATABASE_ID is not set", 400)
        schema = await self.schema(settings.notion_logs_database_id, default_log_schema())
        pages = await self.client.query_database(settings.notion_logs_database_id)
        rows = [parse_log_page(page, schema) for page in pages]
        if date_from or date_to:
            rows = [row for row in rows if _in_range(row.get("date"), date_from, date_to)]
        rows.sort(key=lambda row: row.get("date") or "", reverse=True)
        return rows

    async def upsert_log(self, data: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        if not settings.notion_logs_database_id:
            raise NotionError("NOTION_LOGS_DATABASE_ID is not set", 400)
        payload = dict(data)
        schema = await self.schema(settings.notion_logs_database_id, default_log_schema())
        existing = await self.list_logs(date_from=payload.get("date"), date_to=payload.get("date"))
        properties = build_log_properties(payload, schema)
        if existing and existing[0].get("id"):
            page = await self.client.update_page(existing[0]["id"], {"properties": properties})
        else:
            page = await self.client.create_page(
                {"parent": {"database_id": settings.notion_logs_database_id}, "properties": properties}
            )
        return parse_log_page(page, schema)

    async def get_log(self, item_id: str) -> dict[str, Any]:
        page = await self.client.retrieve_page(item_id)
        schema = default_log_schema()
        settings = get_settings()
        if settings.notion_logs_database_id:
            schema = await self.schema(settings.notion_logs_database_id, default_log_schema())
        return parse_log_page(page, schema)

    async def delete_log(self, item_id: str) -> str:
        await self.client.update_page(item_id, {"archived": True})
        return "deleted"

    def _db_id(self, attr: str, env_name: str) -> str:
        value = getattr(get_settings(), attr)
        if not value:
            raise NotionError(f"{env_name} is not set", 400)
        return value

    async def _list_db(
        self,
        database_id: str,
        fallback: dict[str, Any],
        parse,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_key: str = "date",
    ) -> list[dict[str, Any]]:
        schema = await self.schema(database_id, fallback)
        pages = await self.client.query_database(database_id)
        rows = [parse(page, schema) for page in pages]
        if date_from or date_to:
            rows = [row for row in rows if _in_range(row.get("date"), date_from, date_to)]
        rows.sort(key=lambda row: row.get(sort_key) or row.get("name") or "", reverse=True)
        return rows

    async def _create_db(self, database_id: str, fallback: dict[str, Any], build, parse, data: dict[str, Any]) -> dict[str, Any]:
        schema = await self.schema(database_id, fallback)
        page = await self.client.create_page(
            {"parent": {"database_id": database_id}, "properties": build(data, schema)}
        )
        return parse(page, schema)

    async def _update_db(
        self,
        item_id: str,
        database_id: str,
        fallback: dict[str, Any],
        build,
        parse,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        schema = await self.schema(database_id, fallback) if database_id else fallback
        page = await self.client.update_page(item_id, {"properties": build(data, schema)})
        return parse(page, schema)

    async def _get_db(self, item_id: str, database_id: str, fallback: dict[str, Any], parse) -> dict[str, Any]:
        page = await self.client.retrieve_page(item_id)
        schema = await self.schema(database_id, fallback) if database_id else fallback
        return parse(page, schema)

    async def list_goals(self) -> list[dict[str, Any]]:
        return await self._list_db(
            self._db_id("notion_goals_database_id", "NOTION_GOALS_DATABASE_ID"),
            default_goal_schema(),
            parse_goal_page,
            sort_key="deadline",
        )

    async def get_goal(self, item_id: str) -> dict[str, Any]:
        return await self._get_db(
            item_id,
            get_settings().notion_goals_database_id,
            default_goal_schema(),
            parse_goal_page,
        )

    async def create_goal(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        payload.setdefault("status", "Active")
        return await self._create_db(
            self._db_id("notion_goals_database_id", "NOTION_GOALS_DATABASE_ID"),
            default_goal_schema(),
            build_goal_properties,
            parse_goal_page,
            payload,
        )

    async def update_goal(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._update_db(
            item_id,
            get_settings().notion_goals_database_id,
            default_goal_schema(),
            build_goal_properties,
            parse_goal_page,
            data,
        )

    async def delete_goal(self, item_id: str) -> str:
        await self.client.update_page(item_id, {"archived": True})
        return "deleted"

    async def list_locations(self) -> list[dict[str, Any]]:
        rows = await self._list_db(
            self._db_id("notion_locations_database_id", "NOTION_LOCATIONS_DATABASE_ID"),
            default_location_schema(),
            parse_location_page,
            sort_key="name",
        )
        rows.sort(key=lambda row: (not row.get("is_default"), (row.get("name") or "").casefold()))
        return rows

    async def get_location(self, item_id: str) -> dict[str, Any]:
        return await self._get_db(
            item_id,
            get_settings().notion_locations_database_id,
            default_location_schema(),
            parse_location_page,
        )

    async def create_location(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._create_db(
            self._db_id("notion_locations_database_id", "NOTION_LOCATIONS_DATABASE_ID"),
            default_location_schema(),
            build_location_properties,
            parse_location_page,
            data,
        )

    async def update_location(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._update_db(
            item_id,
            get_settings().notion_locations_database_id,
            default_location_schema(),
            build_location_properties,
            parse_location_page,
            data,
        )

    async def delete_location(self, item_id: str) -> str:
        await self.client.update_page(item_id, {"archived": True})
        return "deleted"

    async def list_body_stats(self, *, date_from: str | None = None, date_to: str | None = None) -> list[dict[str, Any]]:
        return await self._list_db(
            self._db_id("notion_stats_database_id", "NOTION_STATS_DATABASE_ID"),
            default_stats_schema(),
            parse_stats_page,
            date_from=date_from,
            date_to=date_to,
        )

    async def get_body_stats(self, item_id: str) -> dict[str, Any]:
        return await self._get_db(
            item_id,
            get_settings().notion_stats_database_id,
            default_stats_schema(),
            parse_stats_page,
        )

    async def create_body_stats(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._create_db(
            self._db_id("notion_stats_database_id", "NOTION_STATS_DATABASE_ID"),
            default_stats_schema(),
            build_stats_properties,
            parse_stats_page,
            data,
        )

    async def update_body_stats(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._update_db(
            item_id,
            get_settings().notion_stats_database_id,
            default_stats_schema(),
            build_stats_properties,
            parse_stats_page,
            data,
        )

    async def delete_body_stats(self, item_id: str) -> str:
        await self.client.update_page(item_id, {"archived": True})
        return "deleted"

    async def planning_context(self) -> dict[str, Any]:
        goals: list[dict[str, Any]] = []
        locations: list[dict[str, Any]] = []
        stats: list[dict[str, Any]] = []
        try:
            goals = await self.list_goals()
        except NotionError:
            goals = []
        try:
            locations = await self.list_locations()
        except NotionError:
            locations = []
        try:
            stats = await self.list_body_stats()
        except NotionError:
            stats = []
        active = [row for row in goals if (row.get("status") or "Active").casefold() not in {"done", "complete", "completed"}]
        default = next((row for row in locations if row.get("is_default")), locations[0] if locations else None)
        return {
            "goals": active,
            "all_goals": goals,
            "locations": locations,
            "default_location": default,
            "latest_body_stats": stats[0] if stats else None,
        }


def _lift_label(lift: PlannedLift) -> str:
    parts = [lift.lift]
    details: list[str] = []
    if lift.reps is not None:
        details.append(f"{lift.reps} reps")
    weight = lift.actual_weight or lift.goal_weight
    if weight:
        details.append(f"@ {weight}")
        if lift.actual_weight and lift.goal_weight and lift.actual_weight != lift.goal_weight:
            details.append(f"(goal {lift.goal_weight})")
    if details:
        parts.append("— " + " ".join(details))
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
    for cardio in day.cardio:
        label = cardio.kind.title()
        if cardio.distance:
            label = f"{label} {cardio.distance}"
        blocks.append(_todo(label, checked=cardio.completed))
    extras: list[str] = []
    if day.protein_goal is not None:
        extras.append(f"Protein {day.protein_goal}g")
    if day.steps_goal is not None:
        extras.append(f"Steps {day.steps_goal:,}")
    if extras:
        blocks.append(_paragraph(" · ".join(extras)))
    return blocks


def _profile_blocks(plan: WeeklyPlan) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if plan.body_stats:
        stats = plan.body_stats
        parts = []
        if stats.weight:
            parts.append(f"Weight {stats.weight}")
        if stats.height:
            parts.append(f"Height {stats.height}")
        for label, value in (
            ("Squat", stats.squat),
            ("Bench", stats.bench),
            ("Deadlift", stats.deadlift),
            ("OHP", stats.overhead_press),
        ):
            if value:
                parts.append(f"{label} {value}")
        if parts:
            prefix = f"Body stats ({stats.date.isoformat()})" if stats.date else "Body stats"
            blocks.append(_paragraph(f"{prefix}: " + " · ".join(parts)))
    if plan.locations:
        default = next((item for item in plan.locations if item.is_default), plan.locations[0])
        label = default.name
        if default.equipment:
            label = f"{label} ({default.equipment})"
        blocks.append(_paragraph(f"Location: {label}"))
    if plan.goals:
        blocks.append(_heading("Goals", 3))
        for goal in plan.goals:
            text = goal.name
            if goal.target:
                text = f"{text} — {goal.target}"
            if goal.deadline:
                text = f"{text} by {goal.deadline}"
            blocks.append(_todo(text, checked=(goal.status or "").casefold() in {"done", "complete", "completed"}))
    return blocks


def build_page_children(plan: WeeklyPlan) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [_heading(plan.title, 1)]
    if plan.focus:
        blocks.append(_callout(plan.focus))
    if plan.notes:
        blocks.append(_paragraph(plan.notes))
    blocks.extend(_profile_blocks(plan))
    blocks.append(
        _paragraph(
            "Log Actual weight on the Workout Lifts row. That number is what next week’s plan uses.",
            italic=True,
        )
    )
    for day in plan.days:
        blocks.extend(_day_blocks(day))
    return blocks


def build_week_properties(plan: WeeklyPlan, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or {"properties": {"Name": {"type": "title"}}}
    properties = _fill(
        schema,
        {
            "title": plan.title,
            "status": "Planned",
            "focus": plan.focus,
        },
        [
            (TITLE_ALIASES, ("title",), "title"),
            (STATUS_ALIASES, ("select", "status"), "status"),
            (FOCUS_ALIASES, ("rich_text",), "focus"),
        ],
    )
    week_name = _find_property(schema, WEEK_ALIASES, "date")
    if week_name:
        properties[week_name] = {
            "date": {"start": plan.week_start.isoformat(), "end": plan.week_end.isoformat()}
        }
    return properties


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
    notion = client or NotionClient()
    schema = None
    if not dry_run:
        if not settings.notion_database_id:
            raise NotionError("NOTION_DATABASE_ID is not set", 400)
        try:
            schema = await notion.retrieve_database(settings.notion_database_id)
        except NotionError:
            schema = None
    properties = build_week_properties(plan, schema)
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
    if settings.notion_template_id:
        create_payload["template"] = {"type": "template_id", "template_id": settings.notion_template_id}
        if settings.notion_data_source_id:
            create_payload["parent"] = {
                "type": "data_source_id",
                "data_source_id": settings.notion_data_source_id,
            }
        notion.version = settings.notion_version or NOTION_TEMPLATE_VERSION
        page = await notion.create_page(create_payload)
        for _ in range(20):
            try:
                if await notion.list_children(page["id"]):
                    break
            except NotionError:
                pass
            await asyncio.sleep(0.4)
        for extra in _chunk(children):
            await notion.append_children(page["id"], extra)
    else:
        first, rest = children[:CHILDREN_PAGE_SIZE], children[CHILDREN_PAGE_SIZE:]
        create_payload["children"] = first
        page = await notion.create_page(create_payload)
        for extra in _chunk(rest):
            await notion.append_children(page["id"], extra)
    return {
        "dry_run": False,
        "url": page_url(page),
        "page_id": page.get("id"),
        "title": plan.title,
        "week_start": plan.week_start.isoformat(),
        "week_end": plan.week_end.isoformat(),
    }


def parse_day(value: str) -> str:
    return value.replace("Z", "+00:00")[:10]


def coerce_date(value: str | date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return parse_day(value)
