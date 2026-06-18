"""
报告格式化输出模块
"""

from typing import Dict, List

from .analyzer import AnalysisReport, CompareReport
from .models import RhythmType, Script
from .path_generator import GeneratedPlaythrough, PathSummary
from .rhythm import RhythmReport


class ReportFormatter:
    """报告格式化器"""

    def __init__(self, script: Script):
        self.script = script

    def format_analysis_report(self, report: AnalysisReport) -> str:
        """格式化剧情分析报告"""
        lines: List[str] = []

        lines.append("=" * 70)
        lines.append(f"  诅咒剧情分析报告 - {self.script.title}")
        lines.append("=" * 70)
        lines.append("")

        lines.append(f"📊 概览统计")
        lines.append(f"  总节点数: {report.total_nodes}")
        lines.append(f"  总选项数: {report.total_choices}")
        lines.append(f"  结局数: {report.total_endings}")
        lines.append("")

        if report.unreachable_nodes:
            lines.append("⚠️  不可达节点 ({})".format(len(report.unreachable_nodes)))
            lines.append("-" * 70)
            for node in report.unreachable_nodes:
                lines.append(f"  [{node.chapter}] {node.node_id} - {node.title}")
                if node.nearest_reachable:
                    nearest_titles = []
                    for nid in node.nearest_reachable[:3]:
                        n = self.script.get_node(nid)
                        if n and n.title:
                            nearest_titles.append(n.title)
                        else:
                            nearest_titles.append(nid)
                    lines.append(f"    ↳ 最近可达: {', '.join(nearest_titles)}")
                if node.blocked_reasons:
                    for reason in node.blocked_reasons[:2]:
                        lines.append(f"    ↳ 阻断: {reason}")
            lines.append("")

        if report.dead_choices:
            lines.append("⚠️  永远无法到达的选项 ({})".format(len(report.dead_choices)))
            lines.append("-" * 70)
            for choice in report.dead_choices:
                lines.append(f"  节点 {choice.node_id} -> 选项 [{choice.choice_id}]")
                lines.append(f"    文本: {choice.text}")
                lines.append(f"    原因: {choice.reason}")
            lines.append("")

        if report.unused_curses:
            lines.append("⚠️  未有效使用的诅咒标记 ({})".format(len(report.unused_curses)))
            lines.append("-" * 70)
            for curse in report.unused_curses:
                status_parts = []
                if curse.never_checked:
                    status_parts.append("从未被检查")
                if curse.never_effective:
                    status_parts.append("从未影响剧情")
                status = "、".join(status_parts)

                lines.append(f"  🔮 {curse.curse_name}")
                lines.append(f"    描述: {curse.description}")
                lines.append(f"    状态: {status}")
                if curse.set_by:
                    lines.append(f"    设置位置: {', '.join(curse.set_by[:3])}")
                    if len(curse.set_by) > 3:
                        lines.append(f"             等 {len(curse.set_by)} 处")
                if curse.propagated_to:
                    lines.append(f"    传播到: {', '.join(curse.propagated_to[:5])}")
                    if len(curse.propagated_to) > 5:
                        lines.append(f"             等 {len(curse.propagated_to)} 个节点")
                    if curse.propagation_depth > 0:
                        lines.append(f"    传播深度: 最远 {curse.propagation_depth} 跳")
                else:
                    lines.append(f"    传播到: 未传播到任何可达节点")
            lines.append("")

        if report.conflicting_endings:
            lines.append("⚠️  结局条件冲突 ({})".format(len(report.conflicting_endings)))
            lines.append("-" * 70)
            for conflict in report.conflicting_endings:
                lines.append(f"  「{conflict.ending1}」 vs 「{conflict.ending2}」")
                lines.append(f"    类型: {conflict.conflict_type}")
                lines.append(f"    详情: {conflict.details}")
            lines.append("")

        total_issues = (
            len(report.unreachable_nodes)
            + len(report.dead_choices)
            + len(report.unused_curses)
            + len(report.conflicting_endings)
        )

        if total_issues == 0:
            lines.append("✅ 未发现明显问题，剧本结构良好！")
        else:
            lines.append(f"⚠️  共发现 {total_issues} 个问题需要检查")

        lines.append("")
        return "\n".join(lines)

    def format_rhythm_report(self, report: RhythmReport, show_paths: int = 5) -> str:
        """格式化节奏分析报告"""
        lines: List[str] = []

        lines.append("=" * 70)
        lines.append(f"  恐怖节奏预览 - {self.script.title}")
        lines.append("=" * 70)
        lines.append("")

        lines.append(f"🎭 整体节奏分布")
        lines.append("-" * 70)
        total = sum(report.overall_rhythm_distribution.values())
        for rhythm in RhythmType:
            count = report.overall_rhythm_distribution.get(rhythm, 0)
            pct = (count / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            lines.append(f"  {rhythm.value:4} |{bar}| {pct:5.1f}% ({count})")
        lines.append("")

        lines.append(f"🔍 发现路径数: {report.total_paths}")
        lines.append("")

        if report.warnings:
            lines.append("⚠️  全局节奏警告")
            lines.append("-" * 70)
            for warning in report.warnings:
                lines.append(f"  • {warning}")
            lines.append("")

        if report.path_analyses:
            lines.append(f"📋 路径节奏预览 (显示前 {show_paths} 条)")
            lines.append("-" * 70)

            for i, path_analysis in enumerate(report.path_analyses[:show_paths], 1):
                ending_node = self.script.get_node(path_analysis.ending_node)
                ending_title = ending_node.title if ending_node and ending_node.title else path_analysis.ending_node

                rhythm_vis = "".join(
                    self._rhythm_to_symbol(r) for r in path_analysis.rhythm_sequence
                )

                lines.append(f"【路径 {i}】-> {ending_title} ({len(path_analysis.path)} 节点)")
                lines.append(f"  节奏: {rhythm_vis}")

                dist_parts = []
                for rhythm in RhythmType:
                    count = path_analysis.rhythm_counts.get(rhythm, 0)
                    if count > 0:
                        pct = path_analysis.rhythm_percentages.get(rhythm, 0)
                        dist_parts.append(f"{rhythm.value}:{pct:.0f}%")
                lines.append(f"  分布: {' '.join(dist_parts)}")

                if path_analysis.warnings:
                    for warning in path_analysis.warnings[:2]:
                        lines.append(f"  ⚠️  {warning}")

                lines.append("")

            if len(report.path_analyses) > show_paths:
                lines.append(f"  ... 还有 {len(report.path_analyses) - show_paths} 条路径")
                lines.append("")

        return "\n".join(lines)

    def _rhythm_to_symbol(self, rhythm: RhythmType) -> str:
        """将节奏类型转换为可视化符号"""
        mapping = {
            RhythmType.CALM: "·",
            RhythmType.UNSETTLE: "○",
            RhythmType.CHASE: "●",
            RhythmType.REVEAL: "◆",
            RhythmType.BREAKDOWN: "★",
        }
        return mapping.get(rhythm, "?")

    def format_playthrough_report(self, playthrough: GeneratedPlaythrough) -> str:
        """格式化游玩路径摘要"""
        lines: List[str] = []

        lines.append("=" * 70)
        lines.append(f"  随机游玩路径摘要 - {self.script.title}")
        lines.append("=" * 70)
        lines.append("")

        for i, summary in enumerate(playthrough.summaries, 1):
            lines.append(f"🎮 游玩记录 #{i}")
            lines.append("-" * 70)
            lines.append(f"  📍 结局: {summary.ending_title}")
            lines.append(f"  📏 路径长度: {summary.total_nodes} 节点")
            lines.append("")

            if summary.key_moments:
                lines.append("  🎬 关键事件:")
                for moment in summary.key_moments:
                    lines.append(f"    {moment}")
                lines.append("")

            if summary.curse_progressions:
                lines.append("  🔮 诅咒升级历程:")
                for curse_name, progression in summary.curse_progressions.items():
                    levels_str = " → ".join(
                        f"Lv.{level}" for level, _ in progression.levels
                    )
                    lines.append(f"    • {curse_name}: {levels_str}")
                    if progression.description:
                        lines.append(f"      {progression.description}")
                lines.append("")

            if summary.misleads:
                lines.append("  🎭 关键误导:")
                for mislead in summary.misleads:
                    lines.append(f"    • 在「{mislead.node_title}」选择了「{mislead.choice_text}」")
                    lines.append(f"      实际通向: {mislead.actual_target}")
                lines.append("")

            lines.append("  🗺️  完整路径:")
            path_str = " → ".join(summary.node_titles)
            lines.append(f"    {self._wrap_text(path_str, 64, '      ')}")
            lines.append("")

            if i < len(playthrough.summaries):
                lines.append("")

        return "\n".join(lines)

    def _wrap_text(self, text: str, width: int, indent: str) -> str:
        """文本换行"""
        if len(text) <= width:
            return text

        result = []
        current = text
        while len(current) > width:
            break_pos = current.rfind("→", 0, width)
            if break_pos == -1:
                break_pos = width
            result.append(current[:break_pos + 1])
            current = indent + current[break_pos + 1:].strip()
        result.append(current)
        return "\n".join(result)

    def format_node_explain(self, report) -> str:
        """格式化节点可达性解释报告"""
        lines: List[str] = []

        lines.append("=" * 70)
        lines.append(f"  节点可达性分析 - {report.node_title}")
        lines.append("=" * 70)
        lines.append("")

        lines.append(f"📌 节点信息")
        lines.append("-" * 70)
        lines.append(f"  ID: {report.node_id}")
        lines.append(f"  章节: {report.chapter}")
        lines.append(f"  类型: {'起始节点' if report.is_start else '普通节点'}")

        if report.node_conditions:
            lines.append(f"  进入条件: {', '.join(report.node_conditions)}")

        lines.append("")

        if report.is_reachable:
            grouped = self._group_entry_points(report.entry_points)
            total = sum(len(entries) for entries in grouped.values())
            lines.append(f"✅ 节点可达 ({total} 条入口路线)")
            lines.append("-" * 70)
            lines.append("")

            route_num = 1
            for group_key, entries in grouped.items():
                source_label = group_key
                lines.append(f"📂 来自 {source_label}")
                for entry in entries:
                    lines.append(f"  【路线 {route_num}】")
                    if entry.via_choice_id:
                        lines.append(f"    选项: [{entry.via_choice_id}] {entry.via_choice_text}")
                    else:
                        lines.append(f"    方式: 自动跳转")

                    if entry.entry_state:
                        state_parts = []
                        for curse, level in sorted(entry.entry_state.items()):
                            state_parts.append(f"{curse} Lv.{level}")
                        lines.append(f"    进入状态: {', '.join(state_parts)}")
                    else:
                        lines.append(f"    进入状态: 无诅咒（清净状态）")

                    lines.append("")
                    route_num += 1

        else:
            lines.append(f"❌ 节点不可达")
            lines.append("-" * 70)
            lines.append("")

            if report.nearest_reachable_nodes:
                lines.append(f"  最近的可达节点 ({len(report.nearest_reachable_nodes)} 个):")
                for nid in report.nearest_reachable_nodes[:5]:
                    node = self.script.get_node(nid)
                    title = node.title if node and node.title else nid
                    lines.append(f"    • {title} ({nid})")
                lines.append("")

            if report.blocked_reasons:
                lines.append(f"  阻断原因:")
                for reason in report.blocked_reasons:
                    lines.append(f"    • {reason}")
                lines.append("")

            if not report.nearest_reachable_nodes and not report.blocked_reasons:
                lines.append("  没有找到通往该节点的任何路径")
                lines.append("")

        return "\n".join(lines)

    def _group_entry_points(self, entry_points) -> dict:
        """按来源节点和选项分组入口路线"""
        from collections import OrderedDict
        grouped = OrderedDict()
        for entry in entry_points:
            if entry.via_choice_id:
                key = f"{entry.from_node_title} ({entry.from_node_id}) -> [{entry.via_choice_id}] {entry.via_choice_text}"
            else:
                key = f"{entry.from_node_title} ({entry.from_node_id}) [自动跳转]"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(entry)
        return grouped

    def format_compare_report(self, report: CompareReport) -> str:
        """格式化节点对比报告"""
        lines: List[str] = []

        lines.append("=" * 70)
        lines.append(f"  节点对比分析")
        lines.append("=" * 70)
        lines.append("")

        lines.append(f"📌 对比节点")
        lines.append("-" * 70)
        a_status = "✅ 可达" if report.a_reachable else "❌ 不可达"
        b_status = "✅ 可达" if report.b_reachable else "❌ 不可达"
        lines.append(f"  A: {report.node_a_title} ({report.node_a_id}) - {a_status} ({report.a_entry_count} 条入口)")
        lines.append(f"  B: {report.node_b_title} ({report.node_b_id}) - {b_status} ({report.b_entry_count} 条入口)")
        lines.append("")

        if report.a_reachable != report.b_reachable:
            lines.append(f"⚠️  可达性差异")
            lines.append("-" * 70)
            if report.a_reachable and not report.b_reachable:
                lines.append(f"  A 可达但 B 不可达 - B 的阻断原因:")
                for reason in report.b_blocked_reasons[:3]:
                    lines.append(f"    • {reason}")
            else:
                lines.append(f"  B 可达但 A 不可达 - A 的阻断原因:")
                for reason in report.a_blocked_reasons[:3]:
                    lines.append(f"    • {reason}")
            lines.append("")

        lines.append(f"📊 诅咒状态差异")
        lines.append("-" * 70)
        if report.curse_diff_notes:
            for note in report.curse_diff_notes:
                lines.append(f"  • {note}")
        else:
            all_curses = sorted(set(
                list(report.a_state_summary.keys()) + list(report.b_state_summary.keys())
            ))
            if not all_curses:
                lines.append(f"  两个节点均无诅咒状态")
            else:
                lines.append(f"  两个节点的诅咒可达状态完全相同")
                for curse in all_curses:
                    a_levels = report.a_state_summary.get(curse, [])
                    b_levels = report.b_state_summary.get(curse, [])
                    a_str = ", ".join(f"Lv.{l}" for l in a_levels) if a_levels else "无"
                    lines.append(f"    {curse}: [{a_str}]")
        lines.append("")

        lines.append(f"🗺️  来源节点差异")
        lines.append("-" * 70)
        if report.shared_sources:
            source_titles = []
            for nid in report.shared_sources:
                n = self.script.get_node(nid)
                source_titles.append(n.title if n and n.title else nid)
            lines.append(f"  共同来源: {', '.join(source_titles)}")
        else:
            lines.append(f"  共同来源: 无")

        if report.a_only_sources:
            source_titles = []
            for nid in report.a_only_sources:
                n = self.script.get_node(nid)
                source_titles.append(n.title if n and n.title else nid)
            lines.append(f"  仅 A 的来源: {', '.join(source_titles)}")

        if report.b_only_sources:
            source_titles = []
            for nid in report.b_only_sources:
                n = self.script.get_node(nid)
                source_titles.append(n.title if n and n.title else nid)
            lines.append(f"  仅 B 的来源: {', '.join(source_titles)}")

        if not report.a_only_sources and not report.b_only_sources and not report.shared_sources:
            lines.append(f"  两个节点均无可达入口")

        lines.append("")

        if not report.a_reachable:
            lines.append(f"❌ A 不可达的阻断详情")
            lines.append("-" * 70)
            for reason in report.a_blocked_reasons:
                lines.append(f"  • {reason}")
            lines.append("")

        if not report.b_reachable:
            lines.append(f"❌ B 不可达的阻断详情")
            lines.append("-" * 70)
            for reason in report.b_blocked_reasons:
                lines.append(f"  • {reason}")
            lines.append("")

        return "\n".join(lines)
