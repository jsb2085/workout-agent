from app.mcp.server import mcp
from app.services import exercisedb
from tests.conftest import auth_header
from tests.test_mcp import _tool_payload

BENCH = {
    "exerciseId": "exr_bench",
    "name": "Barbell Bench Press",
    "videoUrl": "https://cdn.exercisedb.dev/videos/bench.mp4",
    "imageUrl": "https://cdn.exercisedb.dev/media/images/bench.webp",
    "bodyParts": ["CHEST"],
    "targetMuscles": ["PECTORALIS MAJOR"],
    "secondaryMuscles": ["TRICEPS BRACHII"],
    "equipments": ["BARBELL"],
    "exerciseType": "STRENGTH",
    "instructions": ["Grip the bar.", "Lower to the chest.", "Press up."],
    "overview": "A classic chest press.",
}

SQUAT_GIF = {
    "exerciseId": "EIeI8Vf",
    "name": "barbell squat",
    "gifUrl": "https://static.exercisedb.dev/media/EIeI8Vf.gif",
    "bodyParts": ["upper legs"],
    "targetMuscles": ["quads"],
    "secondaryMuscles": ["glutes"],
    "equipments": ["barbell"],
    "instructions": ["Stand with the bar.", "Squat down.", "Stand back up."],
}

WORKOUT = {
    "lift": "bench press",
    "goal_weight": "185",
    "reps": 5,
    "actual_weight": "175",
    "completed": False,
    "date_todo": "2026-09-05T10:00:00+00:00",
}


def test_normalize_v2_video():
    exercise = exercisedb.normalize_exercise(BENCH)
    assert exercise.exercise_id == "exr_bench"
    assert exercise.video_url.endswith("bench.mp4")
    assert exercise.demo_url == exercise.video_url
    assert exercise.media_kind == "video"
    assert exercise.body_parts == ["CHEST"]
    assert exercise.equipments == ["BARBELL"]


def test_normalize_v1_gif():
    exercise = exercisedb.normalize_exercise(SQUAT_GIF)
    assert exercise.gif_url.endswith(".gif")
    assert exercise.video_url is None
    assert exercise.demo_url == exercise.gif_url
    assert exercise.media_kind == "gif"


async def test_find_exercise_video_ranks_and_fills_media(monkeypatch):
    async def fake_search(**kwargs):
        return [
            exercisedb.normalize_exercise({"exerciseId": "exr_fly", "name": "cable fly"}),
            exercisedb.normalize_exercise({"exerciseId": "exr_bench", "name": "barbell bench press"}),
        ], 2

    async def fake_get(exercise_id: str):
        assert exercise_id == "exr_bench"
        return exercisedb.normalize_exercise(BENCH)

    monkeypatch.setattr(exercisedb, "search_exercises", fake_search)
    monkeypatch.setattr(exercisedb, "get_exercise", fake_get)

    match = await exercisedb.find_exercise_video("bench press")
    assert match is not None
    assert match.exercise_id == "exr_bench"
    assert match.demo_url.endswith("bench.mp4")


async def test_request_json_uses_free_host_without_key(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"success": True, "data": [SQUAT_GIF]}

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
                "exercisedb_api_key": "",
                "exercisedb_api_host": "edb-with-videos-and-images-by-ascendapi.p.rapidapi.com",
                "exercisedb_base_url": "",
                "exercisedb_timeout_seconds": 5,
            },
        )(),
    )
    monkeypatch.setattr(exercisedb.httpx, "AsyncClient", FakeClient)
    await exercisedb.request_json("/api/v1/exercises/search", {"search": "squat"})
    assert captured["url"].startswith("https://oss.exercisedb.dev/")
    assert "X-RapidAPI-Key" not in captured["headers"]


def test_score_name_match_prefers_canonical_lifts():
    assert exercisedb.score_name_match("bench press", "barbell bench press") > exercisedb.score_name_match(
        "bench press", "barbell wide reverse grip bench press horizontal"
    )
    assert exercisedb.score_name_match("squat", "barbell squat") > exercisedb.score_name_match(
        "squat", "squat to overhead reach with twist"
    )
    assert exercisedb.score_name_match("squat", "barbell squat") > exercisedb.score_name_match("squat", "squat jerk")
    assert exercisedb.score_name_match("deadlift", "barbell deadlift") > exercisedb.score_name_match(
        "deadlift", "barbell sumo deadlift"
    )
    assert exercisedb.score_name_match("squat", "squat") == 100


def test_lookup_queries_adds_barbell_aliases():
    queries = [item.casefold() for item in exercisedb.lookup_queries("bench press")]
    assert "barbell bench press" in queries
    assert "bench press" in queries


async def test_search_exercises_merges_canonical_alias(monkeypatch):
    async def fake_list(params):
        name = (params.get("name") or "").casefold()
        if name == "barbell bench press":
            return [exercisedb.normalize_exercise(BENCH)], 1
        return [exercisedb.normalize_exercise({"exerciseId": "exr_incline", "name": "barbell incline bench press"})], 8

    async def fail_search(_query: str):
        raise exercisedb.ExerciseDBError("worker limit", 502)

    monkeypatch.setattr(exercisedb, "_list_exercises", fake_list)
    monkeypatch.setattr(exercisedb, "search_exercise_names", fail_search)
    exercises, _total = await exercisedb.search_exercises(name="bench press", limit=5)
    assert exercises[0].exercise_id == "exr_bench"
    assert exercises[0].demo_url.endswith("bench.mp4")


async def test_search_exercises_requires_auth(client):
    response = await client.get("/exercises/", params={"name": "bench press"})
    assert response.status_code == 401


async def test_search_exercises_returns_videos(client, alice_token, monkeypatch):
    async def fake_search(**kwargs):
        return [exercisedb.normalize_exercise(BENCH)], 1

    monkeypatch.setattr(exercisedb, "search_exercises", fake_search)
    response = await client.get(
        "/exercises/",
        params={"name": "bench press"},
        headers=auth_header(alice_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exercises"][0]["name"] == "Barbell Bench Press"
    assert body["exercises"][0]["demo_url"].endswith("bench.mp4")
    assert body["exercises"][0]["media_kind"] == "video"


async def test_get_exercise_by_id(client, alice_token, monkeypatch):
    async def fake_get(exercise_id: str):
        assert exercise_id == "exr_bench"
        return exercisedb.normalize_exercise(BENCH)

    monkeypatch.setattr(exercisedb, "get_exercise", fake_get)
    response = await client.get("/exercises/exr_bench", headers=auth_header(alice_token))
    assert response.status_code == 200
    assert response.json()["video_url"].endswith("bench.mp4")


async def test_get_exercise_not_found(client, alice_token, monkeypatch):
    async def fake_get(_exercise_id: str):
        raise exercisedb.ExerciseDBError("Exercise not found", 404)

    monkeypatch.setattr(exercisedb, "get_exercise", fake_get)
    response = await client.get("/exercises/missing", headers=auth_header(alice_token))
    assert response.status_code == 404


async def test_workout_videos_match_saved_lifts(client, alice_token, monkeypatch):
    headers = auth_header(alice_token)
    created = await client.post("/lifting-workouts/", headers=headers, json=WORKOUT)
    assert created.status_code == 201
    workout_id = created.json()["id"]

    async def fake_videos(lift_names):
        assert "bench press" in lift_names
        return {"bench press": exercisedb.normalize_exercise(BENCH)}

    monkeypatch.setattr(exercisedb, "videos_for_lift_names", fake_videos)
    response = await client.get("/exercises/for-workouts", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unmatched"] == []
    assert body["workouts"][0]["workout_id"] == workout_id
    assert body["workouts"][0]["exercise"]["demo_url"].endswith("bench.mp4")

    async def fake_find(query: str):
        assert query == "bench press"
        return exercisedb.normalize_exercise(BENCH)

    monkeypatch.setattr(exercisedb, "find_exercise_video", fake_find)
    one = await client.get(f"/lifting-workouts/{workout_id}/exercise-video", headers=headers)
    assert one.status_code == 200
    assert one.json()["exercise"]["exercise_id"] == "exr_bench"


async def test_bob_cannot_fetch_alice_workout_video(client, alice_token, bob_token, monkeypatch):
    created = await client.post(
        "/lifting-workouts/",
        headers=auth_header(alice_token),
        json=WORKOUT,
    )
    workout_id = created.json()["id"]

    async def fail_if_called(_query: str):
        raise AssertionError("should not look up ExerciseDB for another user's workout")

    monkeypatch.setattr(exercisedb, "find_exercise_video", fail_if_called)
    response = await client.get(
        f"/lifting-workouts/{workout_id}/exercise-video",
        headers=auth_header(bob_token),
    )
    assert response.status_code == 404


async def test_mcp_search_and_workout_videos(client, alice_token, monkeypatch):
    created = await mcp.call_tool(
        "create_lifting_workout",
        {
            "email": "alice@example.com",
            **WORKOUT,
        },
    )
    payload = _tool_payload(created)
    if isinstance(payload, list):
        payload = payload[0]
    assert payload["lift"] == "bench press"

    async def fake_search(**kwargs):
        return [exercisedb.normalize_exercise(BENCH)], 12

    async def fake_get(exercise_id: str):
        return exercisedb.normalize_exercise(BENCH)

    async def fake_videos(lift_names):
        return {name: exercisedb.normalize_exercise(BENCH) for name in lift_names}

    monkeypatch.setattr(exercisedb, "search_exercises", fake_search)
    monkeypatch.setattr(exercisedb, "get_exercise", fake_get)
    monkeypatch.setattr(exercisedb, "videos_for_lift_names", fake_videos)

    searched = await mcp.call_tool("search_exercise_videos", {"name": "bench press"})
    search_body = _tool_payload(searched)
    assert search_body["exercises"][0]["video_url"].endswith("bench.mp4")

    detail = await mcp.call_tool("get_exercise_video", {"exercise_id": "exr_bench"})
    detail_body = _tool_payload(detail)
    assert detail_body["exercise_id"] == "exr_bench"

    attached = await mcp.call_tool("get_workout_exercise_videos", {"email": "alice@example.com"})
    attached_body = _tool_payload(attached)
    assert attached_body["unmatched"] == []
    assert attached_body["workouts"][0]["exercise"]["demo_url"].endswith("bench.mp4")


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
            captured["params"] = params
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(exercisedb, "get_settings", lambda: type(
        "S",
        (),
        {
            "exercisedb_api_key": "test-key",
            "exercisedb_api_host": "edb-with-videos-and-images-by-ascendapi.p.rapidapi.com",
            "exercisedb_base_url": "",
            "exercisedb_timeout_seconds": 5,
        },
    )())
    monkeypatch.setattr(exercisedb.httpx, "AsyncClient", FakeClient)

    payload = await exercisedb.request_json("/api/v1/exercises", {"name": "bench"})
    assert payload["data"][0]["exerciseId"] == "exr_bench"
    assert captured["url"].startswith("https://edb-with-videos-and-images-by-ascendapi.p.rapidapi.com/")
    assert captured["headers"]["X-RapidAPI-Key"] == "test-key"
    assert captured["headers"]["X-RapidAPI-Host"] == "edb-with-videos-and-images-by-ascendapi.p.rapidapi.com"
