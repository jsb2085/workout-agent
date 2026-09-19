from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from app.notion_import import load_schema
from app.services.notion import (
    NotionClient,
    NotionError,
    _bulleted,
    _callout,
    _divider,
    _heading,
    _paragraph,
    _quote,
    _toc,
    _toggle,
    page_url,
)

ENV_KEYS = (
    "NOTION_DATABASE_ID",
    "NOTION_LIFTS_DATABASE_ID",
    "NOTION_LOGS_DATABASE_ID",
    "NOTION_GOALS_DATABASE_ID",
    "NOTION_LOCATIONS_DATABASE_ID",
    "NOTION_STATS_DATABASE_ID",
)


def parse_page_id(value: str) -> str:
    text = (value or "").strip().split("?")[0].split("#")[0].rstrip("/")
    if not text:
        raise NotionError("Parent page id is empty", 400)
    compact = re.sub(r"[^0-9a-fA-F]", "", text)
    if len(compact) < 32:
        raise NotionError(f"Could not parse a Notion page id from {value!r}", 400)
    compact = compact[-32:].lower()
    return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"


def is_share_error(message: str) -> bool:
    text = (message or "").casefold()
    return "could not find page" in text or "shared with your integration" in text


def page_title(page: dict[str, Any]) -> str:
    for prop in (page.get("properties") or {}).values():
        if not isinstance(prop, dict) or prop.get("type") != "title":
            continue
        parts = prop.get("title") or []
        text = "".join(str(part.get("plain_text") or part.get("text", {}).get("content") or "") for part in parts)
        if text.strip():
            return text.strip()
    return page.get("id") or "Untitled"


def share_error_message(parent_id: str, original: str, pages: list[dict[str, Any]] | None = None) -> str:
    lines = [
        original.rstrip("."),
        "",
        "The Workout Agent integration cannot see that page yet. Notion hides every page until you invite the integration.",
        "",
        "1. Open the parent page in Notion (the URL you passed to --parent).",
        "2. Click Share (top right) → Invite → select the integration named Workout Agent.",
        "3. Give it Can edit, then run the same command again.",
        "",
        f"Parsed page id: {parent_id}",
        "Pass any existing page you shared. setup creates a Workout Agent child under it.",
        "If this URL is already the page you want filled, add --in-place after sharing it.",
    ]
    if pages:
        lines.append("")
        lines.append("Pages this integration can already see:")
        for page in pages:
            title = page_title(page)
            url = page_url(page) or page.get("id")
            lines.append(f"- {title}  {url}")
    else:
        lines.append("")
        lines.append("This integration cannot see any pages yet. Share one page, then rerun setup with that page's URL.")
    return "\n".join(lines)


async def accessible_pages(client: NotionClient) -> list[dict[str, Any]]:
    try:
        return await client.search_pages()
    except NotionError:
        return []


def property_names(database: dict[str, Any]) -> list[str]:
    return list((database.get("properties") or {}).keys())


def csv_text(database: dict[str, Any]) -> str:
    names = property_names(database)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=names, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in database.get("seed") or []:
        writer.writerow({key: _csv_value(row.get(key)) for key in names})
    return buffer.getvalue()


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _rich(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}]


def database_payload(database: dict[str, Any], parent_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "title": _rich(database["title"]),
        "is_inline": True,
        "properties": database["properties"],
    }
    if database.get("description"):
        payload["description"] = _rich(database["description"])
    if database.get("icon"):
        payload["icon"] = {"type": "emoji", "emoji": database["icon"]}
    return payload


def hub_intro_blocks(schema: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    spec = schema or load_schema()
    sections = spec.get("sections") or {}
    edit = sections.get("edit") or {}
    how_to = spec.get("how_to") or spec.get("intro") or []
    return [
        _quote(spec.get("tagline") or spec["intro"][0]),
        _callout(spec["intro"][0], emoji="🏋️", color="blue_background"),
        _toc(),
        _toggle("How this page works", [_bulleted(step) for step in how_to]),
        _callout("Goals — keep Status Active", emoji="🎯", color="green_background"),
        _callout("Location — one Default gym", emoji="📍", color="blue_background"),
        _callout("Body stats — latest row wins", emoji="📏", color="purple_background"),
        _divider(),
        _heading(edit.get("title") or "Your inputs", 2),
        _paragraph(edit.get("blurb") or "These tables are the coaching brief.", italic=True),
    ]


def section_intro_blocks(section: str, schema: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    spec = schema or load_schema()
    meta = (spec.get("sections") or {}).get(section) or {}
    return [
        _divider(),
        _heading(meta.get("title") or section.title(), 2),
        _paragraph(meta.get("blurb") or "", italic=True),
    ]


def database_frame_blocks(database: dict[str, Any]) -> list[dict[str, Any]]:
    icon = database.get("icon") or "•"
    title = f"{icon} {database['title']}"
    hint = database.get("hint") or database.get("description") or ""
    color = database.get("callout_color") or "gray_background"
    blocks = [_heading(title, 3)]
    if hint:
        blocks.append(_callout(hint, emoji=icon, color=color))
    return blocks


def hub_page_payload(parent_id: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = schema or load_schema()
    payload: dict[str, Any] = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {"title": {"title": _rich(spec["page_title"])}},
        "children": hub_intro_blocks(spec),
    }
    if spec.get("page_icon"):
        payload["icon"] = {"type": "emoji", "emoji": spec["page_icon"]}
    if spec.get("page_cover"):
        payload["cover"] = {"type": "external", "external": {"url": spec["page_cover"]}}
    return payload


def seed_properties(database: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    specs = database.get("properties") or {}
    for name, value in row.items():
        if name not in specs or value is None or value == "":
            continue
        spec = specs[name]
        if "title" in spec:
            properties[name] = {"title": _rich(str(value))}
        elif "rich_text" in spec:
            properties[name] = {"rich_text": _rich(str(value))}
        elif "select" in spec:
            properties[name] = {"select": {"name": str(value)}}
        elif "checkbox" in spec:
            if isinstance(value, bool):
                checked = value
            else:
                checked = str(value).strip().casefold() in {"true", "yes", "1"}
            properties[name] = {"checkbox": checked}
        elif "date" in spec:
            properties[name] = {"date": {"start": str(value)[:10]}}
        elif "number" in spec:
            number = float(value) if "." in str(value) else int(value)
            properties[name] = {"number": number}
    return properties


def env_snippet(ids: dict[str, str]) -> str:
    lines = ["# Notion workspace created by workout setup"]
    for key in ENV_KEYS:
        if key in ids:
            lines.append(f"{key}={ids[key]}")
    if "NOTION_PARENT_PAGE_ID" in ids:
        lines.append(f"NOTION_PARENT_PAGE_ID={ids['NOTION_PARENT_PAGE_ID']}")
    return "\n".join(lines) + "\n"


def upsert_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if stripped and not stripped.startswith("#") and "=" in stripped else None
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    missing = [key for key in values if key not in seen]
    if missing:
        if out and out[-1] != "":
            out.append("")
        out.extend(f"{key}={values[key]}" for key in missing)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


async def setup_workspace(
    parent: str,
    *,
    dry_run: bool = False,
    in_place: bool = False,
    seed: bool = True,
    write_env: str | Path | None = None,
    client: NotionClient | None = None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = schema or load_schema()
    parent_id = parse_page_id(parent)
    notion = None if dry_run else (client or NotionClient())
    created: dict[str, Any] = {}
    env_ids: dict[str, str] = {}

    if not dry_run:
        assert notion is not None
        try:
            await notion.retrieve_page(parent_id)
        except NotionError as exc:
            if is_share_error(str(exc)):
                pages = await accessible_pages(notion)
                raise NotionError(share_error_message(parent_id, str(exc), pages), exc.status_code) from exc
            raise

    if in_place:
        hub_id = parent_id
        hub_url = None
        if dry_run:
            created["hub"] = {"id": hub_id, "dry_run": True, "in_place": True}
        else:
            assert notion is not None
            await notion.append_children(hub_id, hub_page_payload(parent_id, spec)["children"])
            page = await notion.retrieve_page(hub_id)
            hub_url = page_url(page)
            created["hub"] = {"id": hub_id, "url": hub_url, "in_place": True}
    else:
        page_payload = hub_page_payload(parent_id, spec)
        if dry_run:
            hub_id = "dry-run-hub"
            created["hub"] = {"id": hub_id, "payload": page_payload, "dry_run": True}
        else:
            assert notion is not None
            page = await notion.create_page(page_payload)
            hub_id = page["id"]
            created["hub"] = {"id": hub_id, "url": page_url(page)}

    env_ids["NOTION_PARENT_PAGE_ID"] = hub_id
    databases: list[dict[str, Any]] = []
    layout: list[dict[str, Any]] = [{"kind": "intro", "blocks": hub_intro_blocks(spec)}]
    current_section = "edit"
    for database in spec["databases"]:
        section = database.get("section") or "edit"
        if section != current_section:
            section_blocks = section_intro_blocks(section, spec)
            layout.append({"kind": "section", "section": section, "blocks": section_blocks})
            if not dry_run:
                assert notion is not None
                await notion.append_children(hub_id, section_blocks)
            current_section = section
        frame = database_frame_blocks(database)
        layout.append({"kind": "frame", "title": database["title"], "blocks": frame})
        if not dry_run:
            assert notion is not None
            await notion.append_children(hub_id, frame)
        payload = database_payload(database, hub_id)
        if dry_run:
            db_id = f"dry-run-{database['key']}"
            record = {"id": db_id, "title": database["title"], "env": database["env"], "payload": payload, "dry_run": True}
        else:
            assert notion is not None
            result = await notion.create_database(payload)
            db_id = result["id"]
            record = {
                "id": db_id,
                "title": database["title"],
                "env": database["env"],
                "url": result.get("url"),
            }
            if seed:
                for row in database.get("seed") or []:
                    await notion.create_page(
                        {
                            "parent": {"database_id": db_id},
                            "properties": seed_properties(database, row),
                        }
                    )
        env_ids[database["env"]] = db_id
        databases.append(record)

    footer = [
        _divider(),
        _callout("When the week is logged, run: workout run", emoji="▶️", color="blue_background"),
    ]
    layout.append({"kind": "footer", "blocks": footer})
    if not dry_run:
        assert notion is not None
        await notion.append_children(hub_id, footer)

    created["databases"] = databases
    created["layout"] = [
        {key: value for key, value in item.items() if key != "blocks"}
        | {"block_types": [block["type"] for block in item.get("blocks") or []]}
        for item in layout
    ]
    created["env"] = env_snippet(env_ids)
    created["env_ids"] = env_ids
    created["csv_files"] = [item["csv"] for item in spec["databases"]]
    created["dry_run"] = dry_run
    if write_env and not dry_run:
        upsert_env(Path(write_env), {key: value for key, value in env_ids.items() if key in ENV_KEYS or key == "NOTION_PARENT_PAGE_ID"})
        created["wrote_env"] = str(write_env)
    return created
