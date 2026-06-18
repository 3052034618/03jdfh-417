"""
恐怖节奏分析模块
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .analyzer import CurseState
from .models import Node, RhythmType, Script, Choice


@dataclass
class PathRhythm:
    """单条路径的节奏分析"""
    path: List[str]  # 节点ID序列
    rhythm_sequence: List[RhythmType]
    rhythm_counts: Dict[RhythmType, int]
    rhythm_percentages: Dict[RhythmType, float]
    warnings: List[str]
    ending_node: Optional[str]


@dataclass
class RhythmReport:
    """节奏分析报告"""
    total_paths: int = 0
    path_analyses: List[PathRhythm] = field(default_factory=list)
    overall_rhythm_distribution: Dict[RhythmType, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


RHYTHM_INTENSITY = {
    RhythmType.CALM: 0,
    RhythmType.UNSETTLE: 1,
    RhythmType.CHASE: 2,
    RhythmType.REVEAL: 3,
    RhythmType.BREAKDOWN: 4,
}


class RhythmAnalyzer:
    """恐怖节奏分析器"""

    def __init__(self, script: Script):
        self.script = script
        self.max_path_length = 100
        self.max_paths = 1000

    def analyze(self) -> RhythmReport:
        """执行节奏分析"""
        report = RhythmReport()

        paths = self._find_all_paths()
        report.total_paths = len(paths)

        overall_counts: Dict[RhythmType, int] = defaultdict(int)

        for path in paths:
            path_rhythm = self._analyze_path(path)
            report.path_analyses.append(path_rhythm)

            for rhythm, count in path_rhythm.rhythm_counts.items():
                overall_counts[rhythm] += count

        report.overall_rhythm_distribution = dict(overall_counts)
        report.warnings = self._generate_global_warnings(paths)

        return report

    def _find_all_paths(self) -> List[List[str]]:
        """找出所有可能的剧情路径"""
        paths: List[List[str]] = []
        start_nodes = self.script.get_start_nodes()

        for start_node in start_nodes:
            self._dfs_paths(
                node_id=start_node.id,
                current_path=[],
                visited=set(),
                curse_state=CurseState(),
                paths=paths,
                depth=0
            )

        return paths[:self.max_paths]

    def _dfs_paths(
        self,
        node_id: str,
        current_path: List[str],
        visited: set,
        curse_state: CurseState,
        paths: List[List[str]],
        depth: int
    ) -> None:
        """深度优先搜索所有路径"""
        if depth > self.max_path_length or node_id in visited:
            paths.append(current_path + [node_id])
            return

        node = self.script.get_node(node_id)
        if not node:
            return

        new_path = current_path + [node_id]
        new_visited = visited | {node_id}

        new_curse_state = curse_state.copy()
        for effect in node.curse_effects:
            new_curse_state.apply_effect(effect)

        if node.is_ending:
            paths.append(new_path)
            return

        available_choices = [
            c for c in node.choices
            if new_curse_state.check_conditions(c.conditions)
        ]

        if available_choices:
            for choice in available_choices:
                choice_curse_state = new_curse_state.copy()
                for effect in choice.curse_effects:
                    choice_curse_state.apply_effect(effect)
                target_node = self.script.get_node(choice.target_node)
                if target_node and choice_curse_state.check_conditions(target_node.conditions):
                    self._dfs_paths(
                        node_id=choice.target_node,
                        current_path=new_path,
                        visited=new_visited,
                        curse_state=choice_curse_state,
                        paths=paths,
                        depth=depth + 1
                    )
        elif node.next_node:
            target_node = self.script.get_node(node.next_node)
            if target_node and new_curse_state.check_conditions(target_node.conditions):
                self._dfs_paths(
                    node_id=node.next_node,
                    current_path=new_path,
                    visited=new_visited,
                    curse_state=new_curse_state,
                    paths=paths,
                    depth=depth + 1
                )
        else:
            paths.append(new_path)

    def _analyze_path(self, path: List[str]) -> PathRhythm:
        """分析单条路径的节奏"""
        rhythm_sequence: List[RhythmType] = []
        rhythm_counts: Dict[RhythmType, int] = defaultdict(int)

        for node_id in path:
            node = self.script.get_node(node_id)
            if node:
                rhythm_sequence.append(node.rhythm)
                rhythm_counts[node.rhythm] += 1

        total = len(rhythm_sequence)
        rhythm_percentages = {
            rhythm: (count / total * 100) if total > 0 else 0
            for rhythm, count in rhythm_counts.items()
        }

        warnings = self._generate_path_warnings(path, rhythm_sequence)

        ending_node = path[-1] if path else None

        return PathRhythm(
            path=path,
            rhythm_sequence=rhythm_sequence,
            rhythm_counts=dict(rhythm_counts),
            rhythm_percentages=rhythm_percentages,
            warnings=warnings,
            ending_node=ending_node
        )

    def _generate_path_warnings(self, path: List[str], rhythm_sequence: List[RhythmType]) -> List[str]:
        """生成单条路径的节奏警告"""
        warnings: List[str] = []

        if len(rhythm_sequence) < 3:
            return warnings

        max_calm_streak = 5
        current_calm_streak = 0
        max_high_intensity_early = 0.3

        for i, rhythm in enumerate(rhythm_sequence):
            if rhythm in (RhythmType.CALM, RhythmType.UNSETTLE):
                current_calm_streak += 1
                if current_calm_streak >= max_calm_streak:
                    node = self.script.get_node(path[i])
                    warnings.append(
                        f"节点 {path[i]} ({node.title if node and node.title else ''}): "
                        f"连续 {current_calm_streak} 个低压迫感段落，可能导致玩家注意力下降"
                    )
                    current_calm_streak = 0
            else:
                current_calm_streak = 0

            position = (i + 1) / len(rhythm_sequence)
            intensity = RHYTHM_INTENSITY.get(rhythm, 0)
            if position < max_high_intensity_early and intensity >= 3:
                node = self.script.get_node(path[i])
                warnings.append(
                    f"节点 {path[i]} ({node.title if node and node.title else ''}): "
                    f"在进度 {position:.0%} 处出现 {rhythm.value} 段落，可能过早爆点"
                )

        has_breakdown = any(r == RhythmType.BREAKDOWN for r in rhythm_sequence)
        has_reveal = any(r == RhythmType.REVEAL for r in rhythm_sequence)

        if has_breakdown and not has_reveal:
            warnings.append("路径包含崩坏段落但没有揭露段落，节奏曲线可能不完整")

        return warnings

    def _generate_global_warnings(self, paths: List[List[str]]) -> List[str]:
        """生成全局警告"""
        warnings: List[str] = []

        if not paths:
            return warnings

        path_lengths = [len(p) for p in paths]
        avg_length = sum(path_lengths) / len(path_lengths)
        min_length = min(path_lengths)
        max_length = max(path_lengths)

        if max_length - min_length > avg_length * 0.5:
            warnings.append(
                f"路径长度差异较大（最短 {min_length}，最长 {max_length}，平均 {avg_length:.1f}），"
                f"部分支线可能内容不足"
            )

        short_paths = [p for p in paths if len(p) < avg_length * 0.5]
        if short_paths:
            warnings.append(
                f"发现 {len(short_paths)} 条过短路径（小于平均长度的50%），"
                f"可能存在仓促结局"
            )

        all_high_rhythm_paths = 0
        for path in paths:
            rhythms = [self.script.get_node(n).rhythm for n in path if self.script.get_node(n)]
            high_rhythm_count = sum(
                1 for r in rhythms
                if RHYTHM_INTENSITY.get(r, 0) >= 2
            )
            if len(rhythms) > 0 and high_rhythm_count / len(rhythms) > 0.7:
                all_high_rhythm_paths += 1

        if all_high_rhythm_paths > len(paths) * 0.3:
            warnings.append(
                f"超过30%的路径高压迫感段落占比超过70%，"
                f"可能缺乏喘息空间导致玩家疲劳"
            )

        return warnings
