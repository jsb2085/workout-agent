from datetime import date

from app.cli import main
from app.mcp.server import mcp
from app.schemas.weekly_plan import PlannedCardio, PlannedDay, PlannedLift, WeeklyPlan
from app.services import exercisedb, notion, weekly_plan as weekly_plan_service
from tests.conftest import auth_header
from tests.test_mcp import _tool_payload

WORKOUT = {
    "lift": "bench press",
    "goal_weight": "185",
    "reps": 5,
    "actual_weight": "175",
    "completed": False,
    "date_todo": "2026-09-21T10:00:00+00:00",
}

BENCH = exercisedb.normalize_exercise(
    {
        "exerciseId": "exr_bench",
        "name": "barbell bench press",
        "videoUrl": "https://cdn.exercisedb.dev/videos/bench.mp4",
        "exerciseType": "STRENGTH",
    }
)


def _sample_plan() -> WeeklyPlan:
    return WeeklyPlan(
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
        title="Jacob — Week of Sep 21–27",
        focus="bench + squat",
        athlete="Jacob",
        notes="Keep rest times honest.",
        days=[
            PlannedDay(
                date=date(2026, 9, 21),
                focus="Upper",
                lifts=[
                    PlannedLift(
                        lift="bench press",
                        reps=5,
                        goal_weight="185",
                        demo_url="https://cdn.exercisedb.dev/videos/bench.mp4",
                        media_kind="video",
                        exercise_name="barbell bench press",
                    )
                ],
                cardio=[PlannedCardio(kind="walk", distance="2 miles")],
                protein_goal=160,
                steps_goal=8000,
            ),
            PlannedDay(date=date(2026, 9, 22)),
        ],
    )


def test_build_page_is_a_workable_weekly_template():
    children = notion.build_page_children(_sample_plan())
    types = [block["type"] for block in children]
    assert "heading_1" in types
    assert "callout" in types
    assert "to_do" in types
    assert "video" in types
    todos = [block for block in children if block["type"] == "to_do"]
    assert any("bench press" in block["to_do"]["rich_text"][0]["text"]["content"] for block in todos)
    assert any("Walk" in block["to_do"]["rich_text"][0]["text"]["content"] for block in todos)
    headings = [block for block in children if block["type"] == "heading_2"]
    assert any("Monday" in block["heading_2"]["rich_text"][0]["text"]["content"] for block in headings)
    assert any("Tuesday" in block["heading_2"]["rich_text"][0]["text"]["content"] for block in headings)


def test_properties_use_designed_database_schema():
    schema = {
        "properties": {
            "Name": {"type": "title"},
            "Week": {"type": "date"},
            "Status": {"type": "select"},
            "Focus": {"type": "rich_text"},
            "Athlete": {"type": "rich_text"},
        }
    }
    props = notion.build_page_properties(_sample_plan(), schema)
    assert props["Name"]["title"][0]["text"]["content"].startswith("Jacob")
    assert props["Week"]["date"]["start"] == "2026-09-21"
    assert props["Week"]["date"]["end"] == "2026-09-27"
    assert props["Status"]["select"]["name"] == "Planned"
    assert props["Focus"]["rich_text"][0]["text"]["content"] == "bench + squat"


async def test_publish_dry_run_does_not_call_notion(monkeypatch):
    async def fail(*_args, **_kwargs):
        raise AssertionError("should not call Notion on dry-run")

    monkeypatch.setattr(notion.NotionClient, "request", fail)
    result = await notion.publish_weekly_plan(_sample_plan(), dry_run=True)
    assert result["dry_run"] is True
    assert result["url"] is None
    assert result["children"][0]["type"] == "heading_1"


async def test_publish_creates_page_with_children(monkeypatch):
    captured: list[tuple[str, str, dict | None]] = []

    async def fake_request(self, method, path, payload=None):
        captured.append((method, path, payload))
        if method == "GET" and path.startswith("/databases/"):
            return {
                "properties": {
                    "Name": {"type": "title"},
                    "Week": {"type": "date"},
                    "Status": {"type": "select"},
                }
            }
        if method == "POST" and path == "/pages":
            assert payload["parent"]["database_id"] == "db-weekly"
            assert payload["children"]
            return {"id": "page-1", "url": "https://www.notion.so/page-1"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(
        notion,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "notion_token": "secret",
                "notion_database_id": "db-weekly",
                "notion_data_source_id": "",
                "notion_template_id": "",
                "notion_version": "",
                "notion_timeout_seconds": 5,
            },
        )(),
    )
    monkeypatch.setattr(notion.NotionClient, "request", fake_request)
    result = await notion.publish_weekly_plan(_sample_plan())
    assert result["url"] == "https://www.notion.so/page-1"
    assert result["page_id"] == "page-1"
    assert captured[0][0] == "GET"
    assert captured[1][0] == "POST"


async def test_assemble_week_from_saved_workouts(client, alice_token, monkeypatch):
    headers = auth_header(alice_token)
    created = await client.post("/lifting-workouts/", headers=headers, json=WORKOUT)
    assert created.status_code == 201
    await client.post(
        "/cardio/",
        headers=headers,
        json={
            "walk": True,
            "distance": "2 miles",
            "reps": 1,
            "date_todo": "2026-09-21T11:00:00+00:00",
        },
    )

    async def fake_videos(lift_names):
        return {name: BENCH for name in lift_names}

    monkeypatch.setattr(exercisedb, "videos_for_lift_names", fake_videos)

    from app import db as db_module
    from app.services import records

    async with db_module.SessionLocal() as session:
        user = await records.resolve_user(session, email="alice@example.com")
        plan = await weekly_plan_service.assemble_weekly_plan(
            session,
            user,
            week_start=date(2026, 9, 21),
            focus="bench week",
        )
    monday = next(day for day in plan.days if day.date == date(2026, 9, 21))
    assert monday.lifts[0].lift == "bench press"
    assert monday.lifts[0].demo_url.endswith("bench.mp4")
    assert monday.cardio[0].kind == "walk"
    assert len(plan.days) == 7
    assert plan.focus == "bench week"


async def test_mcp_publish_week_dry_run(client, alice_token, monkeypatch):
    created = await client.post(
        "/lifting-workouts/",
        headers=auth_header(alice_token),
        json=WORKOUT,
    )
    assert created.status_code == 201

    async def fake_videos(lift_names):
        return {name: BENCH for name in lift_names}

    monkeypatch.setattr(exercisedb, "videos_for_lift_names", fake_videos)
    result = await mcp.call_tool(
        "publish_weekly_workout_to_notion",
        {
            "email": "alice@example.com",
            "week_start": "2026-09-21",
            "focus": "bench week",
            "dry_run": True,
        },
    )
    payload = _tool_payload(result)
    assert payload["dry_run"] is True
    todos = [block for block in payload["children"] if block["type"] == "to_do"]
    assert any("bench press" in block["to_do"]["rich_text"][0]["text"]["content"] for block in todos)


def test_cli_publish_plan_dry_run(tmp_path, capsys, monkeypatch):
    plan_path = tmp_path / "week.json"
    plan_path.write_text(_sample_plan().model_dump_json(), encoding="utf-8")

    async def fake_attach(plan):
        return plan

    monkeypatch.setattr(weekly_plan_service, "attach_videos", fake_attach)
    assert main(["notion", "publish", "--plan", str(plan_path), "--dry-run", "--no-videos"]) == 0
    printed = capsys.readouterr().out
    assert "Jacob" in printed
    assert "Week of Sep 21" in printed
    assert '"dry_run": true' in printed
