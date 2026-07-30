# FigSpec Designer V1 设计（已批准）

**日期**：2026-07-30
**状态**：Approved（用户批准八节设计并指示直接执行）
**上游文档**：`figspec-设计文档.md` §4.1（Designer 构想）；`2026-07-30-figspec-lint-mvp-design.md`（figlint MVP，已实现）
**参考调研**：SebDeng/Nion-EM-nhdf-Utility-GUI（下称 nhdf）分屏架构与 macOS 打包管线

## 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 技术栈 | PySide6 + PyInstaller | 沿用用户 nhdf 的技术栈与打包管线；与 figspec（Python）同生态，后续可内嵌 figlint |
| 分发 | Developer ID 签名 + notarytool 公证 + DMG，GitHub Release | 科研工具主流方式，无商店审核/沙箱；用户已有 Apple 开发者账号 |
| 仓库 | figspec monorepo，新增 `designer/` 目录 | 与 CLI 共享 spec schema 代码；兑现原设计文档"三组件共享 figspec schema 包" |
| 布局模型 | 方案 A：纯数据布局树（零 Qt 依赖）+ Qt 视图层，导出扁平化为绝对 mm 矩形 | 规避 nhdf 以 widget 树为数据源的架构债；undo/测试天然可行 |
| 坐标系 | **正式定死：原点左上，y 向下，单位 mm**（写入 spec 与导出文件语义） | 补上 MVP 设计文档悬置的约定；Linter 未来 spec 模式内部转换 PDF 坐标 |
| 分支策略 | `designer-v1` 基于 `figlint-mvp`（stacked PR），PR #1 合并后 retarget | Designer 依赖 figspec 包（units 等），main 尚无该代码 |

## nhdf 调研结论（约束实现方式）

**继承**：布局树 JSON schema `{type, orientation, sizes/ratios, children}` 与递归重建思路（nhdf workspace.py 中约 150 行无业务耦合部分）；`panel_factory` 注入模式；`build_macos.sh` + PyInstaller spec + create-dmg + gh release 整套打包脚本骨架（uv、Python 3.11、arm64、版本单一来源 `version.py`）。

**必须新写**（nhdf 没有）：自定义分隔条交互（实时 mm 反馈、吸附）、undo/redo、基于数据树的塌缩逻辑。

**引以为戒**：不以 Qt widget 树为数据源；不复制其内联 QSS/主题散落写法；分隔条命名采用"排列方向"语义（`row` = 子项横排，`column` = 子项竖排），不沿用 nhdf 反直觉的命名。

## 1. 产品定位与 V1 范围

macOS 桌面应用 **FigSpec Designer**：打开即一张按期刊物理宽度定死的画布，自由分割 panel，拖分隔条实时显示 mm，一键导出 figspec.json。

V1 功能清单：
- 期刊预设：Nature 单栏 89 / 双栏 183，ACS 82.5 / 178，APS 86 / 172，自定义宽度；页高用户可调
- 设置：DPI（默认 600）、gutter_mm（默认 4）、constraints（min_font_pt 默认 5、max_font_pt 默认 8、min_linewidth_pt 默认 0.5，来自预设可改）
- 分割（右分/下分）、关闭 panel（兄弟回收空间、单子树塌缩）、拖分隔条（吸附 0.5 mm，⌥ 临时关闭吸附）、undo/redo（⌘Z/⇧⌘Z）
- panel 自动标号 a,b,c…（阅读顺序：按左上角 y 再 x 排序）；选中 panel 侧栏显示 mm / px@DPI / figsize 英寸三套数值；content_hint 可编辑
- 导出：Save figspec.json + Copy JSON（剪贴板 = 交给 agent 的通道）；打开带 `designer` 段的 figspec.json 往返编辑；无该段的文件给出明确提示（V1 不反推）
- UI 语言：英文

## 2. 架构（monorepo）

```
figspec/                  # 现有包；新增 figspec/spec.py：figspec.json 的构建/解析/
                          #   校验辅助（dataclass + to_json/from_json），Designer 与
                          #   未来 CLI --spec 模式共用
designer/
  figspec_designer/
    __init__.py           # __version__（app 版本，独立于 figspec 包版本）
    model/
      tree.py             # SplitNode/PanelNode 纯数据结构 + 序列化
      ops.py              # split/close/set_ratio/normalize 等纯函数（返回新树）
      flatten.py          # 树 + 页面参数 → [PanelRect(x,y,w,h mm)]；标号排序
      history.py          # undo/redo 快照栈
    ui/
      canvas.py           # 画布：由树渲染 Qt 部件；变更→重建或增量更新
      panel_widget.py     # 单 panel：悬停按钮（右分/下分/关闭）、标号、选中态
      handle.py           # 自定义分隔条：拖动、实时 mm 浮显、吸附
      sidebar.py          # 选中 panel 的三套数值 + content_hint 编辑
      toolbar.py          # 预设选择、页高/DPI/gutter、导出按钮
      main_window.py      # 组装、菜单、快捷键、undo 栈接线
    app.py                # 入口
  tests/                  # model 纯 pytest；ui pytest-qt 冒烟
  packaging/
    figspec-designer.spec # PyInstaller（改造自 nhdf）
    build_macos.sh        # uv + PyInstaller + codesign + notarytool + create-dmg
    assets/               # V1 占位图标（icns）
```

模块边界：`model/` 零 Qt 依赖，`ui/` 不做几何数学（一律调 model/flatten），`figspec/spec.py` 不依赖 designer。Designer 以可编辑安装依赖 figspec 包。

## 3. 布局模型

- 树节点：`SplitNode{orientation: "row"|"column", ratios: [float,...], children: [...]}`（ratios 归一化、与 children 等长）；`PanelNode{id: str, content_hint: str}`。`row` = 子项水平排列（分隔条竖直），`column` = 子项竖直排列。
- **分隔条具有物理宽度 = gutter_mm，所见即所出**：扁平化时每级可用空间 = 父矩形尺寸 −(n−1)×gutter_mm，按 ratios 分配，子矩形间留 gutter。
- 扁平化输出 `PanelRect{panel_id, x_mm, y_mm, w_mm, h_mm}`，原点左上 y 向下；派生 `w_px = round(w_mm / 25.4 * dpi)`、`figsize_in = (w_mm/25.4, h_mm/25.4)`（保留 3 位小数）。
- 标号：panels 按 (round(y_mm,1), x_mm) 排序赋 a,b,c,…（超过 26 个用 aa,ab,…）。
- 所有树操作是纯函数（输入树 → 输出新树），undo 栈存树快照（JSON 大小可忽略）。

## 4. 交互

- panel 悬停浮现三按钮：右分（新 panel 在右）、下分（新 panel 在下）、关闭；等价菜单项 + 快捷键：Split Right ⌘D、Split Down ⇧⌘D、Delete Panel ⌘⌫（避开 macOS 系统保留键如 ⌘H/⌘W）。
- 分割语义：对目标 panel 原地包裹——若父节点同方向则直接插入子项并均分该 panel 的 ratio；否则原地生成新 SplitNode 二分。
- 拖分隔条：QSplitterHandle 级别自定义部件；拖动中在 handle 旁浮显两侧 panel 的实时宽/高 mm（一位小数）；释放时吸附到 0.5 mm 网格（按住 ⌥ 释放则不吸附）；拖动只改 ratios，不重建树。
- 关闭 panel：从父 SplitNode 移除，ratio 按剩余项归一；父节点仅剩单子时塌缩（子提升替换父）——全部在数据树上完成后视图重建。
- 视图更新策略 V1 从简：结构性变更（分割/关闭/undo）整画布重建；拖动 ratios 走轻量路径（只 setSizes）。

## 5. 导出与文件格式

导出 JSON 结构完全按 MVP 设计文档 §4.4 草案：

```json
{
  "figspec_version": "0.1",
  "target": {"journal_preset": "nature_double", "figure_width_mm": 183,
             "figure_height_mm": 105.5, "dpi": 600, "gutter_mm": 4},
  "constraints": {"min_font_pt": 5, "max_font_pt": 8, "min_linewidth_pt": 0.5},
  "panels": [{"label": "a", "x_mm": 0, "y_mm": 0, "w_mm": 89.5, "h_mm": 50,
              "w_px": 2114, "h_px": 1181, "figsize_in": [3.524, 1.969],
              "content_hint": ""}],
  "designer": {"tree": {"...": "布局树原样，供往返编辑；其他工具忽略此段"}}
}
```

- 坐标语义：`x_mm/y_mm` 原点左上、y 向下（本 spec 正式定死，figspec/spec.py 文档字符串中注明）。
- `source` 字段 V1 不产出（agent 侧填写）；`panels` 数组按标号序。
- "Copy JSON" 复制完整文件内容到剪贴板；Save 走标准存盘对话框。
- 打开文件：有 `designer.tree` → 恢复树 + target/constraints；没有 → 弹窗说明"该文件缺少 designer 布局数据，V1 不支持从纯 panel 矩形反推"。
- 构建/解析集中在 `figspec/spec.py`，附 JSON 往返测试。

## 6. 打包与分发

- `packaging/build_macos.sh` 改造自 nhdf：uv 建 Python 3.11 build venv → PyInstaller（arm64，`BUNDLE` 带 icns、`NSHighResolutionCapable`、bundle id `com.github.sebdeng.figspec-designer`）→ **`codesign --deep --options runtime`（Developer ID Application 证书）→ `xcrun notarytool submit --wait` + `xcrun stapler staple`** → create-dmg → `gh release create --draft`。
- 签名身份、Team ID、公证凭据（keychain profile 名）一律走环境变量/keychain，不入库；脚本在缺环境变量时明确报错并支持 `--skip-sign` 出未签名包（本地调试用）。
- 版本单一来源 `figspec_designer/__init__.py`；DMG 命名 `FigSpec-Designer-<ver>-arm64.dmg`。
- V1 不做 universal2 / Windows / App Store。

## 7. 测试

- model 层（纯 pytest，无 Qt）：分割/关闭/塌缩、ratio 归一、gutter 扁平化精确数值断言（含嵌套 L 型布局真值）、标号阅读顺序、序列化↔反序列化↔spec 导出三方往返、undo 栈。
- spec 层：figspec/spec.py 构建/解析往返、px 与 figsize 派生值断言。
- ui 层（pytest-qt，headless 环境用 `QT_QPA_PLATFORM=offscreen`）：树→画布部件数一致、点击分割按钮后 model 变更、拖 handle 改 ratios、undo 恢复。
- 打包验收：本地完整跑一次 build_macos.sh（含签名公证）产出可开 DMG。

## 8. 明确不做（YAGNI）

内嵌 figlint、PDF 底图预览、自由浮动矩形、panel 拖拽换位、多 figure 文档、中文 UI、Windows/Intel、自动更新（Sparkle）、从纯 panels 反推布局树。
