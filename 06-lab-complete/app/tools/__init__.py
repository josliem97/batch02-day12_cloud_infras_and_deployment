from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .clarify.tool import ask_user
from .food_recommendation.tools import filter_and_recommend_food


# Tool registry — keys MUST match the "name" field in artifacts/tools.yaml
# The model sees these names and calls them by name.
TOOL_FUNCTIONS = {
    "clarify": ask_user,
    "food_recommendation": filter_and_recommend_food,
}


def load_tool_declarations(path: Path) -> list[dict[str, Any]]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["tools"]


def to_openai_tools(declarations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": item["name"],
            "description": item.get("description", ""),
            "parameters": item.get("parameters", {"type": "object", "properties": {}}),
        },
    } for item in declarations]
