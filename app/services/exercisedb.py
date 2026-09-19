from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.schemas.exercise import ExerciseVideo

FREE_EXERCISEDB_BASE_URL = "https://oss.exercisedb.dev"
RESOLUTION_PREFERENCE = ("720p", "480p", "360p", "1080p")
CANONICAL_QUERIES = {
    "bench": ["barbell bench press"],
    "bench press": ["barbell bench press"],
    "incline bench": ["barbell incline bench press"],
    "incline bench press": ["barbell incline bench press"],
    "squat": ["barbell squat"],
    "back squat": ["barbell squat"],
    "front squat": ["barbell front squat"],
    "deadlift": ["barbell deadlift"],
    "rdl": ["barbell romanian deadlift"],
    "romanian deadlift": ["barbell romanian deadlift"],
    "ohp": ["overhead press", "barbell seated overhead press"],
    "overhead press": ["barbell seated overhead press"],
    "military press": ["barbell seated overhead press"],
    "row": ["barbell bent over row"],
    "barbell row": ["barbell bent over row"],
    "bent over row": ["barbell bent over row"],
}
KNOWN_EQUIPMENT = {"barbell", "dumbbell", "cable", "smith", "band", "ez", "kettlebell"}


class ExerciseDBError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def exercisedb_source() -> str:
    settings = get_settings()
    if settings.exercisedb_base_url:
        host = urlparse(settings.exercisedb_base_url).netloc or settings.exercisedb_base_url
        return host
    if settings.exercisedb_api_key:
        return settings.exercisedb_api_host
    return "oss.exercisedb.dev"


def _base_url() -> str:
    settings = get_settings()
    if settings.exercisedb_base_url:
        return settings.exercisedb_base_url.rstrip("/")
    if settings.exercisedb_api_key:
        return f"https://{settings.exercisedb_api_host}".rstrip("/")
    return FREE_EXERCISEDB_BASE_URL


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Accept": "application/json"}
    if settings.exercisedb_api_key:
        headers["X-RapidAPI-Key"] = settings.exercisedb_api_key
        headers["X-RapidAPI-Host"] = settings.exercisedb_api_host
    return headers


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _first_resolution(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in RESOLUTION_PREFERENCE:
            url = value.get(key)
            if url:
                return str(url)
        for url in value.values():
            if url:
                return str(url)
    return None


def normalize_exercise(raw: dict[str, Any], *, match_score: int | None = None) -> ExerciseVideo:
    video_url = raw.get("videoUrl") or raw.get("video_url")
    gif_url = raw.get("gifUrl") or raw.get("gif_url") or _first_resolution(raw.get("gifUrls"))
    image_url = raw.get("imageUrl") or raw.get("image_url") or _first_resolution(raw.get("imageUrls"))
    demo_url = video_url or gif_url
    media_kind = "video" if video_url else ("gif" if gif_url else None)
    exercise_type = raw.get("exerciseType") or raw.get("exercise_type")
    if exercise_type is None:
        types = _as_list(raw.get("exerciseTypes"))
        exercise_type = types[0] if types else None
    return ExerciseVideo(
        exercise_id=str(raw.get("exerciseId") or raw.get("exercise_id") or raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        video_url=str(video_url) if video_url else None,
        gif_url=str(gif_url) if gif_url else None,
        image_url=str(image_url) if image_url else None,
        demo_url=str(demo_url) if demo_url else None,
        media_kind=media_kind,
        body_parts=_as_list(raw.get("bodyParts") or raw.get("bodyPart") or raw.get("body_parts")),
        target_muscles=_as_list(raw.get("targetMuscles") or raw.get("target") or raw.get("target_muscles")),
        secondary_muscles=_as_list(raw.get("secondaryMuscles") or raw.get("secondary_muscles")),
        equipments=_as_list(raw.get("equipments") or raw.get("equipment")),
        exercise_type=str(exercise_type) if exercise_type else None,
        instructions=_as_list(raw.get("instructions")),
        overview=raw.get("overview"),
        exercise_tips=_as_list(raw.get("exerciseTips") or raw.get("exercise_tips")),
        variations=_as_list(raw.get("variations")),
        match_score=match_score,
    )


def _normalize_name(value: str) -> str:
    cleaned = value.casefold().replace("(", " ").replace(")", " ").replace("-", " ")
    return " ".join(cleaned.split())


def lookup_queries(query: str) -> list[str]:
    """Original lift name plus canonical ExerciseDB aliases."""
    normalized = _normalize_name(query)
    queries: list[str] = []
    for item in [query.strip(), *CANONICAL_QUERIES.get(normalized, [])]:
        if item and _normalize_name(item) not in {_normalize_name(existing) for existing in queries}:
            queries.append(item)
    first = normalized.split()[0] if normalized else ""
    if first and first not in KNOWN_EQUIPMENT:
        prefixed = f"barbell {normalized}"
        if _normalize_name(prefixed) not in {_normalize_name(existing) for existing in queries}:
            queries.append(prefixed)
    return queries


def score_name_match(query: str, name: str) -> int:
    needle = _normalize_name(query)
    haystack = _normalize_name(name)
    if not needle or not haystack:
        return 0
    if haystack == needle:
        return 100

    query_tokens = needle.split()
    name_tokens = haystack.split()
    extra = max(0, len(name_tokens) - len(query_tokens))
    phrase = any(
        name_tokens[index : index + len(query_tokens)] == query_tokens
        for index in range(0, len(name_tokens) - len(query_tokens) + 1)
    )

    if name_tokens[:1] == ["barbell"] and name_tokens[1:] == query_tokens:
        return 96
    if phrase:
        score = 86 - extra * 8
        if name_tokens[: len(query_tokens)] == query_tokens and extra:
            score -= 10
        if "barbell" in name_tokens:
            score += 8
        return max(20, score)
    if set(query_tokens) <= set(name_tokens):
        return max(15, 55 - extra * 8)
    overlap = set(query_tokens) & set(name_tokens)
    if overlap:
        return max(5, int(30 * len(overlap) / len(query_tokens)) - extra * 2)
    return 0


def _error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if payload.get("message"):
            return str(payload["message"])
        if payload.get("detail"):
            return str(payload["detail"])
    return fallback


async def request_json(path: str, params: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    query = {key: value for key, value in (params or {}).items() if value not in (None, "", [])}
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=settings.exercisedb_timeout_seconds) as client:
            response = await client.get(url, params=query, headers=_headers())
    except httpx.TimeoutException as exc:
        raise ExerciseDBError("ExerciseDB request timed out", 504) from exc
    except httpx.HTTPError as exc:
        raise ExerciseDBError("ExerciseDB request failed", 502) from exc

    payload: Any
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.status_code == 404:
        raise ExerciseDBError(_error_message(payload, "Exercise not found"), 404)
    if response.status_code == 401:
        raise ExerciseDBError("ExerciseDB rejected the API key", 502)
    if response.status_code == 429:
        raise ExerciseDBError("ExerciseDB rate limit exceeded", 429)
    if response.status_code >= 400:
        raise ExerciseDBError(
            _error_message(payload, f"ExerciseDB returned HTTP {response.status_code}"),
            502,
        )
    return payload


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _unwrap_meta_total(payload: Any) -> int | None:
    if isinstance(payload, dict):
        meta = payload.get("meta")
        if isinstance(meta, dict) and meta.get("total") is not None:
            return int(meta["total"])
        if payload.get("total") is not None:
            return int(payload["total"])
    return None


async def _list_exercises(params: dict[str, Any]) -> tuple[list[ExerciseVideo], int | None]:
    payload = await request_json("/api/v1/exercises", params)
    rows = _unwrap_data(payload)
    if not isinstance(rows, list):
        rows = [rows] if rows else []
    exercises = [normalize_exercise(row) for row in rows if isinstance(row, dict)]
    return exercises, _unwrap_meta_total(payload)


async def search_exercises(
    *,
    name: str | None = None,
    body_parts: str | None = None,
    equipments: str | None = None,
    target_muscles: str | None = None,
    exercise_type: str | None = None,
    keywords: str | None = None,
    limit: int = 10,
) -> tuple[list[ExerciseVideo], int | None]:
    limit = max(1, min(limit, 25))
    params = {
        "name": name,
        "bodyParts": body_parts,
        "equipments": equipments,
        "targetMuscles": target_muscles,
        "exerciseType": exercise_type,
        "keywords": keywords,
        "limit": str(limit),
    }
    exercises, total = await _list_exercises(params)
    if not name:
        return exercises, total

    by_id = {item.exercise_id: item for item in exercises if item.exercise_id}
    try:
        for item in await search_exercise_names(name):
            if item.exercise_id and item.exercise_id not in by_id:
                by_id[item.exercise_id] = item
    except ExerciseDBError:
        pass

    best = max((score_name_match(name, item.name) for item in by_id.values()), default=0)
    if best < 90:
        for alias in lookup_queries(name)[1:2]:
            try:
                more, _ = await _list_exercises({**params, "name": alias})
            except ExerciseDBError:
                more = []
            for item in more:
                if item.exercise_id and item.exercise_id not in by_id:
                    by_id[item.exercise_id] = item

    ranked = sorted(
        by_id.values(),
        key=lambda item: score_name_match(name, item.name),
        reverse=True,
    )[:limit]
    return ranked, total


async def search_exercise_names(query: str) -> list[ExerciseVideo]:
    payload = await request_json("/api/v1/exercises/search", {"search": query})
    rows = _unwrap_data(payload)
    if not isinstance(rows, list):
        rows = [rows] if rows else []
    return [
        normalize_exercise(row, match_score=score_name_match(query, str(row.get("name") or "")))
        for row in rows
        if isinstance(row, dict)
    ]


async def get_exercise(exercise_id: str) -> ExerciseVideo:
    if not exercise_id or "/" in exercise_id or ".." in exercise_id:
        raise ExerciseDBError("Invalid exercise id", 400)
    payload = await request_json(f"/api/v1/exercises/{exercise_id}")
    row = _unwrap_data(payload)
    if isinstance(row, list):
        row = row[0] if row else None
    if not isinstance(row, dict):
        raise ExerciseDBError("Exercise not found", 404)
    exercise = normalize_exercise(row)
    if not exercise.exercise_id:
        raise ExerciseDBError("Exercise not found", 404)
    return exercise


async def _with_media(exercise: ExerciseVideo) -> ExerciseVideo:
    if exercise.demo_url:
        return exercise
    if not exercise.exercise_id:
        return exercise
    try:
        detailed = await get_exercise(exercise.exercise_id)
    except ExerciseDBError:
        return exercise
    detailed.match_score = exercise.match_score
    return detailed


async def _candidates_for(query: str) -> list[ExerciseVideo]:
    try:
        named, _ = await search_exercises(name=query, limit=15)
        return named
    except ExerciseDBError:
        try:
            return await search_exercise_names(query)
        except ExerciseDBError:
            return []


async def find_exercise_video(query: str) -> ExerciseVideo | None:
    needle = query.strip()
    if not needle:
        return None

    best: ExerciseVideo | None = None
    best_score = -1
    for lookup in lookup_queries(needle):
        for item in await _candidates_for(lookup):
            score = max(score_name_match(needle, item.name), score_name_match(lookup, item.name))
            scored = item.model_copy(update={"match_score": score})
            if score > best_score or (
                score == best_score and best is not None and scored.demo_url and not best.demo_url
            ):
                best = scored
                best_score = score
        if best_score >= 90:
            break
    if best is None or best_score < 25:
        return None
    return await _with_media(best)


async def videos_for_lift_names(lift_names: list[str]) -> dict[str, ExerciseVideo | None]:
    unique: list[str] = []
    seen: set[str] = set()
    for name in lift_names:
        key = " ".join(name.casefold().split())
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(name)

    results: dict[str, ExerciseVideo | None] = {}
    for name in unique:
        results[name] = await find_exercise_video(name)
    return results
