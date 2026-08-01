# UI 减重:按意图收敛交互面(批次 I)

**日期**：2026-07-31
**状态**：Approved（用户确认方向 + 点名顶栏难看）
**范围**：纯 Designer 交互层重组，功能一个不减——从"永远都在"改为"要时才出现"。核心判断：app 的循环只有三个动词——**切格子、看真相、交出去**——表面应对应动词，不对应功能史。

## 现状盘点（重在哪）

侧栏 260px 柱子里约 21 个元素（6 行只读 + 编辑件 + 3 个 Copy 按钮 + 资产块 8 行）；顶栏 11 个常驻控件（其中约束三框选定期刊后几乎不动）；"交出去"有 7 条并行通道；缩放双入口；拆分四入口；样张条常驻 60px；main_window.py 1027 行 god object。

## 决策

1. **交付收敛**：新增 Hand Off 面板（Cmd+E / 顶栏唯一主按钮 / File 菜单一项）承载全部七种输出：Illustrator 底板、选中 panel 画板、matplotlib snippet、作图卡片、figspec.json、坐标表、预览 PNG。侧栏三个 Copy 按钮删除；File 菜单对应六项收敛为一项（Save/Save As 是持久化不是交付，保留）。
2. **顶栏只留三件事 + 一个主按钮**：Preset、W×H（高度超限琥珀警告不变）、**设置 chip**（"600 dpi · 4 mm · 5–7 pt · ≥0.25 pt"，点开 Document 弹层容纳 DPI/Gutter/三约束框）、右侧 Hand Off 主按钮。Open/Save/Copy JSON 三按钮删除（菜单与快捷键仍在）。**控件保活**：八个数值控件对象与 `values()/set_values()/set_height_over_limit()` 契约不变，只是五个移居弹层——既有测试按属性 setValue 全部照跑。
3. **侧栏三层**：常显 = Label、尺寸、**真相行**（有资产："×0.500 · 8→4.0 pt ✗" 或 "×0.215 · 447 dpi ✓"；无资产：约束回显）、hint、Stand-in、锁比例+Square 一行、Remove Asset（仅资产时）；Details 折叠（Position/Aspect/Pixels/figsize）；**真相弹层**（点真相行）容纳源 DPI、Scale、双向算盘、预报列表——现 `asset_box` 整体改作弹层内容容器，全部属性名保留（isVisibleTo 语义兼容既有测试）。
4. **底部合并成一条状态栏**：样张条默认**折叠为 24px**（Aa 微样 + "% of print size" 徽章 + 展开箭头），点开还原完整样张；右侧新增缩放簇 Fit / 1:1 / − / +（与 View 菜单驱动同一控制器，消灭双入口）。`rows()/badge_text()` API 不变。
5. **拆分入口砍到二**：PanelWidget 的 hover 三按钮删除；右键菜单补上 Split Right / Split Down（此前只有 N 版）；菜单栏与快捷键保留。
6. **代码减重**：七个交付动作从 main_window 迁至 `ui/handoff.py`（窗口保留薄委托方法，公共 API 兼容）；目标 main_window < 900 行。
7. **顶栏观感**（点名整改）：theme 重排——统一 26px 控件高度、small-caps 灰标签、chip 药丸样式、Hand Off 用主色、栏底 1px 分隔线，删掉现在"标签+框"×8 的流水排布。

## 验收基准

两套测试全绿（预计改动 ≤ 8 处既有断言 + 重写 1 个 hover 测试）；smoke 通过;改造前后同场景截图对比:侧栏常显元素 21→≤9,顶栏 11→5,File 菜单 12→7,常驻底部 60→24px。
