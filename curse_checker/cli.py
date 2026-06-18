"""
命令行接口
"""

import argparse
import os
import sys
from typing import Optional

from .analyzer import ScriptAnalyzer
from .formatter import ReportFormatter
from .json_export import report_to_json
from .parser import ParseError, ScriptParser
from .path_generator import PathGenerator
from .rhythm import RhythmAnalyzer


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        script = _load_script(args.input)
    except Exception as e:
        print(f"❌ 加载剧本失败: {e}", file=sys.stderr)
        return 1

    try:
        analyzer = ScriptAnalyzer(script)
        report = analyzer.analyze()
    except Exception as e:
        print(f"❌ 分析剧本失败: {e}", file=sys.stderr)
        return 1

    if getattr(args, 'json', False):
        output = report_to_json(report)
    else:
        formatter = ReportFormatter(script)
        output = formatter.format_analysis_report(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 分析报告已写入: {args.output}")
    else:
        print(output)

    return 0 if len(report.unreachable_nodes) == 0 and len(report.dead_choices) == 0 else 2


def cmd_rhythm(args: argparse.Namespace) -> int:
    """节奏分析命令"""
    try:
        script = _load_script(args.input)
    except Exception as e:
        print(f"❌ 加载剧本失败: {e}", file=sys.stderr)
        return 1

    try:
        analyzer = RhythmAnalyzer(script)
        report = analyzer.analyze()
    except Exception as e:
        print(f"❌ 节奏分析失败: {e}", file=sys.stderr)
        return 1

    formatter = ReportFormatter(script)
    output = formatter.format_rhythm_report(report, show_paths=args.show_paths)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 节奏报告已写入: {args.output}")
    else:
        print(output)

    return 0 if not report.warnings else 2


def cmd_playthrough(args: argparse.Namespace) -> int:
    """随机游玩路径命令"""
    try:
        script = _load_script(args.input)
    except Exception as e:
        print(f"❌ 加载剧本失败: {e}", file=sys.stderr)
        return 1

    try:
        generator = PathGenerator(script, seed=args.seed)
        playthrough = generator.generate(count=args.count)
    except Exception as e:
        print(f"❌ 生成游玩路径失败: {e}", file=sys.stderr)
        return 1

    formatter = ReportFormatter(script)
    output = formatter.format_playthrough_report(playthrough)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 游玩摘要已写入: {args.output}")
    else:
        print(output)

    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    try:
        script = _load_script(args.input)
    except Exception as e:
        print(f"❌ 加载剧本失败: {e}", file=sys.stderr)
        return 1

    node_ids = args.node if isinstance(args.node, list) else [args.node]

    try:
        analyzer = ScriptAnalyzer(script)
        if getattr(args, 'json', False):
            reports = []
            for nid in node_ids:
                reports.append(analyzer.explain_node(nid))
            output = report_to_json(reports if len(reports) > 1 else reports[0])
        else:
            formatter = ReportFormatter(script)
            outputs = []
            for nid in node_ids:
                report = analyzer.explain_node(nid)
                outputs.append(formatter.format_node_explain(report))
            output = "\n".join(outputs)
    except Exception as e:
        print(f"❌ 分析节点失败: {e}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 节点分析报告已写入: {args.output}")
    else:
        print(output)

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        script = _load_script(args.input)
    except Exception as e:
        print(f"❌ 加载剧本失败: {e}", file=sys.stderr)
        return 1

    if len(args.nodes) != 2:
        print("❌ compare 命令需要恰好两个节点 ID", file=sys.stderr)
        return 1

    try:
        analyzer = ScriptAnalyzer(script)
        compare_report = analyzer.compare_nodes(args.nodes[0], args.nodes[1])
        if getattr(args, 'json', False):
            output = report_to_json(compare_report)
        else:
            formatter = ReportFormatter(script)
            output = formatter.format_compare_report(compare_report)
    except Exception as e:
        print(f"❌ 对比节点失败: {e}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 对比报告已写入: {args.output}")
    else:
        print(output)

    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    try:
        script = _load_script(args.input)
    except Exception as e:
        print(f"❌ 加载剧本失败: {e}", file=sys.stderr)
        return 1

    try:
        analyzer = ScriptAnalyzer(script)
        trace_report = analyzer.trace_node(args.node, max_routes=args.max_routes)
        if getattr(args, 'json', False):
            output = report_to_json(trace_report)
        else:
            formatter = ReportFormatter(script)
            output = formatter.format_trace_report(trace_report)
    except Exception as e:
        print(f"❌ 追踪节点失败: {e}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 追踪报告已写入: {args.output}")
    else:
        print(output)

    return 0


def _load_script(path: str):
    """加载剧本文件或目录"""
    parser = ScriptParser()

    if os.path.isdir(path):
        print(f"📂 扫描目录: {path}")
        return parser.parse_directory(path)
    elif os.path.isfile(path):
        print(f"📄 解析文件: {path}")
        return parser.parse(path)
    else:
        raise FileNotFoundError(f"路径不存在: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curse-checker",
        description="诅咒剧情检查工具 - 面向恐怖游戏开发者的分支剧情分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  curse-checker analyze script.txt          # 分析单文件剧本
  curse-checker analyze script.txt --json   # 输出 JSON 格式
  curse-checker analyze chapters/           # 扫描目录下所有剧本
  curse-checker rhythm script.txt           # 查看节奏预览
  curse-checker playthrough script.txt      # 生成3条随机游玩路径
  curse-checker explain script.txt node_id  # 解释节点可达性
  curse-checker explain script.txt n1 n2 --json  # JSON 格式
  curse-checker compare script.txt n1 n2    # 对比两个节点
  curse-checker trace script.txt node_id    # 追踪起点到目标的路线
  curse-checker trace script.txt node_id -n 3 --json
        """
    )

    parser.add_argument("--version", action="version", version="%(prog)s 1.1.0")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="分析剧情结构，检测不可达节点、死选项、未使用诅咒和结局冲突"
    )
    analyze_parser.add_argument("input", help="剧本文件或目录路径")
    analyze_parser.add_argument("-o", "--output", help="输出到文件")
    analyze_parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    analyze_parser.set_defaults(func=cmd_analyze)

    rhythm_parser = subparsers.add_parser(
        "rhythm",
        help="恐怖节奏预览，分析各路径的节奏分布"
    )
    rhythm_parser.add_argument("input", help="剧本文件或目录路径")
    rhythm_parser.add_argument("-o", "--output", help="输出到文件")
    rhythm_parser.add_argument(
        "-n", "--show-paths",
        type=int,
        default=5,
        help="显示的路径数量 (默认: 5)"
    )
    rhythm_parser.set_defaults(func=cmd_rhythm)

    playthrough_parser = subparsers.add_parser(
        "playthrough",
        help="随机生成玩家游玩路径摘要"
    )
    playthrough_parser.add_argument("input", help="剧本文件或目录路径")
    playthrough_parser.add_argument("-o", "--output", help="输出到文件")
    playthrough_parser.add_argument(
        "-n", "--count",
        type=int,
        default=3,
        help="生成的路径数量 (默认: 3)"
    )
    playthrough_parser.add_argument(
        "-s", "--seed",
        type=int,
        default=None,
        help="随机种子，用于复现结果"
    )
    playthrough_parser.set_defaults(func=cmd_playthrough)

    explain_parser = subparsers.add_parser(
        "explain",
        help="解释指定节点的可达性，列出所有入口路线和诅咒状态"
    )
    explain_parser.add_argument("input", help="剧本文件或目录路径")
    explain_parser.add_argument("node", nargs="+", help="要分析的节点ID（可多个）")
    explain_parser.add_argument("-o", "--output", help="输出到文件")
    explain_parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    explain_parser.set_defaults(func=cmd_explain)

    compare_parser = subparsers.add_parser(
        "compare",
        help="对比两个节点的可达路线和诅咒状态差异"
    )
    compare_parser.add_argument("input", help="剧本文件或目录路径")
    compare_parser.add_argument("nodes", nargs=2, help="要对比的两个节点ID")
    compare_parser.add_argument("-o", "--output", help="输出到文件")
    compare_parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    compare_parser.set_defaults(func=cmd_compare)

    trace_parser = subparsers.add_parser(
        "trace",
        help="追踪从起点到目标节点的可行路线，每步显示诅咒变化"
    )
    trace_parser.add_argument("input", help="剧本文件或目录路径")
    trace_parser.add_argument("node", help="目标节点ID")
    trace_parser.add_argument("-o", "--output", help="输出到文件")
    trace_parser.add_argument(
        "-n", "--max-routes",
        type=int,
        default=5,
        help="最大路线数量 (默认: 5)"
    )
    trace_parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    trace_parser.set_defaults(func=cmd_trace)

    return parser


def main(argv: Optional[list] = None) -> int:
    """主入口函数"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except ParseError as e:
        print(f"❌ 剧本解析错误: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⏹️  操作已取消", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"❌ 未预期的错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
