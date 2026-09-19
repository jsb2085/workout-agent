WRITABLE_RESOURCES = frozenset(
    {"protein", "steps", "lifting_workouts", "cardio", "goals", "workout_locations", "body_stats"}
)
READ_ONLY_RESOURCES = frozenset()

WRITE_TOOL_PREFIXES = ("create_", "update_", "delete_")
WRITE_TOOL_RESOURCES = WRITABLE_RESOURCES
