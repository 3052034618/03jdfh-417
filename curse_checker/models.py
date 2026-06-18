"""
核心数据模型定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class RhythmType(Enum):
    """恐怖节奏类型"""
    CALM = "平静"
    UNSETTLE = "异常"
    CHASE = "追逐"
    REVEAL = "揭露"
    BREAKDOWN = "崩坏"

    @classmethod
    def from_string(cls, value: str) -> "RhythmType":
        mapping = {
            "平静": cls.CALM,
            "异常": cls.UNSETTLE,
            "追逐": cls.CHASE,
            "揭露": cls.REVEAL,
            "崩坏": cls.BREAKDOWN,
        }
        if value not in mapping:
            raise ValueError(f"未知的节奏类型: {value}")
        return mapping[value]


class CurseOperation(Enum):
    """诅咒标记操作类型"""
    ADD = "add"
    REMOVE = "remove"
    INCREASE = "increase"
    DECREASE = "decrease"

    @classmethod
    def from_string(cls, value: str) -> "CurseOperation":
        mapping = {
            "+": cls.ADD,
            "-": cls.REMOVE,
            "++": cls.INCREASE,
            "--": cls.DECREASE,
        }
        if value not in mapping:
            raise ValueError(f"未知的诅咒操作: {value}")
        return mapping[value]


@dataclass
class CurseEffect:
    """诅咒效果"""
    name: str
    operation: CurseOperation
    level: int = 1


@dataclass
class Condition:
    """选项/跳转条件"""
    curse_name: str
    min_level: int = 1
    max_level: Optional[int] = None
    required: bool = True  # True=需要存在, False=需要不存在


@dataclass
class Choice:
    """选项"""
    id: str
    text: str
    target_node: str
    conditions: List[Condition] = field(default_factory=list)
    curse_effects: List[CurseEffect] = field(default_factory=list)
    is_mislead: bool = False


@dataclass
class Node:
    """剧情节点"""
    id: str
    chapter: str
    title: str
    content: str
    rhythm: RhythmType
    is_ending: bool = False
    is_start: bool = False
    choices: List[Choice] = field(default_factory=list)
    curse_effects: List[CurseEffect] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    next_node: Optional[str] = None  # 无选项时的自动跳转
    tags: Set[str] = field(default_factory=set)


@dataclass
class Chapter:
    """章节"""
    id: str
    title: str
    nodes: Dict[str, Node] = field(default_factory=dict)


@dataclass
class Script:
    """完整剧本"""
    title: str
    chapters: Dict[str, Chapter] = field(default_factory=dict)
    all_nodes: Dict[str, Node] = field(default_factory=dict)
    curse_definitions: Dict[str, str] = field(default_factory=dict)  # 诅咒名称 -> 描述

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.all_nodes.get(node_id)

    def get_start_nodes(self) -> List[Node]:
        return [n for n in self.all_nodes.values() if n.is_start]
