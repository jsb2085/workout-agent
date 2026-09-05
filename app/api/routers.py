from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.crud import crud_router
from app.api.physic_photos import router as physic_photos_router
from app.models.cardio import Cardio
from app.models.gym_location import GymLocation
from app.models.lifting_workout import LiftingWorkout
from app.models.performance_goal import PerformanceGoal
from app.models.protein import Protein
from app.models.steps import Steps
from app.schemas.cardio import CardioCreate, CardioRead, CardioUpdate
from app.schemas.gym_location import GymLocationCreate, GymLocationRead, GymLocationUpdate
from app.schemas.lifting_workout import LiftingWorkoutCreate, LiftingWorkoutRead, LiftingWorkoutUpdate
from app.schemas.performance_goal import (
    PerformanceGoalCreate,
    PerformanceGoalRead,
    PerformanceGoalUpdate,
)
from app.schemas.protein import ProteinCreate, ProteinRead, ProteinUpdate
from app.schemas.steps import StepsCreate, StepsRead, StepsUpdate

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(
    crud_router(
        LiftingWorkout,
        LiftingWorkoutCreate,
        LiftingWorkoutUpdate,
        LiftingWorkoutRead,
        prefix="/lifting-workouts",
        tags=["lifting-workouts"],
        date_field="date_todo",
    )
)
api_router.include_router(
    crud_router(
        Cardio,
        CardioCreate,
        CardioUpdate,
        CardioRead,
        prefix="/cardio",
        tags=["cardio"],
        date_field="date_todo",
    )
)
api_router.include_router(
    crud_router(
        GymLocation,
        GymLocationCreate,
        GymLocationUpdate,
        GymLocationRead,
        prefix="/gym-locations",
        tags=["gym-locations"],
    )
)
api_router.include_router(
    crud_router(
        PerformanceGoal,
        PerformanceGoalCreate,
        PerformanceGoalUpdate,
        PerformanceGoalRead,
        prefix="/performance-goals",
        tags=["performance-goals"],
    )
)
api_router.include_router(physic_photos_router)
api_router.include_router(
    crud_router(
        Protein,
        ProteinCreate,
        ProteinUpdate,
        ProteinRead,
        prefix="/protein",
        tags=["protein"],
        date_field="date_todo",
    )
)
api_router.include_router(
    crud_router(
        Steps,
        StepsCreate,
        StepsUpdate,
        StepsRead,
        prefix="/steps",
        tags=["steps"],
        date_field="date_todo",
    )
)
