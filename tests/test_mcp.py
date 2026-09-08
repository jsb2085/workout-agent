from app.mcp.permissions import READ_ONLY_RESOURCES, WRITABLE_RESOURCES
from app.mcp.server import mcp


async def test_mcp_requires_agent_token(client):
    response = await client.get("/mcp")
    assert response.status_code == 401


async def test_mcp_accepts_agent_token(client, mcp_header):
    response = await client.get("/mcp", headers=mcp_header)
    assert response.status_code != 401


async def test_mcp_write_tools_only_for_allowed_resources():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    for resource in WRITABLE_RESOURCES:
        prefix = resource.removesuffix("s") if resource.endswith("s") and resource != "steps" else resource
        # lifting_workouts -> lifting_workout; cardio/protein/steps stay
        if resource == "lifting_workouts":
            prefix = "lifting_workout"
        assert f"create_{prefix}" in names
        assert f"update_{prefix}" in names
        assert f"delete_{prefix}" in names

    forbidden = {
        "create_gym_location",
        "update_gym_location",
        "delete_gym_location",
        "create_performance_goal",
        "update_performance_goal",
        "delete_performance_goal",
        "create_physic_photo",
        "update_physic_photo",
        "delete_physic_photo",
        "create_body_stats",
        "update_body_stats",
        "delete_body_stats",
    }
    assert forbidden.isdisjoint(names)
    assert READ_ONLY_RESOURCES == frozenset(
        {"gym_location", "performance_goals", "physic_photos", "body_stats"}
    )
    assert "list_gym_locations" in names
    assert "list_performance_goals" in names
    assert "list_physic_photos" in names
    assert "get_physique_comparison_photos" in names
    assert "get_physic_photo_url" in names
    assert "list_body_stats" in names
    assert "get_body_stats" in names


def _tool_payload(result):
    payload = result.structured_content
    if payload is None and result.content:
        payload = result.content
    if isinstance(payload, dict) and "result" in payload and len(payload) == 1:
        payload = payload["result"]
    return payload


async def test_mcp_can_write_protein_for_user(client, alice_token):
    created = await mcp.call_tool(
        "create_protein",
        {
            "email": "alice@example.com",
            "grams_goal": 150,
            "grams_actual": 90,
            "date_todo": "2026-09-05T18:00:00+00:00",
        },
    )
    payload = _tool_payload(created)
    if isinstance(payload, list):
        payload = payload[0]
    assert payload["grams_goal"] == 150
    item_id = payload["id"]

    listed = await mcp.call_tool("list_protein", {"email": "alice@example.com"})
    listed_data = _tool_payload(listed)
    if isinstance(listed_data, dict) and "id" in listed_data:
        listed_rows = [listed_data]
    else:
        listed_rows = listed_data
    assert any(row["id"] == item_id for row in listed_rows)
