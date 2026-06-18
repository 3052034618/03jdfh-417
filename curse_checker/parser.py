"""
剧本文件解析器
格式规范：
  # 剧本标题              - 剧本标题
  * [诅咒名] 描述         - 诅咒定义
  ## 章节ID: 章节标题      - 章节开始
  ### 节点ID              - 节点开始
  @节奏: 平静|异常|追逐|揭露|崩坏  - 节奏类型
  @开始                   - 标记为起始节点
  @结局                   - 标记为结局节点
  @标签: 标签1,标签2      - 节点标签
  > +诅咒名               - 添加诅咒标记
  > -诅咒名               - 移除诅咒标记
  > ++诅咒名              - 诅咒等级+1
  > --诅咒名              - 诅咒等级-1
  ? 诅咒名>=2             - 进入条件：诅咒等级>=2
  ? !诅咒名               - 进入条件：诅咒不存在
  -> 目标节点ID           - 无选项时自动跳转
  - [选项ID] 选项文本 -> 目标节点ID  - 普通选项
  - ![选项ID] 选项文本 -> 目标节点ID - 关键误导选项
  - [选项ID]? 条件 文本 -> 目标ID     - 带条件的选项
  - [选项ID]> +诅咒名 文本 -> 目标ID  - 带诅咒效果的选项
"""

import os
import re
from typing import List, Optional, Tuple

from .models import (
    Chapter, Choice, Condition, CurseEffect, CurseOperation,
    Node, RhythmType, Script
)


class ParseError(Exception):
    """解析错误"""

    def __init__(self, message: str, line_number: int, line_content: str):
        super().__init__(f"第{line_number}行: {message}\n内容: {line_content}")
        self.line_number = line_number
        self.line_content = line_content


class ScriptParser:
    """剧本解析器"""

    def __init__(self):
        self.script: Optional[Script] = None
        self.current_chapter: Optional[Chapter] = None
        self.current_node: Optional[Node] = None
        self.line_number = 0

    def parse(self, file_path: str) -> Script:
        """解析剧本文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"剧本文件不存在: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        self.script = Script(title="未命名剧本")
        self.current_chapter = None
        self.current_node = None
        self.line_number = 0

        for line in lines:
            self.line_number += 1
            line = line.rstrip('\n').rstrip('\r')
            self._parse_line(line)

        self._validate_script()
        return self.script

    def parse_directory(self, dir_path: str) -> Script:
        """解析目录下所有剧本文件"""
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"目录不存在: {dir_path}")

        script_files = []
        for root, _, files in os.walk(dir_path):
            for f in files:
                if f.endswith('.txt') or f.endswith('.script'):
                    script_files.append(os.path.join(root, f))

        if not script_files:
            raise FileNotFoundError(f"目录 {dir_path} 下没有找到剧本文件")

        script_files.sort()
        combined_script = None

        for file_path in script_files:
            sub_script = self.parse(file_path)
            if combined_script is None:
                combined_script = sub_script
            else:
                combined_script.chapters.update(sub_script.chapters)
                combined_script.all_nodes.update(sub_script.all_nodes)
                combined_script.curse_definitions.update(sub_script.curse_definitions)

        return combined_script

    def _parse_line(self, line: str) -> None:
        """解析单行"""
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            return

        # 剧本标题
        if stripped.startswith('# '):
            self._parse_title(stripped)
            return

        # 诅咒定义
        if stripped.startswith('* '):
            self._parse_curse_definition(stripped)
            return

        # 章节
        if stripped.startswith('## '):
            self._parse_chapter(stripped)
            return

        # 节点
        if stripped.startswith('### '):
            self._parse_node(stripped)
            return

        # 属性
        if stripped.startswith('@'):
            self._parse_attribute(stripped)
            return

        # 诅咒效果
        if stripped.startswith('> '):
            self._parse_curse_effect(stripped)
            return

        # 条件
        if stripped.startswith('? '):
            self._parse_condition(stripped)
            return

        # 自动跳转
        if stripped.startswith('-> '):
            self._parse_autojump(stripped)
            return

        # 选项
        if stripped.startswith('- '):
            self._parse_choice(stripped)
            return

        # 节点内容
        if self.current_node is not None:
            if self.current_node.content:
                self.current_node.content += '\n' + line
            else:
                self.current_node.content = line

    def _parse_title(self, line: str) -> None:
        """解析剧本标题"""
        title = line[2:].strip()
        if self.script:
            self.script.title = title

    def _parse_curse_definition(self, line: str) -> None:
        """解析诅咒定义"""
        match = re.match(r'\*\s*\[([^\]]+)\]\s*(.*)', line)
        if not match:
            raise ParseError("诅咒定义格式错误，应为: * [诅咒名] 描述", self.line_number, line)

        name = match.group(1).strip()
        description = match.group(2).strip()
        if self.script:
            self.script.curse_definitions[name] = description

    def _parse_chapter(self, line: str) -> None:
        """解析章节"""
        match = re.match(r'##\s*([^:：]+)[:：]\s*(.*)', line)
        if not match:
            raise ParseError("章节格式错误，应为: ## 章节ID: 章节标题", self.line_number, line)

        chapter_id = match.group(1).strip()
        title = match.group(2).strip()

        chapter = Chapter(id=chapter_id, title=title)
        if self.script:
            self.script.chapters[chapter_id] = chapter
        self.current_chapter = chapter
        self.current_node = None

    def _parse_node(self, line: str) -> None:
        """解析节点"""
        if self.current_chapter is None:
            raise ParseError("节点必须定义在章节内", self.line_number, line)

        node_id = line[4:].strip()
        if not node_id:
            raise ParseError("节点ID不能为空", self.line_number, line)

        node = Node(
            id=node_id,
            chapter=self.current_chapter.id,
            title="",
            content="",
            rhythm=RhythmType.CALM
        )

        self.current_chapter.nodes[node_id] = node
        if self.script:
            self.script.all_nodes[node_id] = node
        self.current_node = node

    def _parse_attribute(self, line: str) -> None:
        """解析属性"""
        if self.current_node is None:
            raise ParseError("属性必须定义在节点内", self.line_number, line)

        attr_line = line[1:].strip()

        if attr_line == '开始':
            self.current_node.is_start = True
        elif attr_line == '结局':
            self.current_node.is_ending = True
        elif attr_line.startswith('节奏:'):
            rhythm_str = attr_line[3:].strip()
            try:
                self.current_node.rhythm = RhythmType.from_string(rhythm_str)
            except ValueError as e:
                raise ParseError(str(e), self.line_number, line)
        elif attr_line.startswith('标题:'):
            self.current_node.title = attr_line[3:].strip()
        elif attr_line.startswith('标签:'):
            tags_str = attr_line[3:].strip()
            self.current_node.tags = set(t.strip() for t in tags_str.split(','))
        else:
            raise ParseError(f"未知属性: {attr_line}", self.line_number, line)

    def _parse_curse_effect(self, line: str) -> None:
        """解析诅咒效果"""
        if self.current_node is None:
            raise ParseError("诅咒效果必须定义在节点或选项内", self.line_number, line)

        effect_str = line[2:].strip()
        effect = self._parse_single_curse_effect(effect_str, line)
        self.current_node.curse_effects.append(effect)

    def _parse_single_curse_effect(self, effect_str: str, line: str) -> CurseEffect:
        """解析单个诅咒效果"""
        match = re.match(r'(\+\+|--|\+|-)\s*([^\s]+)(?:\s*(\d+))?', effect_str)
        if not match:
            raise ParseError(f"诅咒效果格式错误: {effect_str}", self.line_number, line)

        op_str = match.group(1)
        name = match.group(2).strip()
        level = int(match.group(3)) if match.group(3) else 1

        try:
            operation = CurseOperation.from_string(op_str)
        except ValueError as e:
            raise ParseError(str(e), self.line_number, line)

        return CurseEffect(name=name, operation=operation, level=level)

    def _parse_condition(self, line: str) -> None:
        """解析条件"""
        if self.current_node is None:
            raise ParseError("条件必须定义在节点或选项内", self.line_number, line)

        cond_str = line[2:].strip()
        condition = self._parse_single_condition(cond_str, line)
        self.current_node.conditions.append(condition)

    def _parse_single_condition(self, cond_str: str, line: str) -> Condition:
        """解析单个条件"""
        # 否定条件: ? !诅咒名
        if cond_str.startswith('!'):
            name = cond_str[1:].strip()
            return Condition(curse_name=name, required=False)

        # 比较条件: ? 诅咒名>=2, ? 诅咒名<3, ? 诅咒名==1
        match = re.match(r'([^\s>=<!]+)\s*(>=|<=|>|<|==|!=)\s*(\d+)', cond_str)
        if match:
            name = match.group(1).strip()
            op = match.group(2)
            value = int(match.group(3))

            if op == '>=':
                return Condition(curse_name=name, min_level=value)
            elif op == '<=':
                return Condition(curse_name=name, max_level=value)
            elif op == '>':
                return Condition(curse_name=name, min_level=value + 1)
            elif op == '<':
                return Condition(curse_name=name, max_level=value - 1)
            elif op == '==':
                return Condition(curse_name=name, min_level=value, max_level=value)
            elif op == '!=':
                return Condition(curse_name=name, min_level=1, max_level=value - 1)

        # 简单存在条件: ? 诅咒名
        name = cond_str.strip()
        return Condition(curse_name=name, min_level=1)

    def _parse_autojump(self, line: str) -> None:
        """解析自动跳转"""
        if self.current_node is None:
            raise ParseError("自动跳转必须定义在节点内", self.line_number, line)

        target = line[3:].strip()
        self.current_node.next_node = target

    def _parse_choice(self, line: str) -> None:
        """解析选项"""
        if self.current_node is None:
            raise ParseError("选项必须定义在节点内", self.line_number, line)

        choice_line = line[2:].strip()
        is_mislead = False

        # 关键误导选项
        if choice_line.startswith('!'):
            is_mislead = True
            choice_line = choice_line[1:].strip()

        # 解析: [选项ID]?条件>诅咒效果 选项文本 -> 目标节点
        # 先提取选项ID
        id_match = re.match(r'\[([^\]]+)\]', choice_line)
        if not id_match:
            raise ParseError("选项格式错误，应为: - [选项ID] 文本 -> 目标ID", self.line_number, line)

        choice_id = id_match.group(1).strip()
        remaining = choice_line[id_match.end():].strip()

        conditions: List[Condition] = []
        curse_effects: List[CurseEffect] = []

        # 解析条件和诅咒效果
        while remaining:
            if remaining.startswith('?'):
                # 找到下一个空格或>或->
                space_idx = remaining.find(' ', 1)
                if space_idx == -1:
                    raise ParseError("选项条件格式错误", self.line_number, line)
                cond_str = remaining[1:space_idx].strip()
                conditions.append(self._parse_single_condition(cond_str, line))
                remaining = remaining[space_idx + 1:].strip()
            elif remaining.startswith('>'):
                space_idx = remaining.find(' ', 1)
                if space_idx == -1:
                    raise ParseError("选项诅咒效果格式错误", self.line_number, line)
                effect_str = remaining[1:space_idx].strip()
                curse_effects.append(self._parse_single_curse_effect(effect_str, line))
                remaining = remaining[space_idx + 1:].strip()
            else:
                break

        # 解析文本和目标
        arrow_match = re.search(r'\s*->\s*([^\s]+)$', remaining)
        if not arrow_match:
            raise ParseError("选项缺少目标节点，格式: -> 目标ID", self.line_number, line)

        target = arrow_match.group(1).strip()
        text = remaining[:arrow_match.start()].strip()

        choice = Choice(
            id=choice_id,
            text=text,
            target_node=target,
            conditions=conditions,
            curse_effects=curse_effects,
            is_mislead=is_mislead
        )

        self.current_node.choices.append(choice)

    def _validate_script(self) -> None:
        """验证剧本完整性"""
        if self.script is None:
            return

        if not self.script.get_start_nodes():
            raise ParseError("剧本没有定义起始节点（使用 @开始 标记）", 0, "")

        # 检查所有跳转目标是否存在
        for node in self.script.all_nodes.values():
            if node.next_node and node.next_node not in self.script.all_nodes:
                raise ParseError(
                    f"节点 {node.id} 的自动跳转目标 {node.next_node} 不存在",
                    0, ""
                )

            for choice in node.choices:
                if choice.target_node not in self.script.all_nodes:
                    raise ParseError(
                        f"节点 {node.id} 的选项 {choice.id} 的目标 {choice.target_node} 不存在",
                        0, ""
                    )
