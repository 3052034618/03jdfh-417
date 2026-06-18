"""
随机游玩路径生成器
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .analyzer import CurseState
from .models import Choice, CurseOperation, Node, Script


@dataclass
class CurseProgression:
    """诅咒升级历程"""
    curse_name: str
    description: str
    levels: List[Tuple[int, str]]  # (等级, 获得/升级的节点ID)


@dataclass
class MisleadEvent:
    """关键误导事件"""
    node_id: str
    node_title: str
    choice_id: str
    choice_text: str
    actual_target: str


@dataclass
class PathSummary:
    """游玩路径摘要"""
    path: List[str]
    node_titles: List[str]
    curse_progressions: Dict[str, CurseProgression]
    misleads: List[MisleadEvent]
    ending_node: Optional[str]
    ending_title: str
    total_nodes: int
    key_moments: List[str]


@dataclass
class GeneratedPlaythrough:
    """生成的游玩记录"""
    summaries: List[PathSummary] = field(default_factory=list)


class PathGenerator:
    """随机游玩路径生成器"""

    def __init__(self, script: Script, seed: Optional[int] = None):
        self.script = script
        if seed is not None:
            random.seed(seed)
        self.max_path_length = 100

    def generate(self, count: int = 3) -> GeneratedPlaythrough:
        """生成多条随机游玩路径"""
        result = GeneratedPlaythrough()

        for _ in range(count):
            summary = self._generate_single_path()
            if summary:
                result.summaries.append(summary)

        return result

    def _generate_single_path(self) -> Optional[PathSummary]:
        """生成单条随机游玩路径"""
        start_nodes = self.script.get_start_nodes()
        if not start_nodes:
            return None

        start_node = random.choice(start_nodes)
        current_node_id = start_node.id
        current_curse_state = CurseState()
        visited = set()

        path: List[str] = []
        node_titles: List[str] = []
        curse_progressions: Dict[str, CurseProgression] = {}
        misleads: List[MisleadEvent] = []
        key_moments: List[str] = []

        depth = 0
        while depth < self.max_path_length and current_node_id and current_node_id not in visited:
            visited.add(current_node_id)
            node = self.script.get_node(current_node_id)
            if not node:
                break

            path.append(current_node_id)
            title = node.title or current_node_id
            node_titles.append(title)

            if node.is_start:
                key_moments.append(f"【开始】{title}")

            if node.is_ending:
                key_moments.append(f"【结局】{title}")
                break

            for effect in node.curse_effects:
                old_level = current_curse_state.curses.get(effect.name, 0)
                current_curse_state.apply_effect(effect)
                new_level = current_curse_state.curses.get(effect.name, 0)

                if effect.operation in (CurseOperation.ADD, CurseOperation.INCREASE):
                    if effect.name not in curse_progressions:
                        desc = self.script.curse_definitions.get(effect.name, "")
                        curse_progressions[effect.name] = CurseProgression(
                            curse_name=effect.name,
                            description=desc,
                            levels=[]
                        )
                    curse_progressions[effect.name].levels.append(
                        (new_level, current_node_id)
                    )

                    if old_level == 0 and new_level > 0:
                        key_moments.append(f"【诅咒获得】{effect.name} - {title}")
                    elif new_level > old_level:
                        key_moments.append(f"【诅咒升级】{effect.name} Lv.{new_level} - {title}")

            valid_choices = []
            for c in node.choices:
                if current_curse_state.check_conditions(c.conditions):
                    choice_curse_state = current_curse_state.copy()
                    for effect in c.curse_effects:
                        choice_curse_state.apply_effect(effect)
                    target_node = self.script.get_node(c.target_node)
                    if target_node and choice_curse_state.check_conditions(target_node.conditions):
                        valid_choices.append((c, choice_curse_state))

            if valid_choices:
                choice, choice_curse_state = random.choice(valid_choices)

                for effect in choice.curse_effects:
                    old_level = current_curse_state.curses.get(effect.name, 0)
                    current_curse_state.apply_effect(effect)
                    new_level = current_curse_state.curses.get(effect.name, 0)

                    if effect.operation in (CurseOperation.ADD, CurseOperation.INCREASE):
                        if effect.name not in curse_progressions:
                            desc = self.script.curse_definitions.get(effect.name, "")
                            curse_progressions[effect.name] = CurseProgression(
                                curse_name=effect.name,
                                description=desc,
                                levels=[]
                            )
                        curse_progressions[effect.name].levels.append(
                            (new_level, f"{current_node_id}.{choice.id}")
                        )

                        if old_level == 0 and new_level > 0:
                            key_moments.append(f"【诅咒获得】{effect.name} - 选择「{choice.text}」")
                        elif new_level > old_level:
                            key_moments.append(f"【诅咒升级】{effect.name} Lv.{new_level} - 选择「{choice.text}」")

                if choice.is_mislead:
                    target_node = self.script.get_node(choice.target_node)
                    misleads.append(MisleadEvent(
                        node_id=current_node_id,
                        node_title=title,
                        choice_id=choice.id,
                        choice_text=choice.text,
                        actual_target=target_node.title if target_node and target_node.title else choice.target_node
                    ))
                    key_moments.append(f"【误导】选择了「{choice.text}」，实际通向...")

                current_node_id = choice.target_node
            elif node.next_node:
                target_node = self.script.get_node(node.next_node)
                if target_node and current_curse_state.check_conditions(target_node.conditions):
                    current_node_id = node.next_node
                else:
                    break
            else:
                break

            depth += 1

        ending_node = path[-1] if path else None
        ending_node_obj = self.script.get_node(ending_node) if ending_node else None
        ending_title = ending_node_obj.title if ending_node_obj and ending_node_obj.title else (ending_node or "未知")

        return PathSummary(
            path=path,
            node_titles=node_titles,
            curse_progressions=curse_progressions,
            misleads=misleads,
            ending_node=ending_node,
            ending_title=ending_title,
            total_nodes=len(path),
            key_moments=key_moments
        )
