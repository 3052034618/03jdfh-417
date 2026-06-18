"""
命令行接口
"""

import argparse
import os
import sys
from typing import Optional

from .analyzer import ScriptAnalyzer
from .formatter import ReportFormatter
from .parser import ParseError, ScriptParser
from .path_generator import PathGenerator
from .rhythm import RhythmAnalyzer


def cmd_analyze(args: argparse.Namespace) -> int:
    """剧情分析命令"""
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
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="curse-checker",
        description="诅咒剧情检查工具 - 面向恐怖游戏开发者的分支剧情分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  curse-checker analyze script.txt          # 分析单文件剧本
  curse-checker analyze chapters/           # 扫描目录下所有剧本
  curse-checker rhythm script.txt           # 查看节奏预览
  curse-checker rhythm script.txt -o rhythm_report.txt
  curse-checker playthrough script.txt      # 生成3条随机游玩路径
  curse-checker playthrough script.txt -n 5 --seed 42
        """
    )

    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # analyze 命令
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="分析剧情结构，检测不可达节点、死选项、未使用诅咒和结局冲突"
    )
    analyze_parser.add_argument("input", help="剧本文件或目录路径")
    analyze_parser.add_argument("-o", "--output", help="输出到文件")
    analyze_parser.set_defaults(func=cmd_analyze)

    # rhythm 命令
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

    # playthrough 命令
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
