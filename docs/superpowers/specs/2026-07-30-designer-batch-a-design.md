# Designer 批次 A：基础操作补全（已批准）

**日期**：2026-07-30
**状态**：Approved（双镜头功能走查 + 用户确认 "ACB" 顺序）
**范围**：高频基础操作 6 组。零 spec 格式变更（除 designer sidecar 内 PanelNode 可选字段）。

## A1 等分与 N 分

- Panel 右键菜单 + Panel 菜单："Split Right into N…"/"Split Down into N…"（N 输入对话框 2–8）与 "Equalize Siblings"。
- model 层新增纯函数：`ops.split_panel_n(root, panel_id, direction, n)`（语义 = 对同一 panel 连续 split 后等分：父方向匹配时插入 n−1 个新 panel 并把目标 ratio 均分为 n 份；否则原地包裹为 n 子 SplitNode 等 ratio）；`ops.equalize_siblings(root, panel_id)`（目标所在父 SplitNode ratios → 全部均等）。KeyError/ValueError 语义与现有 ops 一致；n<2 或 >8 → ValueError。

## A2 侧栏数值编辑 + 位置显示 + 放置表

- 侧栏 w/h 从只读 QLabel 改为 QDoubleSpinBox（mm，1 位小数，回车生效）；新增只读行 x / y / aspect（w:h 约分显示 + 小数）。
- model 层：`ops.set_panel_size(root, panel_id, axis, size_mm, page_w_mm, page_h_mm, gutter_mm)`——沿该轴找最近的可调祖先 SplitNode，反解新 ratios；无可调祖先（该轴尺寸由页面直接决定）→ ValueError("axis not adjustable")，UI 将该 spinbox 置灰。任何导致某 panel < 5mm 的调整 → ValueError（A6 守卫统一实施）。
- "Copy Placement Table"（File 菜单 + 侧栏按钮）：TSV `label\tx_mm\ty_mm\tw_mm\th_mm`（2 位小数，按标号序）进剪贴板。

## A3 长宽比：显示 + 一键方形 + 软锁定

- 侧栏显示当前 aspect；按钮 "Make Square"（把 h 设为 w，经 set_panel_size，不可调时置灰）。
- 软锁定：PanelNode 新增可选字段 `aspect_lock: float | None`（sidecar 序列化，兼容规则容忍）；侧栏 "Lock aspect" 勾选记录当前 w:h。锁定后为**指示器语义**（不做跨轴约束求解）：偏离锁定值 >2% 时 panel 右上角琥珀色小徽标 + 侧栏 aspect 行变琥珀。V1 不阻止拖动。

## A4 防丢稿基本盘

- 脏状态：任何 `_push_tree`/settings 变更置 dirty；保存清除；窗口标题 `<文件名或 Untitled> — FigSpec Designer`（dirty 时加 " •" 前缀于文件名后）。
- closeEvent：dirty 时 Save / Discard / Cancel 三选对话框。
- ⌘S：已有路径 → 静默保存；无路径 → Save As 对话框。新增 Save As（⇧⌘S）。
- File > Open Recent：QSettings 最多 5 条，打开/保存均登记；子菜单含 "Clear Menu"。
- 启动恢复：上次文件存在则自动打开（QSettings 记路径）；失败静默回落新文档。

## A5 交换 panel

- model：`ops.swap_panels(root, id_a, id_b)`（交换两 PanelNode 在树中的位置；含 hint/aspect_lock 等字段随节点走）。id 相同或任一不存在 → KeyError。
- UI：选中 panel 后 Panel 菜单 "Swap With…" 进入交换模式（状态栏提示"点击另一个 panel 完成交换，Esc 取消"），下一次 panel 点击执行 swap；Esc/点击画布空白取消。

## A6 守卫与微调

- 最小尺寸守卫：所有产生新几何的操作（split/split_n/set_panel_size/拖动 commit）拒绝产生 < 5mm 的 panel（拖动吸附时 clamp 到边界而非报错；命令式操作报 ValueError → 状态栏消息）。
- 键盘微调：选中 panel 后 ⌘←/→ 调宽、⌘↑/↓ 调高，步进 0.5mm（加 ⇧ 为 2mm），经 set_panel_size（不可调轴忽略并状态栏提示）。

## 验收

model 新函数纯 pytest 全覆盖（等分数学、set_panel_size 反解与守卫、swap 字段保全、树往返）；UI pytest-qt：spinbox 编辑回写、放置表剪贴板内容、dirty/标题、swap 流程、微调快捷键。现有 178 测试原样全绿。app 启动目视验收。
