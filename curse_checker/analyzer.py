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
    nearest_reachable: List[str] = field(default_factory=list)  # 最近的可达节点
    blocked_reasons: List[str] = field(default_factory=list)  # 阻断原因


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
    propagated_to: List[str] = field(default_factory=list)  # 诅咒传播到了哪些节点
    propagation_depth: int = 0  # 传播深度（最多传了几个节点）


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


@dataclass
class EntryPoint:
    """节点的入口点信息"""
    from_node_id: str
    from_node_title: str
    via_choice_id: Optional[str]  # None 表示自动跳转
    via_choice_text: Optional[str]
    entry_state: Dict[str, int]  # 进入时的诅咒状态


@dataclass
class NodeExplainReport:
    """节点可达性解释报告"""
    node_id: str
    node_title: str
    chapter: str
    is_reachable: bool
    is_start: bool
    entry_points: List[EntryPoint] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    nearest_reachable_nodes: List[str] = field(default_factory=list)
    node_conditions: List[str] = field(default_factory=list)


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
        self._curse_thresholds: Dict[str, List[int]] = self._collect_curse_thresholds()

    def _collect_curse_thresholds(self) -> Dict[str, List[int]]:
        """收集所有诅咒条件的阈值，用于状态归一化"""
        thresholds: Dict[str, set] = defaultdict(set)

        for node in self.script.all_nodes.values():
            for cond in node.conditions:
                if cond.required:
                    thresholds[cond.curse_name].add(cond.min_level)
                    if cond.max_level is not None:
                        thresholds[cond.curse_name].add(cond.max_level + 1)
                else:
                    thresholds[cond.curse_name].add(1)

            for choice in node.choices:
                for cond in choice.conditions:
                    if cond.required:
                        thresholds[cond.curse_name].add(cond.min_level)
                        if cond.max_level is not None:
                            thresholds[cond.curse_name].add(cond.max_level + 1)
                    else:
                        thresholds[cond.curse_name].add(1)

        result = {}
        for curse, thresh_set in thresholds.items():
            thresh_list = sorted(thresh_set)
            result[curse] = thresh_list

        return result

    def _normalize_state(self, state: CurseState) -> CurseState:
        """将诅咒状态归一化，将等级映射到区间代表值
        
        同一区间内的等级对所有条件来说都是等价的，
        这样可以避免循环刷等级导致的状态爆炸。
        """
        normalized = CurseState()
        normalized.curses = dict(state.curses)

        for curse, level in state.curses.items():
            if curse in self._curse_thresholds:
                thresholds = self._curse_thresholds[curse]
                for t in thresholds:
                    if level < t:
                        normalized.curses[curse] = t - 1 if t > 0 else 0
                        break
                else:
                    normalized.curses[curse] = thresholds[-1]

        return normalized

    def analyze(self) -> AnalysisReport:
        """执行完整分析"""
        self._analyze_reachability()
        self._analyze_dead_choices()
        self._analyze_curse_usage()
        self._analyze_ending_conflicts()
        return self.report

    def _analyze_reachability(self) -> None:
        """分析节点可达性"""
        reachable_with_state: Dict[str, List[CurseState]] = defaultdict(list)
        queue: deque = deque()
        max_iterations = 10000
        iterations = 0
        max_states_per_node = 50

        for start_node in self.script.get_start_nodes():
            initial_state = CurseState()
            if initial_state.check_conditions(start_node.conditions):
                norm_state = self._normalize_state(initial_state)
                state_exists = False
                for existing in reachable_with_state[start_node.id]:
                    if self._states_are_equivalent(existing, norm_state):
                        state_exists = True
                        break
                if not state_exists:
                    reachable_with_state[start_node.id].append(norm_state)
                    queue.append((start_node.id, norm_state))

        while queue and iterations < max_iterations:
            iterations += 1
            node_id, curse_state = queue.popleft()
            node = self.script.get_node(node_id)
            if not node:
                continue

            new_curse_state = curse_state.copy()
            for effect in node.curse_effects:
                new_curse_state.apply_effect(effect)
            new_curse_state = self._normalize_state(new_curse_state)

            for choice in node.choices:
                if new_curse_state.check_conditions(choice.conditions):
                    choice_curse_state = new_curse_state.copy()
                    for effect in choice.curse_effects:
                        choice_curse_state.apply_effect(effect)
                    choice_curse_state = self._normalize_state(choice_curse_state)
                    target_node = self.script.get_node(choice.target_node)
                    if target_node and choice_curse_state.check_conditions(target_node.conditions):
                        state_exists = False
                        for existing_state in reachable_with_state[choice.target_node]:
                            if self._states_are_equivalent(existing_state, choice_curse_state):
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
                        if self._states_are_equivalent(existing_state, new_curse_state):
                            state_exists = True
                            break
                    if not state_exists and len(reachable_with_state[node.next_node]) < max_states_per_node:
                        reachable_with_state[node.next_node].append(new_curse_state)
                        queue.append((node.next_node, new_curse_state))

        for node_id, node in self.script.all_nodes.items():
            if node_id not in reachable_with_state or not reachable_with_state[node_id]:
                nearest = []
                reasons = []

                # 找出所有指向该节点的可达节点
                for src_node in self.script.all_nodes.values():
                    if src_node.id not in reachable_with_state or not reachable_with_state[src_node.id]:
                        continue

                    # 检查选项
                    for choice in src_node.choices:
                        if choice.target_node == node_id:
                            if src_node.id not in nearest:
                                nearest.append(src_node.id)
                            # 分析为什么过不去
                            can_reach_with_any = False
                            for state in reachable_with_state[src_node.id]:
                                node_state = state.copy()
                                for effect in src_node.curse_effects:
                                    node_state.apply_effect(effect)
                                if not node_state.check_conditions(choice.conditions):
                                    continue
                                choice_state = node_state.copy()
                                for effect in choice.curse_effects:
                                    choice_state.apply_effect(effect)
                                if choice_state.check_conditions(node.conditions):
                                    can_reach_with_any = True
                                    break
                            if not can_reach_with_any:
                                reasons.append(
                                    f"从「{src_node.title or src_node.id}」通过「{choice.text}」无法到达："
                                    f"{self._explain_why_blocked(src_node, choice, node)}"
                                )

                    # 检查自动跳转
                    if src_node.next_node == node_id:
                        if src_node.id not in nearest:
                            nearest.append(src_node.id)
                        can_reach_with_any = False
                        for state in reachable_with_state[src_node.id]:
                            node_state = state.copy()
                            for effect in src_node.curse_effects:
                                node_state.apply_effect(effect)
                            if node_state.check_conditions(node.conditions):
                                can_reach_with_any = True
                                break
                        if not can_reach_with_any:
                            reasons.append(
                                f"从「{src_node.title or src_node.id}」自动跳转无法到达："
                                f"目标节点条件不满足"
                            )

                # 去重
                reasons = list(dict.fromkeys(reasons))[:5]

                self.report.unreachable_nodes.append(UnreachableNode(
                    node_id=node_id,
                    title=node.title or node_id,
                    chapter=node.chapter,
                    nearest_reachable=nearest[:5],
                    blocked_reasons=reasons
                ))

        self._reachable_with_state = reachable_with_state

    def explain_node(self, target_node_id: str) -> NodeExplainReport:
        """解释指定节点的可达性，列出所有入口路线和诅咒状态"""
        target_node = self.script.get_node(target_node_id)
        if not target_node:
            return NodeExplainReport(
                node_id=target_node_id,
                node_title="(不存在)",
                chapter="",
                is_reachable=False,
                is_start=False,
                blocked_reasons=["节点不存在"]
            )

        # 重新执行可达性分析，同时记录入口信息
        reachable_with_state: Dict[str, List[Tuple[CurseState, str, Optional[str], Optional[str]]]] = defaultdict(list)
        # 格式: node_id -> [(state, from_node_id, via_choice_id, via_choice_text)]
        queue: deque = deque()
        max_iterations = 10000
        iterations = 0
        max_states_per_node = 50

        for start_node in self.script.get_start_nodes():
            initial_state = CurseState()
            if initial_state.check_conditions(start_node.conditions):
                norm_state = self._normalize_state(initial_state)
                state_exists = False
                for existing, _, _, _ in reachable_with_state[start_node.id]:
                    if self._states_are_equivalent(existing, norm_state):
                        state_exists = True
                        break
                if not state_exists:
                    reachable_with_state[start_node.id].append(
                        (norm_state, "", None, None)
                    )
                    queue.append((start_node.id, norm_state, "", None, None))

        while queue and iterations < max_iterations:
            iterations += 1
            node_id, curse_state, from_id, from_choice_id, from_choice_text = queue.popleft()
            node = self.script.get_node(node_id)
            if not node:
                continue

            new_curse_state = curse_state.copy()
            for effect in node.curse_effects:
                new_curse_state.apply_effect(effect)
            new_curse_state = self._normalize_state(new_curse_state)

            for choice in node.choices:
                if new_curse_state.check_conditions(choice.conditions):
                    choice_curse_state = new_curse_state.copy()
                    for effect in choice.curse_effects:
                        choice_curse_state.apply_effect(effect)
                    choice_curse_state = self._normalize_state(choice_curse_state)
                    target = self.script.get_node(choice.target_node)
                    if target and choice_curse_state.check_conditions(target.conditions):
                        state_exists = False
                        for existing_state, _, _, _ in reachable_with_state[choice.target_node]:
                            if self._states_are_equivalent(existing_state, choice_curse_state):
                                state_exists = True
                                break
                        if not state_exists and len(reachable_with_state[choice.target_node]) < max_states_per_node:
                            reachable_with_state[choice.target_node].append(
                                (choice_curse_state, node_id, choice.id, choice.text)
                            )
                            queue.append((choice.target_node, choice_curse_state, node_id, choice.id, choice.text))

            if node.next_node:
                target = self.script.get_node(node.next_node)
                if target and new_curse_state.check_conditions(target.conditions):
                    state_exists = False
                    for existing_state, _, _, _ in reachable_with_state[node.next_node]:
                        if self._states_are_equivalent(existing_state, new_curse_state):
                            state_exists = True
                            break
                    if not state_exists and len(reachable_with_state[node.next_node]) < max_states_per_node:
                        reachable_with_state[node.next_node].append(
                            (new_curse_state, node_id, None, None)
                        )
                        queue.append((node.next_node, new_curse_state, node_id, None, None))

        # 构建报告
        is_reachable = target_node_id in reachable_with_state and bool(reachable_with_state[target_node_id])

        entry_points: List[EntryPoint] = []
        if is_reachable:
            for state, from_id, choice_id, choice_text in reachable_with_state[target_node_id]:
                from_node = self.script.get_node(from_id) if from_id else None
                entry_points.append(EntryPoint(
                    from_node_id=from_id or "(起点)",
                    from_node_title=from_node.title if from_node and from_node.title else from_id or "(起点)",
                    via_choice_id=choice_id,
                    via_choice_text=choice_text,
                    entry_state=dict(state.curses)
                ))

        # 节点自身的进入条件
        node_conditions = []
        for cond in target_node.conditions:
            if cond.required:
                if cond.max_level is not None and cond.min_level > 1:
                    node_conditions.append(f"{cond.curse_name} {cond.min_level}-{cond.max_level}级")
                elif cond.min_level > 1:
                    node_conditions.append(f"{cond.curse_name} >= {cond.min_level}级")
                elif cond.max_level is not None:
                    node_conditions.append(f"{cond.curse_name} <= {cond.max_level}级")
                else:
                    node_conditions.append(f"{cond.curse_name} 存在")
            else:
                node_conditions.append(f"{cond.curse_name} 不存在")

        # 不可达时找最近的可达节点
        blocked_reasons = []
        nearest = []
        if not is_reachable:
            # 找出所有指向目标节点，但自身可达的节点
            for node in self.script.all_nodes.values():
                if node.id not in reachable_with_state or not reachable_with_state[node.id]:
                    continue
                # 检查选项
                for choice in node.choices:
                    if choice.target_node == target_node_id:
                        nearest.append(node.id)
                        # 分析为什么过不去
                        for state, _, _, _ in reachable_with_state[node.id]:
                            node_state = state.copy()
                            for effect in node.curse_effects:
                                node_state.apply_effect(effect)
                            if not node_state.check_conditions(choice.conditions):
                                conds = []
                                for c in choice.conditions:
                                    conds.append(self._format_condition(c))
                                blocked_reasons.append(
                                    f"从 {node.title or node.id} 选择「{choice.text}」时，选项条件不满足: {', '.join(conds)}"
                                )
                                break
                            else:
                                choice_state = node_state.copy()
                                for effect in choice.curse_effects:
                                    choice_state.apply_effect(effect)
                                if not choice_state.check_conditions(target_node.conditions):
                                    conds = []
                                    for c in target_node.conditions:
                                        conds.append(self._format_condition(c))
                                    blocked_reasons.append(
                                        f"从 {node.title or node.id} 选择「{choice.text}」后，目标节点条件不满足: {', '.join(conds)}"
                                    )
                                    break
                # 检查自动跳转
                if node.next_node == target_node_id:
                    nearest.append(node.id)
                    for state, _, _, _ in reachable_with_state[node.id]:
                        node_state = state.copy()
                        for effect in node.curse_effects:
                            node_state.apply_effect(effect)
                        if not node_state.check_conditions(target_node.conditions):
                            conds = []
                            for c in target_node.conditions:
                                conds.append(self._format_condition(c))
                            blocked_reasons.append(
                                f"从 {node.title or node.id} 自动跳转后，目标节点条件不满足: {', '.join(conds)}"
                            )
                            break

        return NodeExplainReport(
            node_id=target_node_id,
            node_title=target_node.title or target_node_id,
            chapter=target_node.chapter,
            is_reachable=is_reachable,
            is_start=target_node.is_start,
            entry_points=entry_points,
            blocked_reasons=list(dict.fromkeys(blocked_reasons))[:10],
            nearest_reachable_nodes=list(dict.fromkeys(nearest))[:10],
            node_conditions=node_conditions
        )

    def _format_condition(self, cond: Condition) -> str:
        """格式化条件为可读字符串"""
        if cond.required:
            if cond.min_level > 1 and cond.max_level is not None:
                return f"{cond.curse_name} {cond.min_level}-{cond.max_level}级"
            elif cond.min_level > 1:
                return f"{cond.curse_name} >= {cond.min_level}级"
            elif cond.max_level is not None:
                return f"{cond.curse_name} <= {cond.max_level}级"
            else:
                return f"需要 {cond.curse_name}"
        else:
            return f"需要 {cond.curse_name} 不存在"

    def _explain_why_blocked(self, src_node: Node, choice: Choice, target_node: Node) -> str:
        """解释为什么从源节点通过某个选项无法到达目标节点"""
        # 先检查选项条件
        if choice.conditions:
            choice_conds = [self._format_condition(c) for c in choice.conditions]
            return f"选项条件不满足（{', '.join(choice_conds)}）"

        # 再检查目标节点条件
        if target_node.conditions:
            target_conds = [self._format_condition(c) for c in target_node.conditions]
            return f"目标节点条件不满足（{', '.join(target_conds)}）"

        return "原因未知"

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
        """检查 s1 是否完全覆盖 s2（s1 能满足所有 s2 能满足的条件，且更多）

        s1 覆盖 s2 当且仅当：
        1. 两者诅咒集合完全相同（有/无的诅咒完全一致）
        2. s1 中每个诅咒的等级 >= s2 中对应等级

        如果诅咒集合不同，两者互不覆盖，因为"没有某诅咒"也是
        一种状态特征，可以用来进入需要 !诅咒 的节点。
        """
        if set(s1.curses.keys()) != set(s2.curses.keys()):
            return False
        for curse, level in s2.curses.items():
            if s1.curses.get(curse, 0) < level:
                return False
        return True

    def _states_are_equivalent(self, s1: CurseState, s2: CurseState) -> bool:
        """检查两个状态是否等价（对所有条件的满足情况完全相同）

        等价的状态可以合并，避免状态爆炸。
        """
        if set(s1.curses.keys()) != set(s2.curses.keys()):
            return False
        for curse, level in s1.curses.items():
            if s2.curses.get(curse, 0) != level:
                return False
        return True

    def _analyze_curse_usage(self) -> None:
        """分析诅咒标记使用情况"""
        curse_set_by: Dict[str, List[str]] = defaultdict(list)
        curse_checked_in: Dict[str, List[str]] = defaultdict(list)
        curse_effective_in: Dict[str, List[str]] = defaultdict(list)
        all_curse_names: Set[str] = set()

        for node_id, node in self.script.all_nodes.items():
            for effect in node.curse_effects:
                curse_set_by[effect.name].append(f"节点:{node_id}")
                all_curse_names.add(effect.name)

            for cond in node.conditions:
                curse_checked_in[cond.curse_name].append(f"节点条件:{node_id}")
                all_curse_names.add(cond.curse_name)
                if self._is_effective_node_condition(cond, node):
                    curse_effective_in[cond.curse_name].append(f"节点:{node_id}")

            for choice in node.choices:
                for effect in choice.curse_effects:
                    curse_set_by[effect.name].append(f"选项:{node_id}.{choice.id}")
                    all_curse_names.add(effect.name)
                for cond in choice.conditions:
                    curse_checked_in[cond.curse_name].append(f"选项条件:{node_id}.{choice.id}")
                    all_curse_names.add(cond.curse_name)
                    if self._is_effective_choice_condition(cond, node, choice):
                        curse_effective_in[cond.curse_name].append(f"{node_id}.{choice.id}")

        for curse_name in all_curse_names:
            description = self.script.curse_definitions.get(curse_name, "(未定义的诅咒)")
            never_checked = curse_name not in curse_checked_in
            never_effective = curse_name not in curse_effective_in

            if never_checked or never_effective:
                propagated_to = []
                max_depth = 0

                if hasattr(self, '_reachable_with_state'):
                    for node_id, states in self._reachable_with_state.items():
                        for state in states:
                            if curse_name in state.curses:
                                node = self.script.get_node(node_id)
                                title = node.title if node and node.title else node_id
                                propagated_to.append(title)
                                break

                    propagated_to = list(dict.fromkeys(propagated_to))

                    if propagated_to:
                        max_depth = self._calculate_curse_propagation_depth(curse_name)

                self.report.unused_curses.append(UnusedCurse(
                    curse_name=curse_name,
                    description=description,
                    set_by=curse_set_by.get(curse_name, []),
                    never_checked=never_checked,
                    never_effective=never_effective,
                    propagated_to=propagated_to[:10],
                    propagation_depth=max_depth
                ))

    def _calculate_curse_propagation_depth(self, curse_name: str) -> int:
        """计算诅咒的最大传播深度（从设置点开始能传多少个节点）"""
        if not hasattr(self, '_reachable_with_state'):
            return 0

        max_depth = 0
        visited = set()

        def bfs_depth(start_id: str, start_state: CurseState) -> int:
            queue = deque([(start_id, start_state, 0)])
            local_visited = set()
            local_max = 0

            while queue:
                node_id, state, depth = queue.popleft()
                key = (node_id, tuple(sorted(state.curses.items())))
                if key in local_visited:
                    continue
                local_visited.add(key)
                local_max = max(local_max, depth)

                node = self.script.get_node(node_id)
                if not node:
                    continue

                new_state = state.copy()
                for effect in node.curse_effects:
                    new_state.apply_effect(effect)
                new_state = self._normalize_state(new_state)

                for choice in node.choices:
                    if new_state.check_conditions(choice.conditions):
                        choice_state = new_state.copy()
                        for effect in choice.curse_effects:
                            choice_state.apply_effect(effect)
                        choice_state = self._normalize_state(choice_state)
                        target = self.script.get_node(choice.target_node)
                        if target and choice_state.check_conditions(target.conditions):
                            if curse_name in choice_state.curses:
                                queue.append((choice.target_node, choice_state, depth + 1))

                if node.next_node:
                    target = self.script.get_node(node.next_node)
                    if target and new_state.check_conditions(target.conditions):
                        if curse_name in new_state.curses:
                            queue.append((node.next_node, new_state, depth + 1))

            return local_max

        for node_id, states in self._reachable_with_state.items():
            for state in states:
                if curse_name in state.curses:
                    depth = bfs_depth(node_id, state)
                    max_depth = max(max_depth, depth)

        return max_depth

    def _is_effective_node_condition(self, cond: Condition, node: Node) -> bool:
        """判断节点进入条件是否真正影响了剧情走向"""
        if node.is_start:
            return True
        if node.is_ending:
            return True
        if node.conditions and len(node.conditions) >= 1:
            return True
        return False

    def _is_effective_choice_condition(self, cond: Condition, node: Node, choice: Choice) -> bool:
        """判断选项条件是否真正影响了剧情走向"""
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
