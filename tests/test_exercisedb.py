from app.mcp.server import mcp
from app.services import exercisedb
from tests.test_mcp import _tool_payload

BENCH = {
    "exerciseId": "exr_bench",
    "name": "Barbell Bench Press",
    "videoUrl": "https://cdn.exercisedb.dev/videos/bench.mp4",
    "bodyParts": ["CHEST"],
    "equipments": ["BARBELL"],
    "exerciseType": "STRENGTH",
}

SQUAT_GIF = {
    "exerciseId": "EIeI8Vf",
    "name": "barbell squat",
    "gifUrl": "https://static.exercisedb.dev/media/EIeI8Vf.gif",
}


def test_normalize_v2_video():
    exercise = exercisedb.normalize_exercise(BENCH)
    assert exercise.demo_url.endswith("bench.mp4")
    assert exercise.media_kind == "video"


def test_normalize_v1_gif():
    exercise = exercisedb.normalize_exercise(SQUAT_GIF)
    assert exercise.demo_url.endswith(".gif")
    assert exercise.media_kind == "gif"


def test_score_name_match_prefers_canonical_lifts():
    assert exercisedb.score_name_match("bench press", "barbell bench press") > exercisedb.score_name_match(
        "bench press", "barbell wide reverse grip bench press horizontal"
    )
    assert exercisedb.score_name_match("squat", "barbell squat") > exercisedb.score_name_match("squat", "squat jerk")


async def test_mcp_search_videos(monkeypatch):
    async def fake_search(**kwargs):
        return [exercisedb.normalize_exercise(BENCH)], 1

    async def fake_get(exercise_id: str):
        return exercisedb.normalize_exercise(BENCH)

    monkeypatch.setattr(exercisedb, "search_exercises", fake_search)
    monkeypatch.setattr(exercisedb, "get_exercise", fake_get)
    searched = await mcp.call_tool("search_exercise_videos", {"name": "bench press"})
    assert _tool_payload(searched)["exercises"][0]["video_url"].endswith("bench.mp4")
    detail = await mcp.call_tool("get_exercise_video", {"exercise_id": "exr_bench"})
    assert _tool_payload(detail)["exercise_id"] == "exr_bench"


async def test_request_json_sends_rapidapi_headers(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"success": True, "data": [BENCH]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, headers=None):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(
        exercisedb,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "exercisedb_api_key": "test-key",
                "exercisedb_api_host": "edb-with-videos-and-images-by-ascendapi.p.rapidapi.com",
                "exercisedb_base_url": "",
                "exercisedb_timeout_seconds": 5,
            },
        )(),
    )
    monkeypatch.setattr(exercisedb.httpx, "AsyncClient", FakeClient)
    payload = await exercisedb.request_json("/api/v1/exercises", {"name": "bench"})
    assert captured["headers"]["X-RapidAPI-Key"] == "test-key"
    assert payload["data"][0]["exerciseId"] == "exr_bench"
