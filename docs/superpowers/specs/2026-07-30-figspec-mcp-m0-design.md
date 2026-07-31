# figspec-mcp M0 设计（已批准）

**日期**：2026-07-30
**状态**：Approved（v0.3 设计文档 §6 M0 定义，经三镜头评审确认；用户回复"都做"）
**定位**：FastMCP 瘦层包装**已发布能力**（lint、spec 读写、布局操作），无守护进程、无渲染引擎——state = 项目目录文件，每次调用无状态。v0.3 §6："AI 原生立刻为真"。

## 1. 前置重构：纯逻辑上移进 figspec 包

`figspec_designer/model/{tree,ops,flatten,history}.py`、`document.py`、`presets.py` 全部零 Qt 依赖，是 v0.3 点名的"文档看不见但代码库看得见的接缝"。移动：

- `figspec/layout/{tree,ops,flatten,history}.py`（原 model/ 四件）
- `figspec/document.py`（DesignerDocument + MissingDesignerData）
- `figspec/presets.py`（PRESETS/PRESET_CONSTRAINTS/DEFAULT_*）

`figspec_designer/model/*.py`、`document.py`、`presets.py` 变为**单行 re-export shim**（`from figspec.layout.tree import *` 式），designer 代码与 74 个测试零改动。figspec 包由此获得完整的"spec + 布局操作 + 文档层"，MCP 与未来 server 共用。

## 2. MCP 模块（`figspec/mcp_server.py`）

- 依赖：`[project.optional-dependencies] mcp = ["fastmcp>=2"]`；console script `figspec-mcp = "figspec.mcp_server:main"`；未装 extra 时 import 报清晰错误（提示 `pip install "figspec[mcp]"`）。
- 结构：每个 tool = 一个可独立测试的纯实现函数（`_impl` 层，不碰 fastmcp）+ FastMCP 装饰注册（`build_server()` 返回 FastMCP 实例，`main()` 跑 stdio）。测试只打 `_impl` 层 + 一个 `build_server()` 冒烟。

### Tools（M0 全集）

| tool | 签名与行为 |
|---|---|
| `lint_pdf` | `(pdf_path, width_mm=None, min_font_pt=5.0, min_linewidth_pt=0.25, strict=False)` → figlint 的 report dict（extract→run_checks→render_json 复用；与 CLI 同构 JSON）。文件不存在/损坏 → 结构化错误 dict（`{"error": ...}`），不抛异常 |
| `read_spec` | `(spec_path)` → 解析并校验后的 spec dict + 派生摘要（panel 数、labels、是否含 designer sidecar）。SpecError → 错误 dict |
| `write_spec` | `(spec_path, spec: dict)` → 校验（parse_spec）通过才写盘（indent=2 + 换行）；原 dict 原样序列化（未知顶层段天然保留——兼容铁律） |
| `split_panel` | `(spec_path, label, direction)` direction ∈ right/down → 载入（需 designer sidecar，缺则错误 dict 说明 V1 不反推）→ figspec.layout.ops.split_panel → 重扁平化写回 → 返回新 panels 摘要 |
| `close_panel` | `(spec_path, label)` → 同上路径；最后一个 panel → 错误 dict |
| `set_panel_hint` | `(spec_path, label, hint)` → 同上路径 |
| `list_presets` | `()` → PRESETS + PRESET_CONSTRAINTS（含来源文档指引） |
| `new_spec` | `(spec_path, preset="nature_double", height_mm=100.0)` → DesignerDocument.default() 变体按 preset/height 生成并写盘 |

标签寻址：spec 的 panels[].label ↔ sidecar 树 panel id 的映射由 document 层现有 labels() 提供；label 不存在 → 错误 dict 列出现有 labels。

### 错误约定

所有 tool 永不抛异常给 MCP 层：成功 → 结果 dict；失败 → `{"error": "<可执行的说明>", ...}`。（agent 经济学评审：错误文案要可执行。）

## 3. 测试与验收

- 前置重构：78 + 74 全部原样通过（shim 生效的直接证据）。
- `tests/test_mcp.py`（figspec 套件）：_impl 层全覆盖——lint 好/坏样本（复用 selftest samples）、read/write 往返 + 未知顶层段保留、split/close/hint 对含 sidecar 的 spec 文件生效且 labels 重排正确、无 sidecar 错误、坏输入错误 dict、new_spec 各 preset、build_server 冒烟（fastmcp 未装则该单测 skip）。
- CLI：`figspec-mcp` 可启动（`--help` 或立即 EOF 退出即可）。
- README（双语）：新增 MCP 小节（安装 extra、Claude Code/Codex 一行接入示例、tool 清单）。

## 4. 明确不做（M0 边界）

渲染、preview、validate_source、revision/并发、守护进程、watch folder、figure 级合成——全部 M1/M2。set_ratios 类 path 寻址操作不进 M0（对 agent 不友好，等 M1 一起设计）。
