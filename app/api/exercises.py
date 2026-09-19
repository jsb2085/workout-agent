from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.models.lifting_workout import LiftingWorkout
from app.schemas.exercise import (
    ExerciseSearchResponse,
    ExerciseVideo,
    WorkoutExerciseVideo,
    WorkoutExerciseVideosResponse,
)
from app.services import exercisedb, records

router = APIRouter(prefix="/exercises", tags=["exercises"])
workout_video_router = APIRouter(prefix="/lifting-workouts", tags=["lifting-workouts"])


def _raise_exercisedb(exc: exercisedb.ExerciseDBError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/", response_model=ExerciseSearchResponse)
async def search_exercises(
    _user: CurrentUser,
    name: str | None = None,
    body_parts: str | None = None,
    equipments: str | None = None,
    target_muscles: str | None = None,
    exercise_type: str | None = None,
    keywords: str | None = None,
    limit: int = Query(default=10, ge=1, le=25),
):
    """Search ExerciseDB for demonstration videos (MP4 on V2, GIF on the free API)."""
    try:
        exercises, total = await exercisedb.search_exercises(
            name=name,
            body_parts=body_parts,
            equipments=equipments,
            target_muscles=target_muscles,
            exercise_type=exercise_type,
            keywords=keywords,
            limit=limit,
        )
    except exercisedb.ExerciseDBError as exc:
        _raise_exercisedb(exc)
    return ExerciseSearchResponse(source=exercisedb.exercisedb_source(), total=total, exercises=exercises)


@router.get("/for-workouts", response_model=WorkoutExerciseVideosResponse)
async def exercise_videos_for_workouts(
    session: SessionDep,
    user: CurrentUser,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    """Attach ExerciseDB demonstration videos to the current user's lifting workouts."""
    workouts = await records.list_for_user(
        session,
        LiftingWorkout,
        user.id,
        date_field="date_todo",
        date_from=date_from,
        date_to=date_to,
    )
    try:
        videos = await exercisedb.videos_for_lift_names([item.lift for item in workouts])
    except exercisedb.ExerciseDBError as exc:
        _raise_exercisedb(exc)

    rows: list[WorkoutExerciseVideo] = []
    unmatched: list[str] = []
    for item in workouts:
        exercise = videos.get(item.lift)
        if exercise is None:
            unmatched.append(item.lift)
        rows.append(
            WorkoutExerciseVideo(
                workout_id=item.id,
                lift=item.lift,
                query=item.lift,
                workout=records.to_dict(item),
                exercise=exercise,
            )
        )
    return WorkoutExerciseVideosResponse(
        source=exercisedb.exercisedb_source(),
        workouts=rows,
        unmatched=unmatched,
    )


@router.get("/{exercise_id}", response_model=ExerciseVideo)
async def get_exercise(_user: CurrentUser, exercise_id: str):
    """Get one ExerciseDB exercise, including its demonstration video or GIF."""
    try:
        return await exercisedb.get_exercise(exercise_id)
    except exercisedb.ExerciseDBError as exc:
        _raise_exercisedb(exc)


@workout_video_router.get("/{item_id}/exercise-video", response_model=WorkoutExerciseVideo)
async def exercise_video_for_workout(item_id: UUID, session: SessionDep, user: CurrentUser):
    """Look up the ExerciseDB demonstration video for one lifting workout."""
    item = await records.get_for_user(session, LiftingWorkout, user.id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        exercise = await exercisedb.find_exercise_video(item.lift)
    except exercisedb.ExerciseDBError as exc:
        _raise_exercisedb(exc)
    return WorkoutExerciseVideo(
        workout_id=item.id,
        lift=item.lift,
        query=item.lift,
        workout=records.to_dict(item),
        exercise=exercise,
    )
