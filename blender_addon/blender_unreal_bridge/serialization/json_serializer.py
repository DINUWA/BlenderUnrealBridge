"""
JSON Serialization Utilities
----------------------------
Deterministic, safe JSON serialization for Bridge Data Packages.
Guarantees:
  - Valid UTF-8 encoding
  - Stable formatting (2-space indent, sorted keys where appropriate)
  - No NaN or Infinity values (strict JSON standard compliance)
  - Safe conversion of Blender/mathutils numeric types
"""

import json
import math
from typing import Any


class BridgeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder handling Blender mathutils types and ensuring finite numbers."""

    def default(self, o: Any) -> Any:
        # Handle mathutils Vector, Euler, Matrix, Quaternion if passed directly
        if hasattr(o, "to_list"):
            return o.to_list()
        if hasattr(o, "to_tuple"):
            return list(o.to_tuple())
        if hasattr(o, "__iter__") and not isinstance(o, (str, bytes, dict)):
            return list(o)
        return super().default(o)


def serialize_json(data: Any, indent: int = 2) -> str:
    """
    Serialize Python data structures into a deterministic, schema-compliant JSON string.

    Args:
        data: The dictionary or list to serialize.
        indent: Indentation level (default: 2 spaces).

    Returns:
        Deterministic formatted JSON string.

    Raises:
        ValueError: If data contains NaN, Infinity, or cannot be serialized.
    """
    return json.dumps(
        data,
        cls=BridgeJSONEncoder,
        indent=indent,
        ensure_ascii=False,
        allow_nan=False,  # Strict JSON: reject NaN and Infinity
    )
