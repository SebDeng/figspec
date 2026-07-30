# FigSpec：面向人和 AI Agent 的论文 Figure 版式工具链

**作者**：SebDeng
**日期**：2026-07-30
**状态**：Draft v0.1（构思阶段）

---

## 1. 问题

论文多 panel figure 的制作流程里有一个反复出现的失效模式：子图在生成阶段的尺寸和最终拼版尺寸脱节。作者用 matplotlib 默认尺寸出图，拼版时（Illustrator/Inkscape）整体缩放塞进 panel 位，图例、公式、行标题、tick label 的有效字号随之缩到 3–4 pt，印刷后不可读。这个问题往往在投稿前最后一刻、甚至被审稿人指出后才暴露，返工成本高——因为修复不是改一个文件，而是回到出图代码、重出、重拼。

根因有两层。第一层是流程顺序颠倒：应该"先定版式、按最终物理尺寸出图、1:1 拼版不缩放"，实际操作是"先出图、后缩放适配"。第二层是信息断裂：版式信息（panel 的物理尺寸）只存在于拼版者脑子里或 Illustrator 文件的隐式状态里，出图端（无论是人写的脚本还是 AI agent）拿不到，检查端也没有一个明确的基准可以校验。

AI agent 进入出图工作流后，这个断裂变得更尖锐也更值得解决：agent 完全有能力按精确尺寸出图，前提是有人把精确尺寸以机器可读的方式告诉它；agent 也完全有能力根据检查报告自动迭代修复，前提是检查结果是结构化的而不是"肉眼看着有点小"。

## 2. 现有方案调研

### 2.1 版式/拼版工具

**pylustrator**（Gerum，JOSS 2020）：在 matplotlib 之上加了一个交互式编辑器，鼠标拖拽调整 subplot 位置和大小、加文字标注，改动以 Python 代码形式写回源脚本，保证可复现。也支持用 `pylustrator.load()` 把多个出图脚本拼成 panel。它解决的是"matplotlib 里手调布局太痛苦"和"Illustrator 手工修改不可复现"两个问题。局限：布局仍然是"事后调整"而非"事先声明"，没有期刊物理尺寸的概念作为一等公民，输出是 Python 代码而非独立于工具的 spec，agent 无法在出图之前拿到目标尺寸。

**FigureFirst**（Dickinson lab，SciPy 2017）：与本构思在理念上最接近的前作，名字就叫"layout-first"。用户在 Inkscape 里画一组矩形定义版式，SVG 文件经 XML 标签标注后成为 layout 文档；Python 端解析它生成对应位置和尺寸的 matplotlib axes，出完图再写回 SVG 的数据层。版式可以随时在 Inkscape 里调整，重跑脚本即可更新。局限：绑定 Inkscape（对 Illustrator 用户不友好），spec 载体是带私有 XML 标签的 SVG（对人可编辑但对 agent 不是理想的接口），没有字号约束和事后校验环节，项目维护已放缓。

**svgutils / patchworklib**：Python 侧的程序化拼版方案。svgutils 用声明式 API 把多个 SVG 按坐标和缩放组合成大图；patchworklib 借鉴 R 的 patchwork，用 `|` 和 `/` 运算符拼 matplotlib/seaborn/plotnine 图。两者都把拼版留在代码里，回避了 Illustrator，但也因此回避了"人在视觉上自由微调"的需求——这正是很多人离不开 Illustrator 的原因。且缩放仍然可能悄悄压缩字号，工具本身不做校验。

**tueplots / SciencePlots**：rcParams 风格库。tueplots 尤其相关——它按发表场合（ICML、NeurIPS、AISTATS 等）预置正确的 figsize 和字号，是"按最终尺寸设计"理念在参数层的实现。但它只覆盖单图参数，不管多 panel 版式，也不管拼版后的验证。

**R 生态（patchwork / cowplot）**：解决同类问题，思路与 patchworklib 同源，全程代码内拼版，不在本工具链的直接对标范围但可作交互设计参考。

### 2.2 检查/preflight 工具

印刷行业的 PDF preflight 工具（Enfocus PitStop、Acrobat Preflight、FlightCheck 及一批在线服务）能检查 DPI、字体嵌入、出血、CMYK、部分工具可按阈值标记过小文本。Elsevier 等出版社的自动质检（AQC）也会核对分辨率和格式。但这些工具都面向印刷生产，不面向科研作图场景：它们不理解"panel"这个概念，不会告诉你"是 panel c 里的图例出了问题、对应哪个源文件"，输出是给印务人员看的报告而不是机器可读、可驱动自动修复的结构化数据。学术侧目前只有内容型资源（如 ScholarViz 整理的各刊 figure 规格和检查清单），是文档不是工具。

### 2.3 AI 时代的作图工具

2024 年以来出现了一批 LLM 作图方案：MatPlotAgent（代码 LLM + 多模态 LLM 的作图 agent，带视觉反馈迭代）、若干 Claude Code skills（按 MatPlotAgent 三阶段流水线生成 publication-ready 图，检查色盲友好配色和印刷字号）、ScholarPlot MCP、FigureLabs、SciDraw AI、PaperBanana（多 agent 生成-评审-修订流水线）等。共同特点：都聚焦"生成单张图"，以期刊风格为卖点；没有一家处理多 panel 版式的声明、共享和事后校验，也没有一家定义人类可视化编辑器与 agent 之间的尺寸交换格式。

### 2.4 对比与空位

| 方案 | 版式先行 | 可视化编辑 | 机器可读 spec | 字号/线宽校验 | Agent 友好 | Illustrator 兼容 |
|---|---|---|---|---|---|---|
| pylustrator | ✗（事后调整） | ✓ | ✗（Python 代码） | ✗ | 弱 | ✗ |
| FigureFirst | ✓ | ✓（限 Inkscape） | 半（私有标签 SVG） | ✗ | 弱 | ✗ |
| svgutils / patchworklib | 半 | ✗ | ✗ | ✗ | 弱 | ✗ |
| tueplots / SciencePlots | 参数层 ✓ | ✗ | 半（rcParams） | ✗ | 中 | 中 |
| 印刷 preflight（PitStop 等） | — | — | ✗ | 半（不分 panel、不面向科研） | ✗ | ✓ |
| AI 作图工具（MatPlotAgent 等） | ✗ | ✗ | ✗ | 部分自检 | ✓ | ✗ |
| **FigSpec（本构思）** | ✓ | ✓（Web） | ✓（JSON） | ✓（含缩放后有效值） | ✓ | ✓ |

空位很明确：**没有一个工具把"人用眼睛定版式"、"机器按 spec 出图"、"成品按 spec 校验"三件事用同一份数据串起来**。FigureFirst 证明了 layout-first 可行，tueplots 证明了场合感知的参数化可行，MatPlotAgent 一系证明了 agent 出图 + 视觉反馈迭代可行——但三者互不连通。FigSpec 的定位不是再造其中任何一环，而是做那份把三环扣起来的 spec，以及围绕它的最小工具集。

## 3. 产品定位与设计原则

FigSpec 是一个以单一 spec 文件为中心的工具链，服务两类使用者：写论文的研究者（人）和辅助出图的 AI agent。三条设计原则：

**Spec 是唯一事实源。** 版式、物理尺寸、DPI、字号约束全部写在一份 JSON 里。设计器写它，生成器读它，校验器拿它当基准。任何"设计时说好 6 pt、检查时按 5 pt 放行"的口径不一致，都源于多份隐式约定，单一 spec 从结构上消灭这类问题。

**对现有工作流零强制迁移。** 不要求用户放弃 Illustrator，不要求全程代码拼版。三个组件各自独立可用：只用校验器，就是一个投稿前的 lint；只用设计器 + 生成器，就是一个尺寸精确的出图助手；全用，就是闭环。工具适配工作流，不是反过来。

**人机各司其职。** 版式是视觉决策，交给人拖拽；尺寸换算、参数锁定、逐字号核验是精确计算，交给机器。接口处只有 spec 一种语言。

## 4. 系统设计

三个组件围绕一份 spec：

```
  ┌─────────────┐   figspec.json    ┌─────────────┐
  │  Designer    │ ───────────────→ │  Generator   │
  │  版式设计器   │                  │  出图生成器   │
  └─────────────┘                  └──────┬──────┘
        ↑                                  │ 1:1 PDF/SVG per panel
        │ 反馈修改版式                       ↓
        │                          Illustrator 拼版（不缩放）
        │                                  │ final.pdf
  ┌─────┴───────┐   report.json     ┌─────┴───────┐
  │  人 / Agent  │ ←─────────────── │   Linter     │
  │  迭代修复     │                  │  成品校验器   │
  └─────────────┘                  └─────────────┘
```

### 4.1 Designer（版式设计器）

Web 端交互组件（已有原型验证）。功能：选择期刊预设（Nature 89/183 mm、ACS 82.5/178 mm、APS 86/172 mm 等）或自定义总宽；行列结构划分 panel，拖分隔线调宽度比例、拖行底边调行高；选中 panel 实时显示三套数值——毫米（物理真值）、像素（@设定 DPI）、matplotlib figsize 英寸值；一键导出 spec。导出动作直接把 JSON 发进 agent 对话上下文，agent 即刻获得每个 panel 的精确坐标和尺寸。

原型已验证的行列网格结构覆盖约八成常见 figure；v1 需要支持 span（一个 panel 跨多行/多列，覆盖"左侧大 panel + 右侧竖排小 panel"的 L 型布局）。自由矩形 + 吸附留到后续版本，优先保证 spec 结构简单。

### 4.2 Generator（出图生成器）

一个轻量 Python 库 + 一份 agent skill。核心函数：读 spec，为指定 panel 返回锁定好的 `plt.subplots(figsize=...)` 骨架和 rcParams（字体、字号 ≥ spec 的 `min_font_pt`、线宽、tick 尺寸全部固定），保证出图即 1:1 最终尺寸。skill 部分（SKILL.md）向 agent 说明工作流约定："画论文图先要 spec → 没有就引导用户用 Designer 或口头确认尺寸 → 严格按 figsize 出图 → 提醒用户拼版时 100% 摆放不缩放"，并附常见期刊规格表和单位换算。

Generator 不重新发明绘图——它只是 matplotlib 之上薄薄一层尺寸纪律。用户/agent 在返回的 axes 上照常作画。与 tueplots 的关系是互补：tueplots 管风格场合，FigSpec 管版式几何，可以叠用。

### 4.3 Linter（成品校验器）

命令行工具：`figlint final.pdf --spec figspec.json`（无 spec 时可退化为 `--width 183mm --min-font 6` 的独立模式）。原理：PDF 中每个文字对象携带完整的变换矩阵（CTM），有效字号 = 名义字号 × 累积缩放系数，线宽同理，均可精确计算——这绕开了 Illustrator 工作流的一个盲区：linked PDF 被缩放后，AI 界面字号面板显示的仍是源文件的名义值，拼版者根本看不到真实有效字号。

技术路径：pdfminer.six 或 PyMuPDF 解析 text object 与 graphics state，按 spec 中的 panel 坐标把每个元素归属到对应 panel。双输出：

其一，**标注渲染图**（PNG）——原图之上，低于阈值的文字框红框高亮并标注有效值（如"3.2 pt ✗"），给人一眼定位。

其二，**结构化报告**（report.json）——每条违规包含 panel 归属、元素类型（tick label / legend / annotation）、名义值、累积缩放、有效值、阈值、建议修复方向（放大源字号至 X pt，或减少该 panel 缩放至 Y%）。这是给 agent 的接口：agent 读报告 → 改出图代码或改 spec → 重新出图 → 用户重拼 → 再 lint,形成收敛的闭环。

检查项从字号起步，逐步扩展：最小线宽（各刊普遍要求 ≥ 0.25–0.5 pt）、字体嵌入、总尺寸与 spec 一致性、panel 标签风格（Nature 小写 vs Cell 大写）、色彩模式提示。

### 4.4 Spec 数据结构（草案）

```json
{
  "figspec_version": "0.1",
  "target": {
    "journal_preset": "nature_double",
    "figure_width_mm": 183,
    "figure_height_mm": 105.5,
    "dpi": 600,
    "gutter_mm": 4
  },
  "constraints": {
    "min_font_pt": 6,
    "max_font_pt": 8,
    "min_linewidth_pt": 0.5,
    "font_family": "Helvetica",
    "panel_label_style": "lowercase"
  },
  "panels": [
    {
      "label": "a",
      "x_mm": 0, "y_mm": 0,
      "w_mm": 89.5, "h_mm": 50,
      "w_px": 2114, "h_px": 1181,
      "figsize_in": [3.524, 1.969],
      "row_span": 1, "col_span": 1,
      "source": "plots/panel_a.py",
      "content_hint": "STEM image + FFT inset"
    }
  ]
}
```

`source` 和 `content_hint` 字段让 Linter 的报告能直接指回源文件，也让 agent 在多 panel 项目里维持出图脚本与版式的对应关系。像素值是派生量（由 mm 和 DPI 算出），写入 spec 是为了 agent 免换算直接使用；mm 是权威值。

### 4.5 反向导入（v2 方向）

理想工作流中用户可能已经在 Illustrator 里摆了草稿。反向工具解析现有 AI/PDF 文件中 placed object 的位置与变换矩阵，反推出实际版式（"panel b 实际被缩放到 43%"），生成初始 spec。这样 Designer 管从零开始，反向导入管存量迁移，两者产出同一格式,与 Linter 共用同一套 PDF 解析代码。

## 5. 典型工作流

**新figure（完整闭环）**：Designer 里拖出版式 → 导出 spec 给 agent → agent 按 spec 逐 panel 出图（1:1 PDF）→ 用户 Illustrator 拼版，只摆放不缩放 → 导出成品 → `figlint final.pdf --spec figspec.json` → 通过则投稿，违规则报告回给 agent 自动修复重出。

**存量稿件抢救（最低摩擦入口）**：不改任何画图习惯，拼完的 PDF 直接 `figlint final.pdf --width 183mm --min-font 6`，拿标注图逐个修。这是获客路径——lint 的价值第一次使用就兑现。

**纯代码流（无 Illustrator）**：spec → Generator 生成整图 gridspec 骨架 → 全代码出整张 figure。适合数据频繁更新、需要完全可复现的场景，此时 FigSpec 相当于给 subplot_mosaic 加了物理尺寸和约束层。

## 6. MVP 与路线图

**MVP（先做 Linter）**。理由：对现有工作流零侵入，价值即时兑现，且手头稿子马上能用。范围：PDF 有效字号 + 有效线宽计算，阈值命令行参数化，标注 PNG + report.json 双输出，先不要求 spec（独立模式）。核心解析逻辑估计数百行 Python。

**v1**：Designer 补 span 支持 → spec 格式定稿 → Generator 库 + agent skill → Linter 接受 spec 输入并按 panel 归属报告。闭环打通。

**v2**：反向导入；检查项扩展（字体嵌入、标签风格、色彩提示）；期刊预设库社区化维护；考虑 MCP server 形态使任意 agent 环境可调用。

## 7. 技术选型（初步）

Designer：Web（现原型为原生 JS，产品化可考虑 React），无后端硬依赖，spec 即导出物。Generator：纯 Python，依赖仅 matplotlib；skill 为 Markdown 文档。Linter：Python，PDF 解析选 PyMuPDF（性能好、graphics state 访问完整）或 pdfminer.six（纯 Python 易分发），标注渲染用 PyMuPDF 的 page 渲染 + Pillow 叠加。三者共享一个 `figspec` schema 包（含 JSON Schema 校验）。

## 8. 风险与开放问题

**文字被转曲的 PDF**。Illustrator 导出时若 outline 了文字，Linter 拿不到 text object,只能退化为"检测疑似文本的细小路径群并警告"。缓解：在 skill 和文档中明确建议导出流程保留文字。

**Type 3 字体与非常规变换**。部分 matplotlib 后端配置会以 Type 3 嵌字，字号计算路径不同；旋转文字（纵轴标题）的有效字号取矩阵奇异值而非简单缩放系数。工程上都可解，但需要测试集覆盖。

**panel 归属的鲁棒性**。成品 PDF 里元素坐标与 spec 的 panel 框可能有出入（用户微调过位置）。归属算法需要容差和"无法归属"的兜底类别。

**Designer 表达力 vs. spec 简单性**。自由布局诉求会持续存在,但 spec 一旦复杂，Generator 和 Linter 的实现成本同步上升。策略：行列 + span 守住 v1，收集真实 figure 版式样本再决定是否引入自由矩形。

**与 FigureFirst 的关系**。理念同源，值得在文档中致谢并考虑提供 FigureFirst SVG → figspec.json 的转换器，吸纳其存量用户而非对立。

---

*附：本文档基于 2026-07 的原型讨论与公开资料调研；相关项目现状（pylustrator 1.3.0、FigureFirst、svgutils、patchworklib、tueplots、MatPlotAgent 及各 AI 作图工具）以当时可查证信息为准。*
