from pathlib import Path

from app.cli import main
from app.mcp.server import mcp
from app.notion_import import load_schema
from app.services.notion import NotionError
from app.services.workspace import (
    csv_text,
    database_frame_blocks,
    database_payload,
    hub_page_payload,
    parse_page_id,
    seed_properties,
    setup_workspace,
    upsert_env,
)
from tests.test_mcp import _tool_payload


def test_parse_page_id_from_url_and_uuid():
    uuid = "264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4"
    assert parse_page_id(uuid) == uuid
    assert parse_page_id(uuid.replace("-", "")) == uuid
    assert parse_page_id(f"https://www.notion.so/Workout-Agent-{uuid.replace('-', '')}") == uuid
    assert parse_page_id(f"https://app.notion.com/p/Workout-Agent-{uuid.replace('-', '')}") == uuid
    try:
        parse_page_id("not-an-id")
    except NotionError:
        pass
    else:
        raise AssertionError("expected NotionError")


def test_schema_csv_headers_and_seed():
    spec = load_schema()
    assert [item["title"] for item in spec["databases"]] == [
        "Goals",
        "Workout Locations",
        "Body Stats",
        "Workout Lifts",
        "Daily Logs",
        "Weekly Workouts",
    ]
    goals = spec["databases"][0]
    csv_body = csv_text(goals)
    assert csv_body.splitlines()[0] == "Name,Target,Metric,Deadline,Status,Description"
    assert "Bench 225" in csv_body
    assert "Active" in csv_body
    lifts = next(item for item in spec["databases"] if item["key"] == "lifts")
    assert csv_text(lifts).strip() == "Name,Date,Goal weight,Actual weight,Reps,Completed,Week start"


def test_committed_csvs_match_schema():
    repo = Path(__file__).resolve().parents[1] / "notion" / "csv"
    spec = load_schema()
    for database in spec["databases"]:
        path = repo / database["csv"]
        assert path.read_text(encoding="utf-8") == csv_text(database)


def test_database_payload_is_inline():
    spec = load_schema()
    payload = database_payload(spec["databases"][0], "264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4")
    assert payload["is_inline"] is True
    assert payload["parent"]["page_id"] == "264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4"
    assert "Name" in payload["properties"]
    assert payload["properties"]["Status"]["select"]["options"][0]["name"] == "Active"


def test_hub_page_is_a_dashboard_around_the_tables():
    payload = hub_page_payload("264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4")
    types = [block["type"] for block in payload["children"]]
    assert payload["icon"]["emoji"] == "🏋️"
    assert payload["cover"]["external"]["url"].startswith("https://images.unsplash.com/")
    assert types == [
        "quote",
        "callout",
        "table_of_contents",
        "toggle",
        "callout",
        "callout",
        "callout",
        "divider",
        "heading_2",
        "paragraph",
    ]
    assert payload["children"][3]["toggle"]["children"][0]["type"] == "bulleted_list_item"
    goals = load_schema()["databases"][0]
    frame = database_frame_blocks(goals)
    assert frame[0]["type"] == "heading_3"
    assert "Goals" in frame[0]["heading_3"]["rich_text"][0]["text"]["content"]
    assert frame[1]["callout"]["color"] == "green_background"


def test_seed_properties_types():
    spec = load_schema()
    location = next(item for item in spec["databases"] if item["key"] == "locations")
    props = seed_properties(location, location["seed"][0])
    assert props["Name"]["title"][0]["text"]["content"] == "Home gym"
    assert props["Default"]["checkbox"] is True


async def test_setup_dry_run_does_not_call_notion():
    result = await setup_workspace("264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4", dry_run=True)
    assert result["dry_run"] is True
    assert len(result["databases"]) == 6
    assert "NOTION_GOALS_DATABASE_ID=dry-run-goals" in result["env"]
    assert result["databases"][0]["payload"]["is_inline"] is True
    kinds = [item["kind"] for item in result["layout"]]
    assert kinds[0] == "intro"
    assert kinds.count("frame") == 6
    assert "section" in kinds
    assert kinds[-1] == "footer"
    assert "quote" in result["hub"]["payload"]["children"][0]["type"]


async def test_setup_creates_hub_databases_and_seed_rows():
    calls: list[tuple] = []

    class FakeClient:
        async def create_page(self, payload):
            calls.append(("page", payload))
            ident = f"page-{len(calls)}"
            return {"id": ident, "url": f"https://www.notion.so/{ident}"}

        async def create_database(self, payload):
            calls.append(("db", payload["title"][0]["text"]["content"]))
            ident = f"db-{len(calls)}"
            return {"id": ident, "url": f"https://www.notion.so/{ident}"}

        async def append_children(self, block_id, children):
            calls.append(("append", block_id, children[0]["type"]))
            return {}

        async def retrieve_page(self, page_id):
            return {"id": page_id, "url": f"https://www.notion.so/{page_id}"}

    result = await setup_workspace(
        "264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4",
        client=FakeClient(),
    )
    kinds = [item[0] for item in calls]
    assert kinds.count("db") == 6
    assert kinds.count("page") == 4  # hub + 3 example rows
    assert "append" in kinds
    assert result["env_ids"]["NOTION_GOALS_DATABASE_ID"].startswith("db-")
    assert result["hub"]["id"] == "page-1"


def test_cli_setup_dry_run(capsys, monkeypatch):
    async def fake_setup(parent, **kwargs):
        assert parent.endswith("b3c4")
        assert kwargs["dry_run"] is True
        return {"dry_run": True, "env": "NOTION_GOALS_DATABASE_ID=abc"}

    monkeypatch.setattr("app.cli.setup_workspace", fake_setup)
    assert main(["setup", "--parent", "264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4", "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "NOTION_GOALS_DATABASE_ID" in printed
    assert '"dry_run": true' in printed


async def test_mcp_setup_notion_workspace(monkeypatch):
    async def fake_setup(parent, **kwargs):
        assert kwargs["dry_run"] is True
        return {"dry_run": True, "hub": {"id": "page-1"}, "databases": [{"title": "Goals"}]}

    monkeypatch.setattr("app.mcp.tools.setup_workspace", fake_setup)
    result = await mcp.call_tool(
        "setup_notion_workspace",
        {"parent_page": "264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4", "dry_run": True},
    )
    payload = _tool_payload(result)
    assert payload["databases"][0]["title"] == "Goals"


def test_upsert_env(tmp_path):
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=sk-test\nNOTION_TOKEN=secret\n", encoding="utf-8")
    upsert_env(path, {"NOTION_GOALS_DATABASE_ID": "goals-1", "NOTION_TOKEN": "secret"})
    text = path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test" in text
    assert "NOTION_GOALS_DATABASE_ID=goals-1" in text
    assert text.count("NOTION_TOKEN=secret") == 1


def test_repo_root_workout_script():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "workout"), "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "setup" in result.stdout
    assert "run" in result.stdout


async def test_setup_share_error_lists_visible_pages():
    class FakeClient:
        async def retrieve_page(self, page_id):
            raise NotionError(
                'Could not find page with ID: 264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4. Make sure the relevant pages and databases are shared with your integration "Workout Agent".',
                404,
            )

        async def search_pages(self, **kwargs):
            return [
                {
                    "id": "visible",
                    "url": "https://www.notion.so/visible",
                    "properties": {
                        "title": {"type": "title", "title": [{"plain_text": "Gym notes"}]}
                    },
                }
            ]

    try:
        await setup_workspace("264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4", client=FakeClient())
    except NotionError as exc:
        text = str(exc)
        assert "Share" in text
        assert "Gym notes" in text
        assert "Can edit" in text
    else:
        raise AssertionError("expected NotionError")


def test_cli_setup_share_error_has_no_traceback(capsys, monkeypatch):
    async def fail(*args, **kwargs):
        raise NotionError("Could not find page with ID: abc. Shared with your integration.", 404)

    monkeypatch.setattr("app.cli.setup_workspace", fail)
    assert main(["setup", "--parent", "264b5d28-04f5-81a3-b8d4-c9f6e1a2b3c4"]) == 1
    captured = capsys.readouterr()
    assert "Could not find page" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
