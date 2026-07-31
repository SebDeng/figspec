# Designer 批次 B：期刊感知 + 工具链闭环（已批准）

**日期**：2026-07-30
**状态**：Approved（顺序 A→C→B 用户确认）
**范围**：GUI 集成 lint、期刊高度上限警告、标号风格随刊、preset 溯源提示。全部数据来自已核验的 `docs/journal-figure-specs.md`。

## B1 GUI 集成 lint

- File > Lint PDF…（⌘L）：文件对话框选成品 PDF → 后台 QThread 跑 `extract + run_checks`（阈值取当前文档 constraints：min_font_pt / min_linewidth_pt；width 取当前 target.figure_width_mm）→ 完成后打开结果 dock（QDockWidget，右侧）：
  - findings 列表：级别图标（FAIL 红 / WARN 琥珀 / PASS 绿灰）+ check_id + message；选中展开 evidence 行
  - 标注图页：`annotate()` 产物（临时目录 PNG）在可滚动视图中显示；无可标注项则显示"无违规位置"占位
  - 顶部摘要行：verdict + counts，配"重新 lint 同一文件"按钮
- 运行中：菜单项禁用 + 状态栏 busy 提示；异常（LintInputError 等）→ dock 内错误条，不弹崩。
- 实现拆分：`ui/lint_dock.py`（视图）+ `ui/lint_runner.py`（QThread 包装，信号 finished(report_dict, annotated_paths)/failed(msg)）；核心逻辑零新增——全部复用 figspec.lint。

## B2 期刊高度上限警告

- `figspec/presets.py` 新增 `MAX_HEIGHT_MM: dict[str, float | None]`（来源与取值决策记入 journal-figure-specs.md 的"FigSpec 取值决策"节）：
  - nature_single/nature_double: 170.0（Nature 图区上限，留图注位）
  - nature_research_*: 185.0（NRJ 图注 <300 词档的双栏最大值，取宽松档并在 tooltip 说明）
  - science_*: 199.0（SciAdv 推荐上限；旗舰刊无数字，沿用并标注）
  - acs_*: 232.8（660pt 含图注）
  - aps_*: None（现行指南未定 → 不警告）
- TopBar：height 超上限 → height_spin 变琥珀样式（theme 加 `QDoubleSpinBox[overLimit="true"]` 规则 + repolish）+ tooltip"超过 <preset> 最大高度 <N> mm（来源见 journal-figure-specs.md）"。custom preset 不警告。仅提示不阻止。

## B3 标号风格随刊

- `figspec/presets.py` 新增 `PANEL_LABEL_STYLE: dict[str, str]`：nature_* / nature_research_* / acs_* → `"lowercase"`（a）；science_* → `"uppercase"`（A）；aps_* → `"paren_lower"`（(a)）。
- 展示层格式化：`figspec/layout/flatten.py` 加纯函数 `format_label(label: str, style: str) -> str`（lowercase 原样；uppercase 大写；paren_lower 加括号）。**内部与 spec 的 label 恒为小写 a/b/c**（标识符语义不变，展示才变）——canvas panel 字母与 B4 的导出线框按 style 显示。
- 选 preset 时 `constraints.panel_label_size...`——不动 Constraints dataclass；panel_label_style 已在 v0.3 spec constraints 草案中，本批把 Designer 侧 target 联动做实：TopBar 选 preset → doc.constraints.panel_label_style 同步（Constraints 加可选字段 `panel_label_style: str = "lowercase"`，spec 序列化随 asdict 自动携带，旧文件缺键走默认——与 min_effective_dpi 同模式）。
- 批次 C 的线框导出与批次 A 的画布标号均改用 format_label（**B 依赖 A、C 已合并**）。

## B4 Preset 溯源提示

- TopBar preset 下拉每项 setItemData(Qt.ToolTipRole)：`"<宽> mm · <一句来源>"`（数据以字典硬编码于 presets.py `PRESET_SOURCES`，文案取自 journal-figure-specs.md 的来源行）。

## 验收

presets 新字典与 format_label 纯 pytest；lint_runner 用样本 PDF 走线程完成/失败两路（pytest-qt qtbot.waitSignal）；dock 填充断言；height 超限属性翻转断言。现有测试全绿。目视验收：lint 一张 demo bad.pdf 看 dock + 标注图。
