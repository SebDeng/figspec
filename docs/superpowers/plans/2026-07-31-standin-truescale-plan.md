# Stand-ins & True-Scale (批次 D–G) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each batch is one PR, branched per repo convention.

**Goal:** Implement the four pillars of `docs/superpowers/specs/2026-07-31-standin-truescale-design.md` — scale truth for hand-authored assets (nominal → effective, authoring card), a fit/actual/manual zoom model with a calibrated 1:1 mode, an always-honest specimen strip, content stand-ins for the five archetypes, and pre-assembly prediction for PDF assets.

**Architecture:** Pure math and vocabulary land in `figspec/` Qt-free (`scaling.py`, `standins.py`), mirroring the templates/snippet precedent, so MCP/CLI can reuse them later. The Designer consumes them: sidebar gains the source-DPI/calculator/card block, Canvas gains a zoom model behind one `_resolve_scale()` choke point, a new `truescale.py` paint-helper module enforces the honesty disciplines for both the specimen strip and the stand-in painter, and PDF-asset prediction reuses the shipped `figspec.pdf.interpreter` with a virtual scale — zero new lint logic, zero new dependencies (pypdfium2 is already a core figspec dep).

**Tech Stack:** Python 3.13, PySide6, pytest + pytest-qt (`PYTHONPATH=designer QT_QPA_PLATFORM=offscreen`), existing figspec stack (pikepdf/pypdfium2/PIL).

## 决策记录（关闭 spec 的开放问题）

1. 替身排版取值：**混合制** — 家具（轴框/刻度/刻度字/图例框）按约束下限（min_font_pt / min_linewidth_pt），数据笔画按 `min(3 × min_linewidth_pt, 1.0)` pt。
2. archetype 首发五个：`line` / `scatter` / `bar` / `heatmap` / `micrograph`（+ `none`）。
3. 1:1 校准：默认信 OS（`geometry() ÷ physicalSize()`），校准仅由 View > Calibrate Display… 手动触发。
4. loupe：v1 一律 tooltip 文字，不做放大镜。
5. `stand_in` 存 designer sidecar，不进 spec 顶层。
6. `asset_dpi` 存 designer sidecar；换算纯函数进 `figspec/scaling.py`；MCP `authoring_card` 工具**不在本计划**（follow-up，纯函数已就位后是薄包装）。
7. vector 资产**仅 PDF**（pypdfium2 已在依赖树，零新增）；SVG 不做（需 QtSvg 且 lint 不支持，低价值，follow-up）。

## Global Constraints

- `figspec/` 保持 Qt-free；`scaling.py`/`standins.py` 是纯函数 + 纯数据。
- 兼容铁律：旧 figspec.json 与旧 sidecar（无 `asset_dpi`/`stand_in` 键）解析不变；sidecar 序列化只在值非 None 时写键；spec 导出内容与批次 C 末态完全一致（本计划不改 spec 格式）。
- **诚实红线（可测不变量）**：
  - 文字走 painter.scale 路径 — 同一 pt 值在 ppm 与 2×ppm 下的墨迹高度之比 = 2.0 ± 2%（线性），且相邻非整数像素字号可区分（无整像素吸附）。
  - 0.25 pt 线在 ppm < 4 时以半透明渲染（采样行最大 alpha < 255），QPen widthF 永不下取整为 1px 实线。
  - 替身伪数据决定性：同 (archetype, seed, geometry) 输出逐位一致。
- UI copy is English（批次 B 已裁定；spec 中文文案译英）。
- 换算金标（全计划复用同一组数）：源 1472 × 879 px @ 96 dpi（= 389.47 × 232.57 mm）入 60 × 36 mm panel：k = min(60/389.47, 36/232.57) = **0.15406**；名义 8 pt → 有效 **1.232 pt**；目标有效 5 pt → 名义 **32.46 pt**；0.25 pt 线 → 名义 **1.62 pt**；300 有效 dpi → **≥ 709 × 426 px**。
- 测试命令与基线：`.venv/bin/pytest tests/ -q`（起点 143 pass + 1 skip；`test_split_panel_readonly_file_errors` 在 root 容器环境因权限被无视而假失败，非 root 本机为绿——不得让它退步为真失败）；`PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q`（起点 161）；smoke `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python -m figspec_designer --smoke` exit 0。每任务结束三条全绿。

## Batch DAG 与排序理由

```
D 缩放真相(raster 半)  ──→  E 缩放模型+实寸+样张条  ──→  F 内容替身
        └────────────────────────────────────────────→  G PDF 资产+预报
```

- **D 先行**：不碰画布结构、纯函数占比最高、单批兑现"手作图最难"的价值大头（声明/显示/补偿）。
- **E 其次**：画布改造是全计划最大结构风险，独立成批；样张条依赖 D 的换算（"源 8 pt → 有效"行）。
- **F 依赖 E**：替身绘制复用 E 的 `truescale.py` 诚实绘制助手。
- **G 只依赖 D**：可与 E/F 并行开发，但按 PR 顺序排最后（含预报冒烟需构造 PDF fixture）。

---

## Batch D：缩放真相（raster 半）— PR "designer-batch-d"

**File Structure:**
- `figspec/scaling.py` — k/换算/卡片纯函数（create）
- `figspec/layout/tree.py` — `PanelNode.asset_dpi: float | None`（modify）
- `designer/figspec_designer/ui/sidebar.py` — 源 DPI 行、×k、双向小算盘、Copy Authoring Card（modify）
- `designer/figspec_designer/ui/main_window.py` — 拖入时读 DPI 元数据、asset_dpi 编辑落树、卡片入剪贴板（modify）
- Tests: `tests/test_scaling.py`（create）, `designer/tests/test_scale_truth.py`（create）

### Task D1: `figspec/scaling.py` 纯函数层

**Interfaces（后续任务依赖这些确切名字）：**
```python
asset_size_mm(asset_px: tuple[int, int], dpi: float) -> tuple[float, float]
placement_scale(panel_mm: tuple[float, float], src_mm: tuple[float, float]) -> float   # letterbox: min(两轴比)
effective_pt(nominal_pt: float, k: float) -> float
required_nominal_pt(target_effective_pt: float, k: float) -> float
required_px(panel_mm: tuple[float, float], min_effective_dpi: int) -> tuple[int, int]  # ceil
authoring_card(panel_mm, constraints, asset_px=None, asset_dpi=None) -> str            # 三段式英文文本
```

- [ ] **Step 1: 失败测试** `tests/test_scaling.py`：金标全套（`pytest.approx`，见 Global Constraints）；`placement_scale` 取小轴；`required_px` 向上取整（709, 426）；`authoring_card` 无资产时只输出金路径段，有资产时含 `32.5`/`45.4`（`required_nominal_pt` 对 5/7 pt，一位小数）与 `1.6`（线）与 `709 × 426 px`；卡片可逆性——卡片里的名义值乘回 k 落在 [min_font_pt, max_font_pt] ± 0.05。
- [ ] **Step 2: 跑测确认失败**（ImportError）。
- [ ] **Step 3: 实现**。复用 `figspec.units.pt_to_mm/mm_to_pt`；`authoring_card` 由 `Constraints` 派生所有数值，三段标题 `Option 1 — resize your canvas (golden path):` / `Option 2 — keep your canvas:` / `Option 3 — raster export target:`；k ≤ 0 或缺 dpi 时 Option 2 省略。
- [ ] **Step 4: 三条测试命令全绿。**
- [ ] **Step 5: Commit** `feat: figspec.scaling — placement scale, nominal/effective conversion, authoring card`

### Task D2: `asset_dpi` 进树 + 拖入自动读取

- [ ] **Step 1: 失败测试**：`tests/`（layout 往返：`PanelNode(asset_dpi=220.0)` → to_dict/from_dict 保持；无值不写键——断言 `"asset_dpi" not in d`）；`designer/tests/test_scale_truth.py`：构造带 pHYs 的 PNG（`QImage.setDotsPerMeterX/Y(220/25.4*1000)` 后 save）拖入（复用批次 C 的 QMimeData 模拟范式，见 `test_batch_c_ui.py`）→ 断言节点 `asset_dpi == pytest.approx(220, abs=1)`；无元数据 PNG（Qt 默认 d/m）→ `asset_dpi is None`（显示层按 96 假定，见 D3）。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：`figspec/layout/tree.py` PanelNode 加字段 + 序列化（模仿 asset/asset_px 的可选键写法）；main_window 现有 asset-drop handler（沿 `Canvas.asset_dropped` 信号找）在读 `asset_px` 处并读 `QImage.dotsPerMeterX()`——与 Qt 默认值（3780 ± 2 d/m）相同或为 0 时记 None（"默认 96"与"真 96"不可分辨，一律当假定值），否则换算 dpi 存入。undo/redo 经现有 history 机制自动覆盖（字段在树上）。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: asset source-DPI metadata — auto-read on drop, sidecar round-trip`

### Task D3: 侧栏 — 源 DPI 行、×k、双向小算盘

**Interfaces:** `Sidebar.asset_dpi_edited = Signal(str, object)`（panel_id, float|None）；`show_panel(...)` 增参 `asset_dpi: float | None = None`（现有调用点同步）；小算盘为两个互驱 QDoubleSpinBox（`calc_nominal` / `calc_effective`），任一编辑按当前 k 更新另一个（`blockSignals` 防环）。

- [ ] **Step 1: 失败测试**：选中带资产 panel（1472×879 @96 假定值）→ 断言 k 标签文本含 `×0.154`；`calc_nominal` 设 8.0 → `calc_effective` 显示 1.23；`calc_effective` 设 5.0 → `calc_nominal` 显示 32.5；编辑源 DPI 行为 220 → 信号发出、k 标签更新（0.353）；无资产 panel → 整块隐藏。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：源 DPI 行显示 `96 (assumed)` 或 `220 (from file)`（QLineEdit + 后缀 label，编辑落 `asset_dpi_edited`，main_window 写树并 refresh）；k 与算盘全部调 `figspec.scaling`，无本地公式。有效 DPI 灯与新块并排（同一 k 的两张脸，spec §1.4）。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: sidebar scale-truth block — source DPI, placement scale, two-way pt calculator`

### Task D4: Copy Authoring Card

- [ ] **Step 1: 失败测试**：选中带资产 panel → 触发卡片动作 → `QApplication.clipboard().text()` 含三段标题与金标数值；无资产 panel → 卡片仍可复制（仅金路径段）。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：侧栏按钮 + File 菜单项 "Copy Authoring Card"，调 `scaling.authoring_card`（panel rect、当前 constraints、节点 asset_px/asset_dpi），statusBar 提示 3s。
- [ ] **Step 4: 全绿；smoke。**
- [ ] **Step 5: Commit** `feat: per-panel authoring card — the hand-tool counterpart of the snippet`

---

## Batch E：缩放模型 + 实寸 + 样张条 — PR "designer-batch-e"

**File Structure:**
- `designer/figspec_designer/ui/truescale.py` — 诚实绘制助手 + 屏幕 px/mm 解析（create）
- `designer/figspec_designer/ui/canvas.py` — `_resolve_scale()` 三态（modify）
- `designer/figspec_designer/ui/main_window.py` — QScrollArea 包裹画布、View 菜单、校准对话框接线（modify）
- `designer/figspec_designer/ui/specimen_strip.py` — 样张条（create）
- `designer/figspec_designer/ui/calibrate_dialog.py` — 校准（create）
- `designer/figspec_designer/ui/theme.py` — 样张条/徽章 QSS（modify）
- Tests: `designer/tests/test_truescale_ui.py`（create）

### Task E1: `truescale.py` 诚实绘制助手

**Interfaces:**
```python
pt_to_px(pt: float, ppm: float) -> float                      # pt × 25.4/72 × ppm，float 不取整
draw_text_pt(painter, x_mm, y_mm, text, size_pt, ppm, *, bold=False)   # painter.scale 技巧
line_pen_pt(width_pt: float, ppm: float, color) -> QPen       # widthF 精确；<0.75px 时 alpha 随宽度衰减
screen_px_per_mm(screen, correction: float = 1.0) -> float    # geometry().width()/physicalSize().width() × correction
load_correction(screen) -> float / save_correction(screen, value)      # QSettings，键=screen.serialNumber() or name()
```

- [ ] **Step 1: 失败测试**：**线性红线** — 同字串 5 pt 在 ppm=8 与 ppm=16 各渲一张 QImage，墨迹 bbox 高之比 = 2.0 ± 2%；**无吸附红线** — ppm=4.5 与 ppm=4.9（5 pt 字高 7.94 px vs 8.64 px，跨整数像素）墨迹高不同；**细线红线** — `line_pen_pt(0.25, 4.0)` 的 widthF ≈ 0.353 且画后采样行 max alpha < 255；`screen_px_per_mm`（注入 fake screen：geometry 1512 px / physicalSize 311 mm → 4.862 ± 0.001，correction 1.03 相乘生效）；correction 往返 QSettings。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：`draw_text_pt` 设大号字（pixel size 64）后 `painter.save(); painter.translate(); painter.scale(target_px/64)` 绘制再 restore；alpha 衰减 = `min(1, width_px/0.75)` 乘入颜色。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: true-scale paint helpers — fractional-pt text, honest hairlines, screen px/mm`

### Task E2: Canvas 缩放模型 + 滚动

**Interfaces:** `Canvas.set_zoom(mode: str, manual_ppm: float | None = None)`（"fit"|"actual"|"manual"）、`Canvas.zoom_mode`、`scale_changed = Signal(float)`（每次 `_rebuild` 后发 `px_per_mm`）；main_window 把画布放入 QScrollArea（fit：`widgetResizable=True` 维持现状观感；actual/manual：canvas `setFixedSize(page+2×margin)`、居中）。

- [ ] **Step 1: 失败测试**：默认 fit 行为与现基线一致（现有 canvas 测试不动即是回归网）；`set_zoom("actual")` 后 `canvas.px_per_mm == pytest.approx(screen_px_per_mm(fake), rel=1e-6)`（offscreen 注入 fake screen 经 `truescale.screen_px_per_mm` 的可注入参数）；`set_zoom("manual", 12.0)` 后 px_per_mm == 12；三态切换后 splitter/拖拽提交路径仍工作（复用现有 ratios_committed 测试模式跑一次 commit）；`scale_changed` 每次 rebuild 触发。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：`_fit_scale()` 改名为 `_resolve_scale()` 内部三分支；View 菜单 Zoom to Fit（Cmd+0）/ Actual Size（Cmd+1）/ Zoom In/Out（Cmd+±，manual 档位 ×1.25 步进，界 [25%, 400%] of actual）。resizeEvent 仅 fit 态触发 rebuild。
- [ ] **Step 4: 全绿 + smoke。**
- [ ] **Step 5: Commit** `feat: canvas zoom model — fit / actual-size / manual with scroll`

### Task E3: 校准对话框

- [ ] **Step 1: 失败测试**：对话框滑杆改动实时改标尺宽度；Accept 后 `save_correction` 被写入（QSettings 隔离用 `QSettings("figspec-test", …)` 注入或 monkeypatch）；canvas actual 模式下 px_per_mm 含 correction。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：对话框画 100 mm 标尺 + 85.60 mm 银行卡参考框，滑杆范围 ±15%，文案 "Adjust until the bar matches a real ruler (100 mm) or a credit card's long edge (85.60 mm)."；View > Calibrate Display…。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: display calibration for actual-size mode`

### Task E4: 样张条

**Interfaces:** `SpecimenStrip(QWidget)`：`set_context(ppm: float, actual_ppm: float, constraints)`、`set_panel_scale(k: float | None, asset_dpi: float | None)`（选中手作 panel 时追加"源→有效"行）、信号 `actual_size_requested`。

- [ ] **Step 1: 失败测试**：set_context 后 paint 不崩且徽章文本含 `% of print size`（fit ppm=2×actual → "200%"）；set_panel_scale(0.154, 96) 后条内出现 "8 pt → 1.2 pt" 行（文本可断言：strip 暴露 `badge_text()`/`rows()` 只读接口供测试，绘制细节不测像素）；点击 1:1 按钮发 `actual_size_requested`；tooltip 含 mm 换算（"5 pt = 1.76 mm"）。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：条内容全部经 `truescale` 助手按当前 ppm 绘制：`Aa 5 pt`、`Aa 7 pt`（constraints min/max）、0.25/0.5/1.0 pt 线样、10 mm 比例尺；main_window 把条挂画布下方，接 `scale_changed` 与选中变化；"源→有效"行的名义样本值固定展示 8 pt（spec 叙事锚点）+ 当前算盘名义值（若侧栏已输入）。
- [ ] **Step 4: 全绿 + smoke。**
- [ ] **Step 5: Commit** `feat: specimen strip — live type/line specimens, zoom badge, effective row`

---

## Batch F：内容替身 — PR "designer-batch-f"

**File Structure:**
- `figspec/standins.py` — 词表、决定性伪数据、hint 推断（create）
- `designer/figspec_designer/ui/standin_painter.py` — 五 archetype 绘制 + QPicture 缓存（create）
- `designer/figspec_designer/ui/panel_widget.py` / `canvas.py` — 替身层接入（modify）
- `designer/figspec_designer/ui/sidebar.py` — Stand-in 选择行（modify）
- `figspec/layout/tree.py` — `PanelNode.stand_in: str | None`（modify）
- `designer/figspec_designer/ui/preview_export.py` — `with_standins` kwarg（modify）
- Tests: `tests/test_standins.py`（create）, `designer/tests/test_standin_ui.py`（create）

### Task F1: `figspec/standins.py`

**Interfaces:**
```python
ARCHETYPES: tuple[str, ...] = ("line", "scatter", "bar", "heatmap", "micrograph")
infer(content_hint: str) -> str | None          # 关键词表；无匹配 None
pseudo_data(archetype: str, seed: str, n_hint: int = 0) -> dict   # 决定性；hashlib 派生,不用 random 全局态
roles(constraints) -> dict                       # 家具/数据笔画取值（决策记录 1 的公式）
```

- [ ] **Step 1: 失败测试**：词表冻结断言；`infer`（"STEM image"→micrograph、"spectra"→line、"" → None、大小写不敏感）；`pseudo_data` 同 seed 逐位相等、异 seed 不等、值域 [0,1]；`roles` 金标（Nature：furniture 5.0 pt/0.25 pt，data stroke 0.75 pt；Science：data stroke 1.0 pt 封顶生效）。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**（`hashlib.sha256(seed)` 流派生伪随机，禁 `random` 模块全局态）。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: figspec.standins — archetype vocabulary, deterministic pseudo-data, hint inference`

### Task F2: `standin_painter.py`

**Interfaces:** `standin_picture(archetype, w_mm, h_mm, ppm, constraints, seed) -> QPicture`（模块级 LRU ≤ 256 项，key 含 round(w_mm,1)/round(h_mm,1)/round(ppm,2)/constraints 元组/seed）；绘制全部经 `truescale` 助手（E1）。

- [ ] **Step 1: 失败测试**：五 archetype 各渲 40×30 mm @ ppm 4 不崩、非空；缓存命中（同参二次调用返回同一对象 / 计数器不增）；**诚实红线**——line 替身在 ppm=8 与 16 下刻度字墨迹高比 2.0 ± 2%（复用 E1 测法，替身整图渲到 QImage 后测字区 bbox）；heatmap 含 colorbar（右缘 3 mm 区带非底色）；micrograph 含比例尺。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：家具/数据取值全来自 `standins.roles`；micrograph 噪声底用 seed 派生的预生成 tile；整体灰调 + 右下角 "stand-in" 微记号（诚实原则 3）。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: archetype stand-in painter with QPicture cache`

### Task F3: 画布与侧栏接入 + sidecar

- [ ] **Step 1: 失败测试**：树往返 `stand_in` 可选键；侧栏 Stand-in 下拉（Auto/Line/Scatter/Bar/Heatmap/Micrograph/None）改动落树 + undo 可回退；panel 有资产时替身不画（缩略图优先）；`stand_in=None` 且 hint="STEM image" 时画 micrograph（推断路径）；显式 "none" 保持现状灰卡。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：canvas `_build_node` 解析 (stand_in | infer(hint))，传 PanelWidget；PanelWidget paintEvent 在背景后、字母前 drawPicture；字母沿用 onImage 样式。seed = 节点 id。
- [ ] **Step 4: 全绿 + smoke。**
- [ ] **Step 5: Commit** `feat: stand-ins on canvas — sidebar selector, hint inference, sidecar round-trip`

### Task F4: 导出与模板预览升级

- [ ] **Step 1: 失败测试**：`render_layout_image(..., with_standins=True)` 输出与 False 不同（字节级）且文件非空；默认 False 时输出与批次 C 基线路径一致（现有测试即回归网）。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：额外 kwarg + File 导出走 True；TemplateDialog 维持线框（模板无 hint）。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: layout preview export with stand-ins`

---

## Batch G：PDF 资产 + 预报 — PR "designer-batch-g"

**File Structure:**
- `designer/figspec_designer/ui/panel_widget.py` — ASSET_EXTS += ".pdf"（modify）
- `designer/figspec_designer/ui/main_window.py` / `canvas.py` — PDF 缩略图（pypdfium2 首页渲染）、内在尺寸落树（modify）
- `figspec/scaling.py` — `predict_pdf(asset_path, k, constraints) -> list[dict]`（modify；调 `figspec.pdf.interpreter.extract`，逐 text/line 元素输出 nominal/effective/verdict，文字转曲时返回带 `text_absent` 标记的空表）
- `designer/figspec_designer/ui/sidebar.py` — vector 徽章 + 预报列表（modify）
- Tests: `tests/test_scaling.py` 扩展, `designer/tests/test_vector_assets.py`（create）

### Task G1: PDF 资产接入

- [ ] **Step 1: 失败测试**：拖入 PDF（fixture 用 `tests/fixtures.make_panel` 产 8 pt 文本 PDF）→ external 态、缩略图非空、节点 `asset_px` 记录渲染像素、k 由 **MediaBox 内在 mm**（pdfium `get_size()` pt → mm）而非 asset_px 计算；侧栏显示 "vector" 徽章、有效 DPI 灯隐藏（对 vector 无意义）、源 DPI 行隐藏。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：缩略图渲染上限沿用 `_THUMB_MAX`；内在尺寸随读随取（不进 sidecar——spec §4）。
- [ ] **Step 4: 全绿。**
- [ ] **Step 5: Commit** `feat: PDF assets — pdfium thumbnails, intrinsic-size placement scale`

### Task G2: 拖入即预报

- [ ] **Step 1: 失败测试**：金标——`make_panel(fontsize=8)` 的 PDF（读出其内在宽 W mm）指派给 60 mm 宽 panel → `predict_pdf` 返回项含 nominal 8.0、effective == 8 × (60/W) ± 0.01、verdict 按 5 pt 红线判红绿；转曲 fixture（tests/fixtures 已有 outlined 样本能力，见 `test_integration.py::test_outlined_panel_warns_text_present`）→ `text_absent` 标记；侧栏列表在拖入后非空并显示英文文案 "8.0 pt → 1.2 pt ✗"。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**：`predict_pdf` 复用 interpreter 的 (nominal × CTM) 输出再乘 k——**零新检查逻辑**；聚合去重（同字号合并、最多列 8 行、超出加 "+N more"）；预报在拖入与 k 变化（panel resize、DPI 编辑不适用于 vector）时刷新，主线程同步跑（单页资产 PDF，延迟可忽略；慢再上 QThread，不预先复杂化）。
- [ ] **Step 4: 全绿 + smoke。**
- [ ] **Step 5: Commit** `feat: pre-assembly lint prediction for PDF assets`

---

## Verification（全计划收尾）

1. 三条测试命令全绿（核心新增 ≈ 25 测试、designer 新增 ≈ 30）。
2. Controller 目视：金标场景走查——1472×879 PNG 拖入 60 mm panel，侧栏 ×0.154 / 算盘 8→1.23 / 卡片三段；Cmd+1 实寸 + 样张条 100% 徽章，MBP 内屏实尺比对 10 mm 比例尺；五 archetype 替身网格截图；8 pt PDF 拖入即预报判红。
3. 更新 `figspec-设计文档.md` §2.5 实现现状小节（一句话：Designer 增替身/实寸/缩放真相/PDF 预报）与本 spec 状态行 → Shipped。
4. Follow-up 清单（不在本计划）：MCP `authoring_card` 工具、SVG 资产、真放大镜 loupe、`stand_in`/`asset_dpi` 升格进 spec 的再评估。
