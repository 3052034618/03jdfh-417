"""
剧情分析核心引擎
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    Choice, Condition, CurseEffect, CurseOperation,
    Node, Script
)


@dataclass
class UnreachableNode:
    """不可达节点信息"""
    node_id: str
    title: str
    chapter: str


@dataclass
class DeadChoice:
    """永远无法到达的选项"""
    node_id: str
    choice_id: str
    text: str
    reason: str


@dataclass
class UnusedCurse:
    """未使用的诅咒标记"""
    curse_name: str
    description: str
    set_by: List[str]  # 设置该诅咒的节点/选项
    never_checked: bool  # 是否从未被检查
    never_effective: bool  # 是否从未影响剧情


@dataclass
class ConflictingEnding:
    """冲突的结局"""
    ending1: str
    ending2: str
    conflict_type: str
    details: str


@dataclass
class AnalysisReport:
    """分析报告"""
    unreachable_nodes: List[UnreachableNode] = field(default_factory=list)
    dead_choices: List[DeadChoice] = field(default_factory=list)
    unused_curses: List[UnusedCurse] = field(default_factory=list)
    conflicting_endings: List[ConflictingEnding] = field(default_factory=list)
    total_nodes: int = 0
    total_choices: int = 0
    total_endings: int = 0


class CurseState:
    """诅咒状态"""

    def __init__(self):
        self.curses: Dict[str, int] = {}

    def copy(self) -> "CurseState":
        new_state = CurseState()
        new_state.curses = dict(self.curses)
        return new_state

    def apply_effect(self, effect: CurseEffect) -> None:
        if effect.operation == CurseOperation.ADD:
            self.curses[effect.name] = max(
                self.curses.get(effect.name, 0),
                effect.level
            )
        elif effect.operation == CurseOperation.REMOVE:
            if effect.name in self.curses:
                del self.curses[effect.name]
        elif effect.operation == CurseOperation.INCREASE:
            self.curses[effect.name] = self.curses.get(effect.name, 0) + effect.level
        elif effect.operation == CurseOperation.DECREASE:
            if effect.name in self.curses:
                self.curses[effect.name] = max(0, self.curses[effect.name] - effect.level)
                if self.curses[effect.name] == 0:
                    del self.curses[effect.name]

    def check_condition(self, condition: Condition) -> bool:
        current_level = self.curses.get(condition.curse_name, 0)
        if condition.required:
            if current_level == 0:
                return False
            if current_level < condition.min_level:
                return False
            if condition.max_level is not None and current_level > condition.max_level:
                return False
            return True
        else:
            return current_level == 0

    def check_conditions(self, conditions: List[Condition]) -> bool:
        return all(self.check_condition(c) for c in conditions)


class ScriptAnalyzer:
    """剧本分析器"""

    def __init__(self, script: Script):
        self.script = script
        self.report = AnalysisReport()
        self.report.total_nodes = len(script.all_nodes)
        self.report.total_choices = sum(len(n.choices) for n in script.all_nodes.values())
        self.report.total_endings = sum(1 for n in script.all_nodes.values() if n.is_ending)

    def analyze(self) -> AnalysisReport:
        """执行完整分析"""
        self._analyze_reachability()
        self._analyze_dead_choices()
        self._analyze_curse_usage()
        self._analyze_ending_conflicts()
        return self.report

    def _analyze_reachability(self) -> None:
        """分析节点可达性"""
        reachable: Set[str] = set()
        queue: deque = deque()

        for start_node in self.script.get_start_nodes():
            if start_node.id not in reachable:
                if CurseState().check_conditions(start_node.conditions):
                    reachable.add(start_node.id)
                    queue.append((start_node.id, CurseState()))

        while queue:
            node_id, curse_state = queue.popleft()
            node = self.script.get_node(node_id)
            if not node:
                continue

            new_curse_state = curse_state.copy()
            for effect in node.curse_effects:
                new_curse_state.apply_effect(effect)

            for choice in node.choices:
                if new_curse_state.check_conditions(choice.conditions):
                    choice_curse_state = new_curse_state.copy()
                    for effect in choice.curse_effects:
                        choice_curse_state.apply_effect(effect)
                    target_node = self.script.get_node(choice.target_node)
                    if target_node and choice_curse_state.check_conditions(target_node.conditions):
                        if choice.target_node not in reachable:
                            reachable.add(choice.target_node)
                            queue.append((choice.target_node, choice_curse_state))

            if node.next_node:
                target_node = self.script.get_node(node.next_node)
                if target_node and new_curse_state.check_conditions(target_node.conditions):
                    if node.next_node not in reachable:
                        reachable.add(node.next_node)
                        queue.append((node.next_node, new_curse_state))

        for node_id, node in self.script.all_nodes.items():
            if node_id not in reachable:
                self.report.unreachable_nodes.append(UnreachableNode(
                    node_id=node_id,
                    title=node.title or node_id,
                    chapter=node.chapter
                ))

    def _analyze_dead_choices(self) -> None:
        """分析永远无法到达的选项"""
        reachable_with_state: Dict[str, List[CurseState]] = defaultdict(list)
        queue: deque = deque()
        max_iterations = 10000
        iterations = 0
        max_states_per_node = 50

        for start_node in self.script.get_start_nodes():
            initial_state = CurseState()
            if initial_state.check_conditions(start_node.conditions):
                reachable_with_state[start_node.id].append(initial_state)
                queue.append((start_node.id, initial_state))

        while queue and iterations < max_iterations:
            iterations += 1
            node_id, curse_state = queue.popleft()
            node = self.script.get_node(node_id)
            if not node:
                continue

            new_curse_state = curse_state.copy()
            for effect in node.curse_effects:
                new_curse_state.apply_effect(effect)

            for choice in node.choices:
                if new_curse_state.check_conditions(choice.conditions):
                    choice_curse_state = new_curse_state.copy()
                    for effect in choice.curse_effects:
                        choice_curse_state.apply_effect(effect)

                    target_node = self.script.get_node(choice.target_node)
                    if not target_node or not choice_curse_state.check_conditions(target_node.conditions):
                        continue

                    state_exists = False
                    for existing_state in reachable_with_state[choice.target_node]:
                        if self._states_are_compatible(existing_state, choice_curse_state):
                            state_exists = True
                            break

                    if not state_exists and len(reachable_with_state[choice.target_node]) < max_states_per_node:
                        reachable_with_state[choice.target_node].append(choice_curse_state)
                        queue.append((choice.target_node, choice_curse_state))

            if node.next_node:
                target_node = self.script.get_node(node.next_node)
                if target_node and new_curse_state.check_conditions(target_node.conditions):
                    state_exists = False
                    for existing_state in reachable_with_state[node.next_node]:
                        if self._states_are_compatible(existing_state, new_curse_state):
                            state_exists = True
                            break

                    if not state_exists and len(reachable_with_state[node.next_node]) < max_states_per_node:
                        reachable_with_state[node.next_node].append(new_curse_state)
                        queue.append((node.next_node, new_curse_state))

        for node_id, node in self.script.all_nodes.items():
            for choice in node.choices:
                is_reachable = False
                for curse_state in reachable_with_state.get(node_id, []):
                    node_curse_state = curse_state.copy()
                    for effect in node.curse_effects:
                        node_curse_state.apply_effect(effect)
                    if node_curse_state.check_conditions(choice.conditions):
                        is_reachable = True
                        break

                if not is_reachable:
                    reason = self._explain_unreachable_choice(node, choice)
                    self.report.dead_choices.append(DeadChoice(
                        node_id=node_id,
                        choice_id=choice.id,
                        text=choice.text,
                        reason=reason
                    ))

    def _explain_unreachable_choice(self, node: Node, choice: Choice) -> str:
        """解释为什么选项不可达"""
        if not choice.conditions:
            return "父节点本身不可达"

        reasons = []
        for cond in choice.conditions:
            if cond.required:
                if cond.max_level is not None:
                    reasons.append(f"需要 {cond.curse_name} <= {cond.max_level}")
                elif cond.min_level > 1:
                    reasons.append(f"需要 {cond.curse_name} >= {cond.min_level}")
                else:
                    reasons.append(f"需要 {cond.curse_name} 存在")
            else:
                reasons.append(f"需要 {cond.curse_name} 不存在")

        return "条件无法满足: " + ", ".join(reasons)

    def _states_are_compatible(self, s1: CurseState, s2: CurseState) -> bool:
        """检查两个诅咒状态是否兼容（s1是否覆盖s2的所有要求）"""
        for curse, level in s2.curses.items():
            if s1.curses.get(curse, 0) < level:
                return False
        return True

    def _analyze_curse_usage(self) -> None:
        """分析诅咒标记使用情况"""
        curse_set_by: Dict[str, List[str]] = defaultdict(list)
        curse_checked_in: Dict[str, List[str]] = defaultdict(list)
        curse_effective_in: Dict[str, List[str]] = defaultdict(list)

        for node_id, node in self.script.all_nodes.items():
            for effect in node.curse_effects:
                curse_set_by[effect.name].append(f"节点:{node_id}")

            for cond in node.conditions:
                curse_checked_in[cond.curse_name].append(f"节点条件:{node_id}")

            for choice in node.choices:
                for effect in choice.curse_effects:
                    curse_set_by[effect.name].append(f"选项:{node_id}.{choice.id}")
                for cond in choice.conditions:
                    curse_checked_in[cond.curse_name].append(f"选项条件:{node_id}.{choice.id}")
                    if self._is_effective_condition(cond, node, choice):
                        curse_effective_in[cond.curse_name].append(f"{node_id}.{choice.id}")

        for curse_name, description in self.script.curse_definitions.items():
            never_checked = curse_name not in curse_checked_in
            never_effective = curse_name not in curse_effective_in

            if never_checked or never_effective:
                self.report.unused_curses.append(UnusedCurse(
                    curse_name=curse_name,
                    description=description,
                    set_by=curse_set_by.get(curse_name, []),
                    never_checked=never_checked,
                    never_effective=never_effective
                ))

    def _is_effective_condition(self, cond: Condition, node: Node, choice: Choice) -> bool:
        """判断条件是否真正影响了剧情走向"""
        if not node.choices:
            return False

        has_alternative = False
        for other_choice in node.choices:
            if other_choice.id == choice.id:
                continue
            other_cond_names = {c.curse_name for c in other_choice.conditions}
            if cond.curse_name not in other_cond_names:
                has_alternative = True
                break

        return has_alternative or len(choice.conditions) > 1

    def _analyze_ending_conflicts(self) -> None:
        """分析结局条件冲突"""
        endings = [n for n in self.script.all_nodes.values() if n.is_ending]

        for i, ending1 in enumerate(endings):
            for ending2 in endings[i + 1:]:
                conflict = self._check_ending_conflict(ending1, ending2)
                if conflict:
                    self.report.conflicting_endings.append(conflict)

    def _check_ending_conflict(self, e1: Node, e2: Node) -> Optional[ConflictingEnding]:
        """检查两个结局是否存在条件冲突"""
        if not e1.conditions and not e2.conditions:
            return ConflictingEnding(
                ending1=e1.title or e1.id,
                ending2=e2.title or e2.id,
                conflict_type="无区分条件",
                details=f"两个结局都没有进入条件，玩家可能同时或随机进入"
            )

        conds1 = {c.curse_name: c for c in e1.conditions}
        conds2 = {c.curse_name: c for c in e2.conditions}

        mutual_curses = set(conds1.keys()) & set(conds2.keys())
        if not mutual_curses:
            return ConflictingEnding(
                ending1=e1.title or e1.id,
                ending2=e2.title or e2.id,
                conflict_type="条件正交",
                details=f"两个结局使用不同的诅咒条件，可能同时满足"
            )

        for curse in mutual_curses:
            c1 = conds1[curse]
            c2 = conds2[curse]

            if c1.required != c2.required:
                return ConflictingEnding(
                    ending1=e1.title or e1.id,
                    ending2=e2.title or e2.id,
                    conflict_type="条件互斥",
                    details=f"诅咒 {curse}: 一个需要存在，一个需要不存在"
                )

            if c1.required and c2.required:
                if c1.max_level is not None and c2.min_level is not None:
                    if c1.max_level < c2.min_level:
                        return ConflictingEnding(
                            ending1=e1.title or e1.id,
                            ending2=e2.title or e2.id,
                            conflict_type="等级范围不重叠",
                            details=f"诅咒 {curse}: {e1.title or e1.id} 需要 <= {c1.max_level}, {e2.title or e2.id} 需要 >= {c2.min_level}"
                        )
                if c2.max_level is not None and c1.min_level is not None:
                    if c2.max_level < c1.min_level:
                        return ConflictingEnding(
                            ending1=e1.title or e1.id,
                            ending2=e2.title or e2.id,
                            conflict_type="等级范围不重叠",
                            details=f"诅咒 {curse}: {e2.title or e2.id} 需要 <= {c2.max_level}, {e1.title or e1.id} 需要 >= {c1.min_level}"
                        )

        return None
