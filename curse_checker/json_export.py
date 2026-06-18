import json
from dataclasses import asdict, fields, is_dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

from .analyzer import (
    AnalysisReport, CompareReport, NodeExplainReport,
    TraceReport, TraceRoute, TraceStep,
    EntryPoint, RouteEntry,
    UnreachableNode, DeadChoice, UnusedCurse, ConflictingEnding
)


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, str)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_to_jsonable(v) for v in obj)
    if is_dataclass(obj):
        result = {}
        for f in fields(obj):
            val = getattr(obj, f.name)
            result[f.name] = _to_jsonable(val)
        return result
    return str(obj)


def report_to_json(report) -> str:
    return json.dumps(_to_jsonable(report), ensure_ascii=False, indent=2)
