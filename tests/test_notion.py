from datetime import date

from app.cli import main
from app.mcp.server import mcp
from app.schemas.weekly_plan import PlannedCardio, PlannedDay, PlannedLift, WeeklyPlan
from app.services import exercisedb, notion, weekly_plan as weekly_plan_service
from tests.test_mcp import _tool_payload


def _sample_plan() -> WeeklyPlan:
    return WeeklyPlan(
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
        title="Week of Sep 21–27",
        focus="bench + squat",
        days=[
            PlannedDay(
                date=date(2026, 9, 21),
                lifts=[
                    PlannedLift(
                        lift="bench press",
                        reps=5,
                        goal_weight="185",
                        actual_weight="195",
                        completed=True,
                        demo_url="https://cdn.exercisedb.dev/videos/bench.mp4",
                        media_kind="video",
                    )
                ],
                cardio=[PlannedCardio(kind="walk", distance="2 miles")],
                protein_goal=160,
            ),
            PlannedDay(date=date(2026, 9, 22)),
        ],
    )


def test_build_page_uses_actual_weight():
    children = notion.build_page_children(_sample_plan())
    todos = [block for block in children if block["type"] == "to_do"]
    assert any("195" in block["to_do"]["rich_text"][0]["text"]["content"] for block in todos)
    assert any("Walk" in block["to_do"]["rich_text"][0]["text"]["content"] for block in todos)


def test_build_log_properties_only_writes_provided_keys():
    props = notion.build_log_properties(
        {"date": "2026-09-21", "distance": "2 miles"},
        notion.default_log_schema(),
    )
    assert "Distance" in props
    assert "Protein goal" not in props
    assert "Steps actual" not in props


def test_build_log_properties_can_clear_fields():
    props = notion.build_log_properties({"protein_goal": None}, notion.default_log_schema())
    assert props["Protein goal"] == {"number": None}


def test_build_lift_properties_can_set_actual_weight():
    props = notion.build_lift_properties({"actual_weight": "195"}, notion.default_lift_schema())
    assert props["Actual weight"]["rich_text"][0]["text"]["content"] == "195"
    assert "Name" not in props


def test_parse_lift_page_reads_actual_weight():
    page = {
        "id": "abc",
        "url": "https://www.notion.so/abc",
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "bench press"}]},
            "Date": {"type": "date", "date": {"start": "2026-09-21"}},
            "Goal weight": {"type": "rich_text", "rich_text": [{"plain_text": "185"}]},
            "Actual weight": {"type": "rich_text", "rich_text": [{"plain_text": "195"}]},
            "Reps": {"type": "number", "number": 5},
            "Completed": {"type": "checkbox", "checkbox": True},
            "Week start": {"type": "date", "date": {"start": "2026-09-21"}},
        },
    }
    parsed = notion.parse_lift_page(page, notion.default_lift_schema())
    assert parsed["lift"] == "bench press"
    assert parsed["actual_weight"] == "195"
    assert parsed["completed"] is True
    assert "athlete" not in parsed


async def test_store_lists_and_filters_lifts(monkeypatch):
    pages = [
        {
            "id": "1",
            "properties": {
                "Name": {"type": "title", "title": [{"plain_text": "bench press"}]},
                "Date": {"type": "date", "date": {"start": "2026-09-21"}},
                "Actual weight": {"type": "rich_text", "rich_text": [{"plain_text": "195"}]},
            },
        },
        {
            "id": "2",
            "properties": {
                "Name": {"type": "title", "title": [{"plain_text": "squat"}]},
                "Date": {"type": "date", "date": {"start": "2026-09-22"}},
            },
        },
    ]

    async def fake_request(self, method, path, payload=None):
        if method == "GET" and path.startswith("/databases/"):
            return notion.default_lift_schema()
        if method == "POST" and path.endswith("/query"):
            return {"results": pages, "has_more": False}
        raise AssertionError(path)

    monkeypatch.setattr(
        notion,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "notion_token": "secret",
                "notion_lifts_database_id": "db-lifts",
                "notion_logs_database_id": "",
                "notion_database_id": "db-week",
                "notion_version": "",
                "notion_timeout_seconds": 5,
            },
        )(),
    )
    monkeypatch.setattr(notion.NotionClient, "request", fake_request)
    rows = await notion.NotionStore().list_lifts()
    assert [row["lift"] for row in rows] == ["squat", "bench press"]
    recent = await notion.NotionStore().recent_performance()
    assert {row["lift"]: row.get("actual_weight") for row in recent}["bench press"] == "195"


async def test_assemble_week_from_notion_rows(monkeypatch):
    class FakeStore:
        async def list_lifts(self, **kwargs):
            return [
                {
                    "id": "lift-1",
                    "lift": "bench press",
                    "date": "2026-09-21",
                    "goal_weight": "185",
                    "actual_weight": "195",
                    "reps": 5,
                    "completed": True,
                }
            ]

        async def list_logs(self, **kwargs):
            return [
                {
                    "date": "2026-09-21",
                    "cardio_kind": "walk",
                    "distance": "2 miles",
                    "protein_goal": 160,
                    "steps_goal": 8000,
                }
            ]

    async def fake_videos(names):
        return {
            "bench press": exercisedb.normalize_exercise(
                {"exerciseId": "x", "name": "barbell bench press", "videoUrl": "https://cdn.example/bench.mp4"}
            )
        }

    monkeypatch.setattr(exercisedb, "videos_for_lift_names", fake_videos)
    plan = await weekly_plan_service.assemble_weekly_plan(
        week_start=date(2026, 9, 21),
        store=FakeStore(),
    )
    monday = plan.days[0]
    assert monday.lifts[0].actual_weight == "195"
    assert monday.lifts[0].demo_url.endswith("bench.mp4")
    assert monday.cardio[0].kind == "walk"
    assert len(plan.days) == 7


async def test_publish_dry_run(monkeypatch):
    async def fail(*args, **kwargs):
        raise AssertionError("no Notion calls on dry-run")

    monkeypatch.setattr(notion.NotionClient, "request", fail)
    result = await notion.publish_weekly_plan(_sample_plan(), dry_run=True)
    assert result["dry_run"] is True
    assert result["children"][0]["type"] == "heading_1"


async def test_mcp_publish_from_notion(monkeypatch):
    class FakeStore:
        async def list_lifts(self, **kwargs):
            return [
                {
                    "id": "lift-1",
                    "lift": "deadlift",
                    "date": "2026-09-21",
                    "goal_weight": "315",
                    "actual_weight": None,
                    "reps": 3,
                    "completed": False,
                }
            ]

        async def list_logs(self, **kwargs):
            return []

    monkeypatch.setattr(notion, "NotionStore", FakeStore)
    monkeypatch.setattr(exercisedb, "videos_for_lift_names", lambda names: {})

    result = await mcp.call_tool(
        "publish_weekly_workout_to_notion",
        {"week_start": "2026-09-21", "dry_run": True, "include_videos": False},
    )
    payload = _tool_payload(result)
    assert payload["dry_run"] is True
    todos = [block for block in payload["children"] if block["type"] == "to_do"]
    assert any("deadlift" in block["to_do"]["rich_text"][0]["text"]["content"] for block in todos)


def test_cli_publish_dry_run(tmp_path, capsys, monkeypatch):
    path = tmp_path / "week.json"
    path.write_text(_sample_plan().model_dump_json(), encoding="utf-8")

    async def fake_attach(plan):
        return plan

    monkeypatch.setattr(weekly_plan_service, "attach_videos", fake_attach)
    assert main(["notion", "publish", "--plan", str(path), "--dry-run", "--no-videos"]) == 0
    printed = capsys.readouterr().out
    assert "Week of Sep 21" in printed
    assert '"dry_run": true' in printed
