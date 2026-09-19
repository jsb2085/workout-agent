from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any


def schema_path() -> Path:
    return Path(str(files("app.notion_import").joinpath("schema.json")))


@lru_cache
def load_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))
