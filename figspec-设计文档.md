# FigSpec：人类原生 + AI 原生的论文 Figure 渲染与版式系统

**作者**：SebDeng
**日期**：2026-07-30
**状态**：Draft v0.3（构思阶段；v0.1 → v0.2 → v0.3 变更见文末。v0.3 吸收三路架构/渲染/agent 经济学评审与渲染 spike 实证结果）

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

### 2.5 实现现状（2026-07-30）

Linter 已作为 `figspec` 包 + `figspec lint` CLI 发布（有效字号/线宽/DPI 校验、pikepdf 自研解释器、Form XObject 递归）；Designer 已作为 PySide6 macOS 应用发布（分割树画布、期刊预设与每预设约束、figspec.json 导出/往返、签名分发管线）；期刊预设数值经四社官方一手来源核验（见 `docs/journal-figure-specs.md`）。2026-07-31 起 Designer 增内容替身（五 archetype 排版预演，约束派生取值）、实寸模式（fit/1:1/手动缩放 + 屏幕校准）、磅尺样张条、手作图缩放真相（源 DPI 声明、名义↔有效换算、作图卡片）与 PDF 资产拖入即预报（lint 解释器 × 虚拟缩放，`figspec.scaling`/`figspec.standins` 供 MCP 复用），见 `docs/superpowers/specs/2026-07-31-standin-truescale-design.md`；另增 Illustrator 拼版底板与单 panel 画板导出（物理尺寸精确、OCG 分层、资产 1:1 预置的 PDF，`figspec.board`，见 `docs/superpowers/specs/2026-07-31-illustrator-board-design.md`）。本文档后续章节的 server/渲染部分为待建内容。

## 3. 产品定位与设计原则

FigSpec 是一个本地 figure server：人和 AI agent 是它的两个平权客户端。人类原生（GUI 拖拽、Illustrator 兼容）与 AI 原生（MCP 接口、结构化报告）从第一天起同时成立，而不是先做人的工具再补 agent 接口。六条设计原则：

**项目目录是持久真相，server 是物化视图。** figspec.json、panels/ 源码、assets/ 资产全部住在项目目录里、进 git；server 只是它们之上的构建守护进程（渲染缓存、lint 报告等派生物放 `.figspec/cache/`，gitignore）。server 崩溃 = 零数据丢失，重启 = 重扫描。这一条决定了协作语义（git 是版本真相）、崩溃语义（无内存权威）和多客户端引导（谁先起谁拉起守护进程）。

**Spec 是唯一事实源。** 版式、物理尺寸、DPI、字号约束全部写在一份 JSON 里。所有客户端读写同一份状态，从结构上消灭"设计时说好 6 pt、检查时按 5 pt 放行"式的口径不一致，也消灭截图确认循环——agent 想知道现状调工具即可，不需要用户用嘴同步。并发由 spec 级单调 revision 保障：`update_spec(patch, base_revision)` 过期即冲突拒绝，GUI 拖拽手势期间对被拖路径持短租约，双向变更通知（GUI 走 WebSocket，MCP 走 resource 订阅）。

**智能与执行分离。** Agent 的产出物不是"一张图"，而是以几何为参数的 panel 源函数。几何调整的**执行**是 server 的确定性重执行，亚秒级、零 token；几何变化引发的**布局劣化**（aspect 改变后图例压线、标注遮挡）才值得一轮对话——server 渲染后做廉价的包围盒重叠/裁切检测，把劣化变成结构化信号而非静默变丑。一轮对话是一次性投资，买到的是可复用的参数化源。

**Figure 是模块化的，不是单体。** 整图一把梭的生成方式使任何局部修改都要求 agent 装载全图上下文。FigSpec 把 figure 分解为 spec（接口）+ 独立 panel 源（编译单元），agent 的工作上下文永远只有当前任务涉及的那一小块，且视觉信息是按需拉取（pull）而非用户推送（push）。上下文经济的正确口径是**比值**而非绝对值：读状态数百 token；改一个 panel（spec + 契约 skill + 数据窥探 + 源码读写 + 数轮受限尺寸 preview）约 6–15k token；单体整图方案数万 token 且每轮重付。省的大头在"跨轮免重述"——server 持状态，agent 不必每轮重贴代码。

**对现有工作流零强制迁移。** 不要求放弃 Illustrator，不要求全程代码拼版。只用 lint，就是投稿前检查器；只用 Designer + 渲染，就是尺寸精确的出图助手；全用，就是闭环。

**人机各司其职。** 版式是视觉决策，人拖拽；换算、执行、逐项校验是精确计算，机器做。接口处只有 spec 一种语言。Illustrator 内部状态是人的私有领地，交换货币是导出的 PDF + spec——agent 永远不假装能看见你画布里没导出的东西。

## 4. 系统设计

### 4.1 总体架构：单守护进程，三张脸

```
        ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
        │  GUI(人类)    │   │  MCP(agent)  │   │  CLI(自动化)  │
        │ PySide6      │   │  stdio 瘦代理 │   │ figspec / CI │
        │ Designer/预览 │   │ tools + res. │   │  独立模式保留 │
        └──────┬───────┘   └──────┬───────┘   └──────┬──────┘
            WS │            连接或拉起 │               │
               └───────────────┬──┴──────────────────┘
                       ┌───────┴────────┐
                       │ FigSpec 守护进程 │  每项目一个
                       │ · spec + revision│  .figspec/server.lock (port+pid)
                       │ · 渲染引擎      │←─ 缓存 (.figspec/cache/, content hash)
                       │ · lint 引擎     │
                       │ · watch folder  │←─ Illustrator 导出 final.pdf
                       └───────┬────────┘
                项目目录（持久真相）: figspec.json + panels/ + assets/
```

**实例模型是这版架构唯一不能妥协的地基**：MCP server 通常被 agent host 以 stdio 拉起，若把引擎直接嵌进 stdio 进程，GUI 无处可连、两个实例即 split-brain，"人机共享同一份状态"第一天就失效。因此引擎住在**每项目单守护进程**里（`.figspec/server.lock` 记录 port+pid），MCP stdio 层是瘦代理：发现已有守护进程就连接，没有就拉起。这同时回答了多项目并存（按项目目录 scope）与"agent 调用时 server 没跑"（代理自动拉起）。所有能力在核心库实现一次：GUI 给人，MCP 给 agent，CLI 给脚本和 CI。人拖 Designer 分隔线与 agent 调 `update_spec()` 走同一条带 revision 的状态变更路径，任一侧修改经变更通知对另一侧实时可见。

Watch folder 的生命周期要点：Illustrator 写 PDF 非原子，需 mtime 静默去抖；守护进程停机期间的导出靠启动时 mtime 对账补 lint。

### 4.2 Spec 数据结构（草案）

```json
{
  "figspec_version": "0.3",
  "target": {
    "journal_preset": "nature_double",
    "figure_width_mm": 183,
    "figure_height_mm": 105.5,
    "dpi": 600,
    "gutter_mm": 4
  },
  "constraints": {
    "min_font_pt": 5, "max_font_pt": 7,
    "min_linewidth_pt": 0.25,
    "min_effective_dpi": 300,
    "font_family": "Helvetica",
    "panel_label_style": "lowercase"
  },
  "panels": [
    {
      "label": "a",
      "type": "generated",
      "x_mm": 0, "y_mm": 0, "w_mm": 89.5, "h_mm": 50,
      "source": "panels/a/draw.py",
      "layers": ["frame_below", "data", "frame_above", "annotations", "legend"],
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
  ],
  "designer": { "tree": { "…": "布局树 sidecar，供 Designer 往返编辑，其他工具忽略" } }
}
```

`type` 区分两类 panel：`generated`（参数化源，server 可重渲染）与 `external`（渲染图、显微图、照片等非生成资产，人工放置，server 只做合成与校验）。像素值一律由 mm × DPI 派生，mm 是权威值；坐标约定为左上原点、y 向下（已在 `figspec/spec.py` 固化为规范）。`source` 指回源文件，使 lint 报告和 agent 的修改都能精确定位。`type` 省略时语义为"仅版式占位"，因此已发布的 0.1 格式文件天然前向兼容。

**多客户端兼容铁律**：解析器按版本分派且**必须容忍未知键**；任何工具改写 spec 时**必须保留自己不认识的顶层段**（否则 agent 的一次 `update_spec` 会悄悄剥掉 `designer.tree`）。constraints 示例值即 Nature 预设（已发布的每预设约束表见 `docs/journal-figure-specs.md`）。

### 4.3 Panel 源的参数化契约

`generated` panel 的源必须写成几何的纯函数：

```python
def draw(fig, ax, geometry, style):
    # geometry: {w_mm, h_mm, figsize_in, dpi}  由 server 从 spec 注入
    # style:    {font sizes, linewidths, ...}   由 constraints 派生、锁定
    ...
```

契约的执行分三层，缺一不可：

**结构性预防**：fig/ax 由 server 创建后注入——figsize 硬编码在结构上不可能；尺寸类数值只能从 style 对象取，源码中的字号/线宽数字字面量直接被 lint。

**静态校验**：`validate_source` 检查显式放置——注意 `legend()` **不带参数的默认值就是 `loc='best'`**，因此规则不是"禁止字符串 best"而是"必须显式给出 loc"；同族禁令覆盖 `tight_layout`/`constrained_layout`/`bbox_inches='tight'`（它们会破坏分层几何对齐，见 4.4）。静态校验约能拦八九成，agent 肌肉记忆写 `plt.legend()` 时报错文案要可执行（"缺 loc=，契约要求显式位置"），通常一轮收敛。

**性质测试兜底**：用两组 geometry 各渲一次，若 legend/annotations 层的输出随数据或几何漂移，即为隐式依赖违约——比任何静态规则都难绕过。

显式放置本来也是出版图的最佳实践，工具顺便强制了好习惯。

### 4.4 分层渲染模型（分层为 v1 合成语义，增量缓存降为 v2）

分层的正确切法是**五层**而非四层——spike 实证发现 grid 的 z 序在数据之下、spines 在数据之上，"坐标框架"一层在 z 序上是错的：`frame_below`（axes patch + grid）→ `data` → `frame_above`（spines/ticks/labels）→ `annotations` → `legend`。各层以相同 viewBox、透明背景独立输出 SVG，合成是纯 z 轴堆叠。

分层成立的渲染纪律（全部经 matplotlib spike 验证）：固定 figsize + 显式 axes 定位，**禁用 tight/constrained layout**（它们按 artist 边界改几何，各层 viewBox 会分道扬镳）；渲染前先做一次 **extent 计算 pass**——"数据 extent"本身是构建产物，坐标层对它声明依赖，数据变了 frame 层正确连带变脏（否则复用缓存的 frame 会产生真实几何错位，不只是刻度文字过期）；确定性归一化（固定 `svg.hashsalt`、元数据去时间戳）后同输入跨进程逐字节一致，content-hash 缓存地基成立；每层 = 全量构建 + 可见性掩码 + 独立导出，单 panel 全渲成本约 5× 单次绘制，增量收益只在跨编辑复用时兑现。

**工程排序上，层级 content-hash 增量缓存降为 v2**：它是全文档投机性最强的部分，而其价值前提"panel 渲染很贵"对典型 1–3 秒的 panel 不成立（大散点/imshow 用 `rasterized=True` 在平渲染里就地解决）。v1 先做**不分层的整 panel 重渲染**——零对话 resize 的主张靠参数化契约就已成立，不依赖分层。spec 保留 `layers` 字段做前向兼容。External panel 天然是底层，其上的 scale bar、标注是 overlay 层——改一个 scale bar 字号不再碰渲染了半小时的图（overlay 复用 generated 渲染机器，随 v1.5 落地）。分层的隐性收益是稳定性：未动的层 bit 级不变，产物 diff 干净，lint 结果可按层缓存。

### 4.5 MCP 接口（草案）

Tools：

| tool | 作用 |
|---|---|
| `get_spec()` | 读 spec（含当前 revision） |
| `update_spec(patch, base_revision)` | JSON Merge Patch 改版式与约束；revision 过期即冲突拒绝；返回新 spec 免二次读取 |
| `get_panel_source(label)` / `put_panel_source(label, code)` | 读写某 panel 的参数化源。put 一响应三事：契约校验结果（违规明细）、渲染结果（含 traceback）、preview 就绪——省掉 put→render→查错三轮往返 |
| `validate_source(label, code)` | 写盘前的契约预检，错误文案可执行 |
| `render(label?)` | 显式触发渲染（通常由状态变更自动触发） |
| `get_panel_preview(label, max_px=800)` | 单 panel 预览，默认限长边 800px（约 0.6–0.9k token），全分辨率显式要 |
| `get_figure_preview()` | 整图合成预览——看整体观感时一张图优于 N 张 panel 图 |
| `lint(target?, panel?)` | 对当前合成或 watch folder 的 final.pdf 跑校验，支持单 panel 作用域；报告 JSON 与已发布 figlint 的 finding 格式同构 |
| `revert(revision)` | 回滚 spec（panel 源靠 server 自动 git commit 兜底） |
| `list_assets()` | 列出 external 资产及其原始像素尺寸 |

Resources：`figspec://spec`、`figspec://report`、`figspec://panels/{label}/preview`，支持订阅通知。

源码读写粒度为 **panel 级**（一 panel 一文件，层是文件内的命名函数）——不提供层级读写接口，诚实换简单。截图确认循环由此消失：figure 状态不再只存在于用户屏幕上，agent 拉取即得、按需拉取，上下文永远只装当前任务那一块。

### 4.6 Designer（人类前端）

**PySide6 桌面应用（已发布）**：分割树画布 + 自定义分隔条（实时 mm 反馈、0.5mm 吸附）+ 期刊预设与每预设约束 + 三套数值检查器 + undo/redo + figspec.json 导出/往返 + Developer ID 签名分发管线。接入 server 后的增强：版式改动即时触发受影响 panel 的本地重渲染，画布里看到的就是真实产物而非灰框占位。协议做成客户端无关（HTTP+JSON/WS），Web 客户端留作未来选项而非重写目标；Designer 保留单机模式（"零强制迁移"原则推广到 GUI 自身）。自由矩形 + 吸附留到后续，优先守住 spec 简单性。

### 4.7 Linter（校验引擎，已发布）

原理：PDF 中每个文字对象携带完整变换矩阵（CTM），有效字号 = 名义字号 × 累积缩放，线宽同理，可精确计算——这绕开 Illustrator 工作流的盲区：linked PDF 被缩放后，AI 字号面板显示的仍是源文件名义值。已以 `figspec lint` CLI 发布（pikepdf 自研内容流解释器、Form XObject 递归、TrimBox 感知、旋转文字奇异值处理）；spec 模式下按 panel 坐标把元素归属到对应 panel（待建）。

检查项按 panel 类型分工：vector 内容查有效字号、有效线宽、字体嵌入；raster 内容（external panel 及任何位图）查放置后有效 DPI（如 2000 px 宽的渲染图放进 60 mm panel 约 850 dpi 安全，被拉到 120 mm 只剩约 420 dpi，逼近 `min_effective_dpi` 即报）；叠加在渲染图上的 scale bar、标注在成品 PDF 里是 text object，同样被字号检查覆盖。另查总尺寸与 spec 一致性、panel 标签风格。

双输出：标注渲染图（低于阈值处红框 + "3.2 pt ✗"，给人一眼定位）与 report.json（每条违规含 panel 归属、元素类型、名义值、累积缩放、有效值、阈值、修复建议，给 agent 驱动自动迭代）。

Watch folder 集成：用户从 Illustrator 导出 final.pdf 到被监视目录，server 自动 lint，报告同时出现在 GUI 和 agent 可调用状态里。

## 5. 典型工作流

**新 figure（完整闭环）**：Designer 拖出版式 → spec 入 server → agent 按契约为各 generated panel 写参数化源 → server 渲染 → 用户将 external 资产与各 panel 产物在 Illustrator 里 1:1 拼版 → 导出到 watch folder → 自动 lint → 违规项由 agent 读报告改源、server 重渲染，人只重拼受影响的 panel。

**几何微调（零对话路径）**：拖 Designer 分隔线 / 改行高 → server 以新 geometry 重执行受影响 panel → 预览即时更新。全程无 agent 参与、无 token 消耗；若 aspect 变化引发布局劣化（图例压线等），包围盒检测把它变成结构化信号，由用户决定是否召回 agent 修一轮。

**语义修改（agent 路径）**："把 panel c 图例移到右上、文案改成 pristine/irradiated" → agent 拉 spec + panel c 的源 → 改代码写回（put 一响应三事）→ server 重渲染。上下文 = spec + 一个 panel 的源。

**存量稿件抢救（最低摩擦入口）**：不改任何习惯，`figspec lint final.pdf --width 183 --min-font 5`（无 spec 独立模式，已可用），拿标注图逐个修。获客路径——lint 的价值第一次使用即兑现。

## 6. MVP 与路线图（按已发布现状重排）

Lint 核心与 Designer 已发布，"核心库 + MCP"的正确切法是：

**M0（天级）**：`figspec-mcp`——FastMCP 瘦层包装已发布能力：lint、spec 读写、布局树操作（现居 `figspec_designer/model/` 的纯函数上移为 `figspec/layout/`，agent 与 server 共用）。不含渲染引擎，state = 项目目录文件，无守护进程也成立——4.1 的"地基不可妥协"约束自共享可变状态出现（渲染引擎、GUI 接入，即 M2）起生效，M0 的无状态文件操作不在其射程。"AI 原生"立刻为真。

**M1**：渲染引擎第一根垂直切片——参数化契约 skill + `validate_source` + **不分层**的 geometry 注入渲染 + 限尺寸 preview；external panel 的便宜半（type/asset_px 进 spec、有效 DPI 按 panel 归属——lint 侧已实现大半）。

**M2**：守护进程 + revision 并发 + watch folder + `get_figure_preview` + 布局劣化检测；Designer 接入 server。

**v2**：层级 content-hash 增量缓存；overlay_source；反向导入（解析既有 AI/PDF 的 placed object 变换矩阵反推版式，与 lint 共用解析代码）；检查项扩展；期刊预设库社区化；FigureFirst SVG → figspec 转换器。

## 7. 技术选型

核心与 server：Python；MCP 层用 FastMCP（stdio 瘦代理 + 每项目守护进程，见 4.1）；渲染为 matplotlib headless 重执行，确定性归一化（固定 `svg.hashsalt`、元数据去时间戳）为 content-hash 前提；缓存为文件系统 content-addressed（`.figspec/cache/`）。PDF 解析：**pikepdf + 自研内容流解释器（已发布并验证）**，标注图用 pypdfium2 渲染 + Pillow 叠加——宽松协议全链路。GUI：PySide6（已发布，含签名分发管线）。三组件共享 `figspec` schema 包（`figspec/spec.py`，含坐标约定规范）。

## 8. 风险与开放问题

**文字被转曲的 PDF**。Illustrator 导出若 outline 文字，lint 拿不到 text object，只能退化为"检测疑似文本的细小路径群并警告"。缓解：skill 与文档明确建议导出保留文字（已发布的 TEXT-PRESENT 检查覆盖告警半）。

**并发写的实现精度**。revision + 租约 + 变更通知的模型已定（4.1/4.5），但拖拽手势与 agent patch 的合并粒度（不相交 patch 可自动合并到什么程度）需要实现期校准，宁可先粗（整 spec 级锁）后细。

**契约执法的剩余一成**。静态校验拦不住的隐式依赖靠双几何性质测试兜底，但性质测试有成本（双渲染），触发时机（每次 put 还是抽查）待定。

**panel 归属鲁棒性**。成品 PDF 元素坐标与 spec 可能有出入（用户微调过），归属算法需容差与"无法归属"兜底。

**Server 常驻的接受度**。本地守护进程 + watch folder 比一次性 CLI 重。缓解：CLI 独立模式保留（已发布）、M0 的 MCP 无守护进程也可用、守护进程按需拉起。

**Designer 表达力 vs. spec 简单性**。分割树 + 绝对矩形导出已发布并验证（span 由树天然覆盖）；自由矩形收集真实版式样本再定。

**与 FigureFirst 的关系**。理念同源，文档致谢并提供迁移转换器，吸纳存量用户而非对立。

---

## 附：变更记录

**v0.1 → v0.2**：其一，架构从"三个松散组件"改为 server-centric：一个本地 server 持有全部状态，GUI/MCP/CLI 三客户端，人机双原生从第一天成立，MVP 相应改为核心库 + MCP。其二，新增设计原则"智能与执行分离"与 panel 源参数化契约：agent 产出参数化函数而非图，几何调整走零对话的本地重执行。其三，新增分层增量渲染模型（层级 content hash 缓存、依赖传播、显式放置要求）。其四，panel 增加 `type` 字段区分 generated/external，raster 内容纳入有效 DPI 校验，人工放置成为架构一等公民。其五，新增"per-panel 分解与上下文经济"论证：spec 是 agent 上下文的隔离边界，视觉信息按需拉取。

**v0.2 → v0.3**（吸收架构/渲染可行性/agent 经济学三路评审与 matplotlib spike 实证）：其一，声明持久化模型：项目目录是持久真相，server 降格为物化视图 + 构建守护进程，新增第一设计原则。其二，定实例模型：每项目单守护进程 + MCP stdio 瘦代理 + lock 文件，并发写引入 spec revision/租约/变更通知。其三，渲染模型按 spike 结果修正：分层从四层改五层（z 序实证）、写明渲染纪律（禁 tight/constrained、extent 计算 pass、确定性归一化、约 5× 成本）；层级增量缓存从 v1 降为 v2，v1 用不分层整 panel 重渲染。其四，契约执法三层化（结构性预防/静态校验/双几何性质测试），修正 `legend()` 默认即 'best' 的规则口径。其五，MCP 接口修订：update_spec 带 base_revision、put 一响应三事、新增 validate_source/get_figure_preview/revert、preview 默认限尺寸、源码读写收敛为 panel 级。其六，MVP 按已发布现状重排为 M0（MCP 包现有能力）/M1（平渲染垂直切片）/M2（守护进程与并发）/v2。其七，上下文经济改为比值口径；GUI 定为 PySide6（已发布）；spec 删除 row_span/col_span、增加版本兼容铁律与 designer sidecar；技术选型更新为已验证的 pikepdf/pypdfium2 栈。删除"零 token resize"的绝对化表述，改为"执行零对话，布局劣化可检测、可选择性召回 agent"。其八，随实现落地的文档更新：§2 新增"实现现状"小节；§4.2 constraints 示例值更新为已发布的 Nature 预设（5/7/0.25）；v0.2 的"Type 3 字体与旋转文字"风险因 linter 已实现（fonttype 3/42 平行测试、奇异值处理）而移除；§5 存量稿件 CLI 语法更新为已发布形式。

*本文档基于 2026-07 的原型讨论、公开资料调研与仓库内已发布组件的实证；相关项目现状以当时可查证信息为准。*
