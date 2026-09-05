WRITABLE_RESOURCES = frozenset({"protein", "steps", "lifting_workouts", "cardio"})
READ_ONLY_RESOURCES = frozenset({"gym_location", "performance_goals", "physic_photos"})

WRITE_TOOL_PREFIXES = ("create_", "update_", "delete_")
WRITE_TOOL_RESOURCES = WRITABLE_RESOURCES
