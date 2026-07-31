# FigSpec：人类原生 + AI 原生的论文 Figure 渲染与版式系统

**作者**：SebDeng
**日期**：2026-07-30
**状态**：Draft v0.2（构思阶段；v0.1 → v0.2 变更见文末）

---

## 1. 问题

论文多 panel figure 的制作流程里有一个反复出现的失效模式：子图在生成阶段的尺寸和最终拼版尺寸脱节。作者用 matplotlib 默认尺寸出图，拼版时（Illustrator/Inkscape）整体缩放塞进 panel 位，图例、公式、行标题、tick label 的有效字号随之缩到 3–4 pt，印刷后不可读。这个问题往往在投稿前最后一刻、甚至被审稿人指出后才暴露，返工成本高——因为修复不是改一个文件，而是回到出图代码、重出、重拼。

根因有两层。第一层是流程顺序颠倒：应该"先定版式、按最终物理尺寸出图、1:1 拼版不缩放"，实际操作是"先出图、后缩放适配"。第二层是信息断裂：版式信息（panel 的物理尺寸）只存在于拼版者脑子里或 Illustrator 文件的隐式状态里，出图端拿不到，检查端也没有基准可校验。

AI agent 大规模进入出图工作流后，又暴露出三个新问题，它们共同定义了本工具的设计空间：

**混合来源是常态。** Agent 驱动的图越来越多，但拼图不可能全由 AI 完成——渲染图、显微图、照片这类非生成内容必然由人放置。工具必须把"人工放置的 panel"当一等公民，而不是当作要被消灭的遗留环节。

**整图生成对 agent 是上下文灾难。** 从第一天就按整张 figure 生成的话，后期任何局部调整都要求 agent 把几百行的整图代码读进上下文，改一处牵动全局。Figure 需要像软件一样模块化。

**几何调整不该消耗对话。** 把一个 panel 从 200 px 调到 250 px 这种纯几何操作，如果需要发起一整轮 agent 对话来改代码重跑，成本荒谬。确定性的重执行不需要智能。

## 2. 现有方案调研

### 2.1 版式/拼版工具

**pylustrator**（Gerum，JOSS 2020）：在 matplotlib 之上加交互式编辑器，鼠标拖拽调整 subplot 位置和大小，改动以 Python 代码形式写回源脚本，保证可复现；支持 `pylustrator.load()` 拼多个出图脚本。局限：布局是事后调整而非事先声明，没有期刊物理尺寸的一等概念，输出是 Python 代码而非工具无关的 spec，agent 无法在出图前拿到目标尺寸。

**FigureFirst**（Dickinson lab，SciPy 2017）：理念上最接近的前作，名字就叫 layout-first。用户在 Inkscape 里画矩形定义版式，SVG 经 XML 标签标注后成为 layout 文档；Python 端解析生成对应尺寸的 matplotlib axes，出完图以 SVG layer 形式写回。版式可随时在 Inkscape 调整、重跑即更新。局限：绑定 Inkscape，spec 载体是私有标签 SVG（对 agent 不是理想接口），无字号约束与事后校验，维护放缓。

**svgutils / patchworklib**：Python 侧程序化拼版。前者声明式 API 组合多个 SVG，后者用 `|`/`/` 运算符拼 matplotlib/seaborn/plotnine 图。全程代码拼版，回避了 Illustrator，也因此回避了人在视觉上自由微调的需求；缩放仍可能悄悄压缩字号，工具不校验。

**tueplots / SciencePlots**：rcParams 风格库。tueplots 按发表场合（ICML、NeurIPS 等）预置正确 figsize 和字号，是"按最终尺寸设计"在参数层的实现，但只覆盖单图参数，不管多 panel 版式与验证。

### 2.2 检查/preflight 工具

印刷业 PDF preflight（Enfocus PitStop、Acrobat Preflight、FlightCheck 及在线服务）能查 DPI、字体嵌入、出血、CMYK，部分可按阈值标记过小文本；出版社自动质检（如 Elsevier AQC）核对分辨率与格式。但它们面向印刷生产：不理解 panel，不会指出"panel c 的图例出了问题、对应哪个源文件"，输出是给印务人员的报告而非可驱动自动修复的结构化数据。学术侧只有内容型资源（各刊 figure 规格清单），是文档不是工具。

### 2.3 AI 时代的作图工具

MatPlotAgent（代码 LLM + 多模态 LLM 作图 agent，带视觉反馈迭代）、若干 Claude Code figure-generation skills、ScholarPlot MCP、FigureLabs、SciDraw AI、PaperBanana（多 agent 生成-评审-修订流水线）等。共同点：聚焦生成单张图、以期刊风格为卖点；无一处理多 panel 版式的声明与共享、拼版后校验，或人类可视化编辑器与 agent 之间的尺寸交换格式。已有的 figure 类 MCP 是"云端生成服务"形态，不是本地状态共享形态。

### 2.4 对比与空位

| 方案 | 版式先行 | 可视化编辑 | 机器可读 spec | 校验 | 增量渲染 | Agent 友好 | Illustrator 兼容 |
|---|---|---|---|---|---|---|---|
| pylustrator | ✗ | ✓ | ✗（Python 代码） | ✗ | ✗ | 弱 | ✗ |
| FigureFirst | ✓ | ✓（限 Inkscape） | 半（私有标签 SVG） | ✗ | ✗ | 弱 | ✗ |
| svgutils / patchworklib | 半 | ✗ | ✗ | ✗ | ✗ | 弱 | ✗ |
| tueplots / SciencePlots | 参数层 | ✗ | 半（rcParams） | ✗ | ✗ | 中 | 中 |
| 印刷 preflight | — | — | ✗ | 半（不分 panel） | — | ✗ | ✓ |
| AI 作图工具 | ✗ | ✗ | ✗ | 部分自检 | ✗ | ✓ | ✗ |
| **FigSpec（本构思）** | ✓ | ✓ | ✓（JSON） | ✓（含有效值） | ✓（分层 + 缓存） | ✓ | ✓ |

空位明确：没有一个工具把"人用眼睛定版式"、"机器按 spec 出图"、"成品按 spec 校验"用同一份数据串起来，更没有工具把 figure 当作可增量重渲染的持久对象。FigureFirst 证明了 layout-first 可行，tueplots 证明了场合感知参数化可行，MatPlotAgent 一系证明了 agent 出图 + 视觉反馈可行——三者互不连通。FigSpec 做的是扣起三环的 spec，和围绕它的渲染核心。

## 3. 产品定位与设计原则

FigSpec 是一个本地 figure server：核心状态（spec、panel 源、渲染产物、lint 报告）住在 server 里，人和 AI agent 是它的两个平权客户端。人类原生（GUI 拖拽、Illustrator 兼容）与 AI 原生（MCP 接口、结构化报告）从第一天起同时成立，而不是先做人的工具再补 agent 接口。五条设计原则：

**Spec 是唯一事实源。** 版式、物理尺寸、DPI、字号约束全部写在一份 JSON 里。所有客户端读写同一份状态，从结构上消灭"设计时说好 6 pt、检查时按 5 pt 放行"式的口径不一致，也消灭截图确认循环——agent 想知道现状调工具即可，不需要用户用嘴同步。

**智能与执行分离。** Agent 的产出物不是"一张图"，而是以几何为参数的 panel 源函数。几何调整（改尺寸、挪位置）是 server 的确定性重执行，亚秒级、零 token；agent 只在语义变化（改内容、改样式逻辑）时被调用。一轮对话是一次性投资，买到的是可复用的参数化源。

**Figure 是模块化的，不是单体。** 整图一把梭的生成方式使任何局部修改都要求 agent 装载全图上下文。FigSpec 把 figure 分解为 spec（接口，几百 token）+ 独立 panel 源（编译单元）+ panel 内的层（最小重渲染粒度），agent 的工作上下文永远只有当前任务涉及的那一小块，且视觉信息是按需拉取（pull）而非用户推送（push）。

**对现有工作流零强制迁移。** 不要求放弃 Illustrator，不要求全程代码拼版。只用 lint，就是投稿前检查器；只用 Designer + 渲染，就是尺寸精确的出图助手；全用，就是闭环。

**人机各司其职。** 版式是视觉决策，人拖拽；换算、执行、逐项校验是精确计算，机器做。接口处只有 spec 一种语言。Illustrator 内部状态是人的私有领地，交换货币是导出的 PDF + spec——agent 永远不假装能看见你画布里没导出的东西。

## 4. 系统设计

### 4.1 总体架构：一个核心，三张脸

```
        ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
        │  GUI(人类)    │   │  MCP(agent)  │   │  CLI(自动化)  │
        │ Designer/预览 │   │ tools + res. │   │ figlint / CI │
        └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
               └───────────────┬──┴──────────────────┘
                       ┌───────┴────────┐
                       │  FigSpec Server │
                       │  · spec 状态    │
                       │  · 渲染引擎     │←─ 分层缓存 (content hash)
                       │  · lint 引擎    │
                       │  · watch folder │←─ Illustrator 导出 final.pdf
                       └───────┬────────┘
                        panel sources (参数化函数) + assets (渲染图等)
```

所有能力在核心库实现一次：GUI 给人，MCP 给 agent，CLI 给脚本和 CI。人拖动 Designer 分隔线与 agent 调 `update_spec()` 走的是同一条状态变更路径，任一侧的修改另一侧实时可见。

### 4.2 Spec 数据结构（草案）

```json
{
  "figspec_version": "0.2",
  "target": {
    "journal_preset": "nature_double",
    "figure_width_mm": 183,
    "figure_height_mm": 105.5,
    "dpi": 600,
    "gutter_mm": 4
  },
  "constraints": {
    "min_font_pt": 6, "max_font_pt": 8,
    "min_linewidth_pt": 0.5,
    "min_effective_dpi": 300,
    "font_family": "Helvetica",
    "panel_label_style": "lowercase"
  },
  "panels": [
    {
      "label": "a",
      "type": "generated",
      "x_mm": 0, "y_mm": 0, "w_mm": 89.5, "h_mm": 50,
      "row_span": 1, "col_span": 1,
      "source": "panels/a/draw.py",
      "layers": ["data", "frame", "annotations", "legend"],
      "content_hint": "atom displacement statistics"
    },
    {
      "label": "b",
      "type": "external",
      "x_mm": 93.5, "y_mm": 0, "w_mm": 89.5, "h_mm": 50,
      "asset": "assets/stem_render.png",
      "asset_px": [2000, 1118],
      "overlay_source": "panels/b/overlay.py",
      "content_hint": "AC-STEM image, human-placed"
    }
  ]
}
```

`type` 区分两类 panel：`generated`（参数化源，server 可重渲染）与 `external`（渲染图、显微图、照片等非生成资产，人工放置，server 只做合成与校验）。像素值一律由 mm × DPI 派生，mm 是权威值。`source` 指回源文件，使 lint 报告和 agent 的修改都能精确定位。

### 4.3 Panel 源的参数化契约

`generated` panel 的源必须写成几何的纯函数：

```python
def draw(fig, ax, geometry, style):
    # geometry: {w_mm, h_mm, figsize_in, dpi}  由 server 从 spec 注入
    # style:    {font sizes, linewidths, ...}   由 constraints 派生、锁定
    ...
```

代码中禁止硬编码 figsize、字号、线宽——这是 agent skill 强制执行的契约，也是"改 200 px 到 250 px 不需要对话"得以成立的前提：resize 只是 server 用新 geometry 重调这个函数。图例位置、标注坐标必须显式给定（禁用 `loc="best"` 这类数据依赖的自动放置），原因见 4.4 的依赖分析——这本来也是出版图的最佳实践，工具顺便强制了好习惯。

### 4.4 分层增量渲染

每个 generated panel 内部再分层：数据层（真正昂贵的部分）、坐标框架层（axes/tick/spine）、标注层、图例层。各层以相同 viewBox、透明背景独立输出 SVG，合成是纯 z 轴堆叠，几何对齐由 spec 保证。每层对其输入（数据文件哈希 + 层源码哈希 + geometry + style）计算 content hash，任何变更进来时 server 只重渲染 hash 脏了的层——与增量编译同构。

依赖传播要诚实处理：数据变更可能改变轴范围，因此"数据 extent"本身是一个构建产物，coordinate 层对它声明依赖，变了就正确地连带变脏。Panel 改尺寸（aspect 变化）时数据层必须重画，这物理上绕不开，但仍是零对话的本地重执行；纯移动位置则是零重渲染的合成操作。External panel 是天然的底层，其上的 scale bar、标注是 overlay 层——改一个 scale bar 字号再也不用碰那张渲染了半小时的图。

分层的隐性收益是稳定性：未动的层 bit 级不变，产物 diff 干净，lint 结果可按层缓存。

### 4.5 MCP 接口（草案）

Tools：

| tool | 作用 |
|---|---|
| `get_spec()` / `update_spec(patch)` | 读/改版式与约束，改动触发增量重渲染并同步 GUI |
| `get_panel_source(label)` / `put_panel_source(label, code)` | 读写某 panel 的参数化源 |
| `render(label, layer?)` | 触发渲染（通常由状态变更自动触发，此为显式入口） |
| `get_panel_preview(label)` | 返回该 panel 当前渲染预览（图片直接进上下文，取代用户截图） |
| `lint(target?)` | 对当前合成或 watch folder 里的 final.pdf 跑校验，返回结构化报告 + 标注图 |
| `list_assets()` | 列出 external 资产及其原始像素尺寸 |

Resources：`figspec://spec`（当前 spec）、`figspec://report`（最新 lint 报告）、`figspec://panels/{label}/preview`。

截图确认循环由此消失：figure 的当前状态不再只存在于用户屏幕上，agent 拉取即得，且按需拉取（平时只持有几百 token 的 spec，需要看哪个 panel 才调 preview），上下文永远只装当前任务那一块。

### 4.6 Designer（人类前端）

Web GUI（已有原型验证行列网格 + 拖拽调整 + 三套数值实时显示 + 一键导出）。作为 server 客户端后的增强：版式改动即时触发受影响 panel 的本地重渲染，画布里看到的就是真实产物而非灰框占位；期刊预设（Nature 89/183、ACS 82.5/178、APS 86/172 mm 等）；v1 支持 span 覆盖 L 型布局。自由矩形 + 吸附留到后续，优先守住 spec 简单性。

### 4.7 Linter（校验引擎）

原理：PDF 中每个文字对象携带完整变换矩阵（CTM），有效字号 = 名义字号 × 累积缩放，线宽同理，可精确计算——这绕开 Illustrator 工作流的盲区：linked PDF 被缩放后，AI 字号面板显示的仍是源文件名义值。按 spec 的 panel 坐标把元素归属到对应 panel。

检查项按 panel 类型分工：vector 内容查有效字号、有效线宽、字体嵌入；raster 内容（external panel 及任何位图）查放置后有效 DPI（如 2000 px 宽的渲染图放进 60 mm panel 约 850 dpi 安全，被拉到 120 mm 只剩约 420 dpi，逼近 `min_effective_dpi` 即报）；叠加在渲染图上的 scale bar、标注在成品 PDF 里是 text object，同样被字号检查覆盖。另查总尺寸与 spec 一致性、panel 标签风格。

双输出：标注渲染图（低于阈值处红框 + "3.2 pt ✗"，给人一眼定位）与 report.json（每条违规含 panel 归属、元素类型、名义值、累积缩放、有效值、阈值、修复建议，给 agent 驱动自动迭代）。

Watch folder 集成：用户从 Illustrator 导出 final.pdf 到被监视目录，server 自动 lint，报告同时出现在 GUI 和 agent 可调用状态里。

## 5. 典型工作流

**新 figure（完整闭环）**：Designer 拖出版式 → spec 入 server → agent 按契约为各 generated panel 写参数化源 → server 渲染 → 用户将 external 资产与各 panel 产物在 Illustrator 里 1:1 拼版 → 导出到 watch folder → 自动 lint → 违规项由 agent 读报告改源、server 重渲染，人只重拼受影响的 panel。

**几何微调（零对话路径）**：拖 Designer 分隔线 / 改行高 → server 以新 geometry 重执行受影响 panel 的脏层 → 预览即时更新。全程无 agent 参与、无 token 消耗。

**语义修改（agent 路径）**：“把 panel c 图例移到右上、文案改成 pristine/irradiated” → agent 拉 spec + panel c 的 legend 层源 → 改代码写回 → server 只重渲染 legend 层。上下文 = spec + 一个层的源。

**存量稿件抢救（最低摩擦入口）**：不改任何习惯，`figlint final.pdf --width 183mm --min-font 6`（无 spec 独立模式），拿标注图逐个修。获客路径——lint 的价值第一次使用即兑现。

## 6. MVP 与路线图

**MVP：核心库 + MCP 包装。** 与 v0.1 的"先做孤立 CLI"不同——既然决定 AI 原生从第一天成立，MVP 就是核心库（spec schema、尺寸换算、lint 引擎）加薄薄一层 MCP（FastMCP 一类框架下每个核心函数包一层即一个 tool），CLI 与 GUI 是后包的皮。Lint 先行的理由不变：零侵入、价值即时、手头稿子马上能用。

**v1**：参数化契约 + generated panel 渲染 + 分层缓存；Designer 接入 server 并支持 span；watch folder；lint 按 panel 归属报告。闭环打通。

**v2**：反向导入（解析既有 AI/PDF 的 placed object 变换矩阵，反推实际版式生成初始 spec，与 lint 共用 PDF 解析代码）；检查项扩展；期刊预设库社区化；FigureFirst SVG → figspec 转换器。

## 7. 技术选型（初步）

核心与 server：Python；MCP 层用 FastMCP；渲染为 matplotlib headless 重执行（同 figsize、同 axes position 下按 artist 分组输出透明 SVG 实现分层）；缓存为文件系统 content-addressed。PDF 解析：PyMuPDF（性能与 graphics state 访问完整）或 pdfminer.six（纯 Python 易分发），标注图用 PyMuPDF 渲染 + Pillow 叠加。GUI：Web（原型为原生 JS，产品化可 React），作为 server 的前端。三组件共享 `figspec` schema 包（含 JSON Schema 校验）。

## 8. 风险与开放问题

**文字被转曲的 PDF**。Illustrator 导出若 outline 文字，lint 拿不到 text object，只能退化为"检测疑似文本的细小路径群并警告"。缓解：skill 与文档明确建议导出保留文字。

**Type 3 字体与旋转文字**。部分 matplotlib 配置以 Type 3 嵌字，字号计算路径不同；旋转文字的有效字号取矩阵奇异值。工程可解，需测试集覆盖。

**matplotlib 自动行为打穿分层**。`loc="best"` 等数据依赖放置引入隐式数据→图例依赖边。对策：契约禁用自动放置（4.3），server 校验源码合规。

**panel 归属鲁棒性**。成品 PDF 元素坐标与 spec 可能有出入（用户微调过），归属算法需容差与"无法归属"兜底。

**Server 常驻的接受度**。本地 server + watch folder 比一次性 CLI 重。缓解：CLI 独立模式保留，server 按需启动。

**Designer 表达力 vs. spec 简单性**。行列 + span 守住 v1，收集真实版式样本再决定是否引入自由矩形。

**与 FigureFirst 的关系**。理念同源，文档致谢并提供迁移转换器，吸纳存量用户而非对立。

---

## 附：v0.1 → v0.2 变更记录

其一，架构从"三个松散组件"改为 server-centric：一个本地 server 持有全部状态，GUI/MCP/CLI 三客户端，人机双原生从第一天成立，MVP 相应改为核心库 + MCP。其二，新增设计原则"智能与执行分离"与 panel 源参数化契约：agent 产出参数化函数而非图，几何调整走零对话的本地重执行。其三，新增分层增量渲染模型（层级 content hash 缓存、依赖传播、显式放置要求）。其四，panel 增加 `type` 字段区分 generated/external，raster 内容纳入有效 DPI 校验，人工放置成为架构一等公民。其五，新增"per-panel 分解与上下文经济"论证：spec 是 agent 上下文的隔离边界，视觉信息按需拉取。

*本文档基于 2026-07 的原型讨论与公开资料调研；相关项目现状以当时可查证信息为准。*
