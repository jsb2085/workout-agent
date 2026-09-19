from app.mcp.permissions import READ_ONLY_RESOURCES, WRITABLE_RESOURCES
from app.mcp.server import mcp
from app.services import exercisedb, notion


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


async def test_mcp_write_tools_only_for_allowed_resources():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    for resource in WRITABLE_RESOURCES:
        prefix = resource.removesuffix("s") if resource.endswith("s") and resource != "steps" else resource
        if resource == "lifting_workouts":
            prefix = "lifting_workout"
        elif resource == "workout_locations":
            prefix = "workout_location"
        elif resource == "body_stats":
            prefix = "body_stats"
        assert f"create_{prefix}" in names
        assert f"update_{prefix}" in names
        assert f"delete_{prefix}" in names

    assert READ_ONLY_RESOURCES == frozenset()
    assert "search_exercise_videos" in names
    assert "get_exercise_video" in names
    assert "publish_weekly_workout_to_notion" in names
    assert "get_recent_lift_performance" in names
    assert "get_planning_context" in names
    assert "create_physic_photo" not in names
    assert "sync_notion_workouts_to_agent" not in names
    assert "resolve_user" not in names


async def test_mcp_create_lift_uses_notion(monkeypatch):
    async def fake_create(self, data):
        return {"id": "lift-1", **data}

    monkeypatch.setattr(notion.NotionStore, "create_lift", fake_create)
    created = await mcp.call_tool(
        "create_lifting_workout",
        {
            "lift": "bench press",
            "goal_weight": "185",
            "reps": 5,
            "date_todo": "2026-09-21",
        },
    )
    payload = _tool_payload(created)
    assert payload["lift"] == "bench press"
    assert payload["actual_weight"] is None
    assert "athlete" not in payload


async def test_mcp_update_lift_actual_weight(monkeypatch):
    async def fake_update(self, item_id, data):
        return {"id": item_id, **data}

    monkeypatch.setattr(notion.NotionStore, "update_lift", fake_update)
    updated = await mcp.call_tool(
        "update_lifting_workout",
        {"item_id": "lift-1", "actual_weight": "195"},
    )
    payload = _tool_payload(updated)
    assert payload["id"] == "lift-1"
    assert payload["actual_weight"] == "195"


async def test_old_rest_routes_are_gone(client):
    assert (await client.get("/physic-photos/")).status_code == 404
    assert (await client.post("/auth/login")).status_code == 404
    assert (await client.get("/exercises")).status_code == 404


async def test_mcp_recent_and_search(monkeypatch):
    async def fake_recent(self):
        return [{"lift": "bench press", "actual_weight": "195", "goal_weight": "185"}]

    async def fake_search(**kwargs):
        return [exercisedb.normalize_exercise({"exerciseId": "exr_bench", "name": "Bench Press", "videoUrl": "https://cdn.example/bench.mp4"})], 1

    monkeypatch.setattr(notion.NotionStore, "recent_performance", fake_recent)
    monkeypatch.setattr(exercisedb, "search_exercises", fake_search)

    recent = await mcp.call_tool("get_recent_lift_performance", {})
    assert _tool_payload(recent)["lifts"][0]["actual_weight"] == "195"

    searched = await mcp.call_tool("search_exercise_videos", {"name": "bench press"})
    assert _tool_payload(searched)["exercises"][0]["demo_url"].endswith("bench.mp4")


async def test_mcp_create_goal_and_context(monkeypatch):
    async def fake_create(self, data):
        return {"id": "goal-1", **data}

    async def fake_context(self):
        return {
            "goals": [{"name": "Bench 225", "target": "225", "status": "Active"}],
            "locations": [{"name": "Home gym", "is_default": True, "equipment": "barbell"}],
            "latest_body_stats": {"weight": "185", "bench": "195"},
            "default_location": {"name": "Home gym", "is_default": True},
        }

    monkeypatch.setattr(notion.NotionStore, "create_goal", fake_create)
    monkeypatch.setattr(notion.NotionStore, "planning_context", fake_context)

    created = await mcp.call_tool("create_goal", {"name": "Bench 225", "target": "225"})
    payload = _tool_payload(created)
    assert payload["name"] == "Bench 225"
    assert payload["status"] == "Active"

    context = await mcp.call_tool("get_planning_context", {})
    assert _tool_payload(context)["latest_body_stats"]["weight"] == "185"
