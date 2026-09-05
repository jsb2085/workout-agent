from app.schemas.auth import GoogleLoginRequest, TokenResponse
from app.schemas.cardio import CardioCreate, CardioRead, CardioUpdate
from app.schemas.gym_location import GymLocationCreate, GymLocationRead, GymLocationUpdate
from app.schemas.lifting_workout import LiftingWorkoutCreate, LiftingWorkoutRead, LiftingWorkoutUpdate
from app.schemas.performance_goal import PerformanceGoalCreate, PerformanceGoalRead, PerformanceGoalUpdate
from app.schemas.physic_photo import PhysicPhotoRead, PhysicPhotoUpdate, PhysicPhotoUrl
from app.schemas.protein import ProteinCreate, ProteinRead, ProteinUpdate
from app.schemas.steps import StepsCreate, StepsRead, StepsUpdate
from app.schemas.user import UserRead

__all__ = [
    "CardioCreate",
    "CardioRead",
    "CardioUpdate",
    "GoogleLoginRequest",
    "GymLocationCreate",
    "GymLocationRead",
    "GymLocationUpdate",
    "LiftingWorkoutCreate",
    "LiftingWorkoutRead",
    "LiftingWorkoutUpdate",
    "PerformanceGoalCreate",
    "PerformanceGoalRead",
    "PerformanceGoalUpdate",
    "PhysicPhotoRead",
    "PhysicPhotoUpdate",
    "PhysicPhotoUrl",
    "ProteinCreate",
    "ProteinRead",
    "ProteinUpdate",
    "StepsCreate",
    "StepsRead",
    "StepsUpdate",
    "TokenResponse",
    "UserRead",
]
