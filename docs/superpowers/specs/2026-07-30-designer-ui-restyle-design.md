# Designer UI 视觉改造：方向 C「极简画室」（已批准）

**日期**：2026-07-30
**状态**：Approved（用户经视觉对比 mockup 选定方向 C，逐节确认设计）
**性质**：纯视觉改造，**零行为变更**——现有 59 个 designer 测试原样全绿是硬约束。

## Design tokens（全部集中于新文件 `designer/figspec_designer/ui/theme.py`）

| token | 值 | 用途 |
|---|---|---|
| CHROME | `#FAF9F7` | 窗口/工具栏/侧栏背景（暖白） |
| CANVAS | `#F1EFEB` | 画布井背景；gutter 透出色（所见即所出保持） |
| HAIRLINE | `#EAE7E1` | 发丝分割线、静默边框 |
| DIVIDER | `#D8D5CF` | 强分割线、分隔条 hover、输入框 hover 边 |
| INK | `#1A1A18` | 主文字、选中描边、主按钮背景 |
| INK_SECONDARY | `#6B6862` | 次级文字 |
| INK_MUTED | `#A09D96` | 弱化文字、小标题 |
| PANEL_BG | `#FFFFFF` | panel 卡片 |
| 投影 | QGraphicsDropShadowEffect blur 12, offset (0,1), rgba(26,26,24,0.10) | panel 卡片浮起 |

## 组件规格

- **theme.py**：`QSS`（全局样式表，f-string 由 tokens 拼装）、`apply_theme(app)`、`repolish(widget)`（unpolish/polish）、`smallcaps_font()`（QFont AllUppercase + PercentageSpacing 112 —— QSS 不支持 letter-spacing）、`panel_shadow(widget)`。样式选择器用类名（`PanelWidget`、`Canvas`）与 objectName（`#page`、`#panelActions`、`#dragFeedback`、`#topbar`、`#sidebar`、`#primary`、`#panelLetter`、`#sectionHeader`、`#fieldLabel`、`#fieldValue`）。
- **MainWindow** 构造时调用 `apply_theme(QApplication.instance())`（幂等；测试路径同样被主题覆盖）。
- **Qt 关键机制**：纯 QWidget 子类（Canvas、topbar、sidebar、panelActions 容器）必须 `setAttribute(Qt.WA_StyledBackground, True)` 否则 QSS 背景不生效；选中态改为动态属性 + `repolish` 模式（`PanelWidget[selected="true"]` 选择器），拆除组件内所有散落的 `setStyleSheet`。
- **PanelWidget**：字母标号 QLabel objectName `panelLetter`（20px 淡灰 `#C6C3BC`，由 QSS 控制）；三个悬停按钮装入 objectName `panelActions` 的白色圆角浮层小条（发丝边框，按钮无框、hover 背景 CANVAS），enter/leave 切换容器可见性（替代逐按钮切换）；`set_selected` 只 setProperty + repolish。公开接口（signal `action`、`set_label`、`set_selected`、`label_widget`、按钮 objectName）不变。
- **Canvas**：page 容器 objectName `page`、透明无边框（panel 白卡直接浮在画布上，边界由卡片定义）；每个 PanelWidget 创建后挂 `panel_shadow`；拖动反馈 QLabel objectName `dragFeedback`（黑 chip 白字圆角）；分隔条平时透明，`QSplitter::handle:hover/:pressed` 显 DIVIDER。
- **Sidebar**：objectName `sidebar`；顶部小节标题 QLabel objectName `sectionHeader`（`smallcaps_font`，文字 "PANEL"）；信息行改 QGridLayout：左 `fieldLabel`（MUTED）右 `fieldValue`（INK 加粗右对齐）；hint 输入框改无框底线样式（QSS QLineEdit）。公开属性名 `lbl_label/lbl_mm/lbl_px/lbl_figsize/hint_edit` 与信号不变。
- **TopBar**：objectName `topbar`（底部发丝线）；8px 网格间距（外边距 16/8，控件间 8，组间 16）；输入控件白底圆角 6 发丝边；`btn_copy` objectName `primary`（黑胶囊白字），`btn_save`/`btn_open` 安静胶囊（radius 12）。`values()/set_values()` 接口不变。
- **app/main_window**：central widget objectName `chrome`；StatusBar/MenuBar 由全局 QSS 覆盖（CHROME 背景、次级文字色）。

## 验收

1. `.venv/bin/pytest designer/tests -q` 原有 59 个测试不改动全绿；新增 theme 测试（QSS 已应用且含 token、smallcaps 字体属性、repolish 不抛错）。
2. `--smoke` 正常。
3. 启动 app 由用户目视验收，反馈直接迭代。

## 明确不做

自定义标题栏、图标字体/SVG 图标集（保留 unicode 字形，样式化处理）、深色模式、动效过渡、预设改 tab 交互（保持下拉）。
