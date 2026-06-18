# 诅咒剧情检查工具 (Curse Checker)

面向恐怖游戏开发者的命令行分支剧情分析工具。作者在本地用简单格式写下节点、选项、诅咒标记和跳转目标，运行命令后获得清晰的分析报告。

## 功能特性

### 1. 剧情结构分析 (`analyze`)
- 🔍 **不可达节点检测**: 找出永远无法到达的剧情节点
- ❌ **死选项检测**: 标记因条件无法满足而永远不会被玩家看到的选项
- 🔮 **诅咒标记分析**: 检测哪些诅咒被设置后从未影响后续剧情
- ⚔️ **结局冲突检测**: 识别进入条件互相冲突或无法区分的结局

### 2. 恐怖节奏预览 (`rhythm`)
- 🎭 **整体节奏分布**: 统计平静、异常、追逐、揭露、崩坏五种段落的比例
- 📊 **单路径节奏曲线**: 可视化每条故事线的节奏变化
- ⚠️ **节奏问题警告**: 检测过早爆点、长时间低压迫感、节奏曲线不完整等问题

### 3. 随机游玩路径生成 (`playthrough`)
- 🎮 **模拟玩家体验**: 随机生成多条游玩路径
- 🔮 **诅咒升级历程**: 记录玩家获得和升级诅咒的过程
- 🎭 **关键误导追踪**: 标记玩家经历的关键误导选项
- 📋 **完整路径摘要**: 展示关键事件和完整的节点序列

## 剧本格式

使用简单的文本格式编写剧本，后缀为 `.txt` 或 `.script`:

```text
# 剧本标题

* [诅咒名] 诅咒描述
* [镜中影] 镜中的倒影开始有了自己的意志

## 章节ID: 章节标题

### 节点ID
@开始
@节奏: 平静|异常|追逐|揭露|崩坏
@标题: 节点显示名称
@结局 (标记为结局)

> +诅咒名       添加诅咒
> -诅咒名       移除诅咒
> ++诅咒名      诅咒等级+1
> --诅咒名      诅咒等级-1

? 诅咒名>=2     进入条件
? !诅咒名       需要诅咒不存在

-> 目标节点ID   (无选项时自动跳转)

- [选项ID] 选项文本 -> 目标节点ID
- ![选项ID] 误导选项文本 -> 目标节点ID   (关键误导选项)
- [选项ID]? 条件 > +诅咒 文本 -> 目标ID  (带条件和效果)
```

## 安装

```bash
pip install -e .
```

## 使用方法

### 1. 分析剧本结构
```bash
# 分析单个文件
curse-checker analyze examples/mirror_manor.txt

# 扫描目录下所有剧本
curse-checker analyze chapters/

# 输出到文件
curse-checker analyze script.txt -o analysis_report.txt
```

### 2. 查看节奏预览
```bash
curse-checker rhythm examples/mirror_manor.txt

# 显示更多路径
curse-checker rhythm script.txt -n 10
```

### 3. 生成游玩路径
```bash
# 生成3条随机路径
curse-checker playthrough examples/mirror_manor.txt

# 生成5条路径，使用固定种子复现结果
curse-checker playthrough script.txt -n 5 -s 42
```

## 项目结构

```
curse_checker/
├── __init__.py          # 包初始化
├── __main__.py          # 模块入口
├── models.py            # 数据模型定义
├── parser.py            # 剧本文件解析器
├── analyzer.py          # 剧情分析引擎
├── rhythm.py            # 节奏分析模块
├── path_generator.py    # 随机路径生成器
├── formatter.py         # 报告格式化输出
└── cli.py               # 命令行接口
examples/
└── mirror_manor.txt     # 示例剧本
```

## 退出码含义

- `0`: 成功，未发现问题
- `1`: 执行错误（文件不存在、解析失败等）
- `2`: 分析发现问题（不可达节点、节奏警告等）
- `130`: 用户中断（Ctrl+C）

## 许可证

MIT License
