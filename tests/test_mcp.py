from datetime import date

from app.mcp.permissions import READ_TOOLS, WRITE_TOOLS
from app.mcp.server import mcp
from app.schemas.weekly_plan import PlannedDay, PlannedLift, WeeklyPlan
from app.services import exercisedb, weekly_plan as weekly_plan_service


def _sample_plan() -> WeeklyPlan:
    return WeeklyPlan(
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
        title="Week of Sep 21–27",
        days=[
            PlannedDay(
                date=date(2026, 9, 21),
                lifts=[PlannedLift(lift="bench press", reps=5, goal_weight="185")],
            )
        ],
    )


def _tool_payload(result):
    payload = result.structured_content
    if payload is None and result.content:
        payload = result.content
    if isinstance(payload, dict) and "result" in payload and len(payload) == 1:
        payload = payload["result"]
    return payload


async def test_mcp_requires_agent_token(client):
    response = await client.get("/mcp")
    assert response.status_code == 401


async def test_mcp_accepts_agent_token(client, mcp_header):
    response = await client.get("/mcp", headers=mcp_header)
    assert response.status_code != 401


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_mcp_exposes_pull_and_push_only():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert WRITE_TOOLS <= names
    assert READ_TOOLS <= names
    assert names == WRITE_TOOLS | READ_TOOLS
    assert "create_lifting_workout" not in names
    assert "create_goal" not in names
    assert "publish_weekly_workout_to_notion" not in names


async def test_old_rest_routes_are_gone(client):
    assert (await client.get("/physic-photos/")).status_code == 404
    assert (await client.post("/auth/login")).status_code == 404
    assert (await client.get("/exercises")).status_code == 404


async def test_mcp_pull_and_push(monkeypatch):
    class FakeStore:
        async def planning_context(self):
            return {
                "goals": [{"name": "Bench 225", "target": "225", "status": "Active"}],
                "locations": [{"name": "Home gym", "is_default": True}],
                "default_location": {"name": "Home gym", "is_default": True},
                "latest_body_stats": {"weight": "185", "bench": "195"},
            }

        async def recent_performance(self):
            return [{"lift": "bench press", "actual_weight": "195", "goal_weight": "185"}]

        async def list_lifts(self, **kwargs):
            return []

        async def list_logs(self, **kwargs):
            return []

    monkeypatch.setattr(weekly_plan_service.notion, "NotionStore", FakeStore)
    pulled = await mcp.call_tool("pull_planning_context", {"week_start": "2026-09-21"})
    payload = _tool_payload(pulled)
    assert payload["recent_lifts"][0]["actual_weight"] == "195"
    assert payload["goals"][0]["name"] == "Bench 225"

    async def fake_push(plan, **kwargs):
        return {"dry_run": True, "title": plan.title, "lift_count": 1}

    monkeypatch.setattr(weekly_plan_service, "push_plan", fake_push)
    pushed = await mcp.call_tool(
        "push_weekly_plan",
        {"plan_json": _sample_plan().model_dump_json(), "dry_run": True, "include_videos": False},
    )
    assert _tool_payload(pushed)["dry_run"] is True


async def test_mcp_search_videos(monkeypatch):
    async def fake_search(**kwargs):
        return [
            exercisedb.normalize_exercise(
                {"exerciseId": "exr_bench", "name": "Bench Press", "videoUrl": "https://cdn.example/bench.mp4"}
            )
        ], 1

    monkeypatch.setattr(exercisedb, "search_exercises", fake_search)
    searched = await mcp.call_tool("search_exercise_videos", {"name": "bench press"})
    assert _tool_payload(searched)["exercises"][0]["demo_url"].endswith("bench.mp4")
