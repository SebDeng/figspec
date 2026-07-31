[English](README.md) | [中文](README.zh-CN.md)

# figspec

对成品图表 PDF 进行检查，核实其**有效**（缩放后）字号与线宽。

当 matplotlib 生成的面板被放入 Illustrator 并缩放以适配版面时，名义上 7 pt 的
标签可能悄无声息地变成 3 pt。Illustrator 的字体面板仍然显示 7 pt。figspec 打开
*成品* PDF，将每个文本对象的字号沿完整的 PDF 变换栈（包括 Form XObject —
也就是被放置、缩放的面板）连乘，报告实际印刷出来的效果。

## 安装

```bash
pip install figspec
```

## 使用

```bash
figspec lint final.pdf --width 183mm
figspec lint final.pdf --json report.json --annotate
figspec lint --self-test
```

## 检查项

| check_id | 检查内容 | 级别 |
|---|---|---|
| FONT-EFFECTIVE | 有效字号 >= --min-font（默认 5 pt） | FAIL |
| LINEWIDTH-EFFECTIVE | 有效描边宽度 >= --min-linewidth（默认 0.25 pt） | FAIL |
| FINAL-WIDTH | 页面宽度与 --width 相符（+/- 2 mm） | WARN |
| TEXT-PRESENT | 文档中存在文本对象（未被轮廓化或栅格化） | WARN |
| RASTER-DPI | 放置的位图在显示尺寸下 >= 300 dpi | WARN |
| PAGE-PARSE | 页面内容解析无误（正常时为 PASS，每个仅部分解析成功的页面为 WARN） | WARN |

退出码：0 表示可提交，1 表示存在问题，2 表示输入错误。`--strict` 会将 WARN
提升为不可提交。JSON 结果中的每条 finding 包含
`{check_id, level, message, evidence}`，以及
`page/bbox_mm/nominal_pt/scale/effective_pt`。

属于 FigSpec 工具链的一部分（布局规范 -> 精确尺寸生成 -> 成品检查）。
`figspec.json` 布局规范及生成器在路线图中，尚未实现。

## FigSpec Designer（macOS 应用）

一款可视化布局编辑器，承担工作流的另一半：将符合期刊宽度的画布拆分为多个面板，
拖动分隔线时实时显示 mm 反馈，并导出 `figspec.json`（保存或复制）供你的绘图
agent 使用。面板会自动按阅读顺序标注（a、b、c……），并给出每个面板的
mm / px / figsize 数值。

从源码运行：

```bash
pip install -e . && pip install -e designer
python -m figspec_designer
```

构建已签名的 DMG（需要 Apple Developer ID；env 约定见
`designer/packaging/build_macos.sh`）：

```bash
cd designer/packaging && ./build_macos.sh
```

## MCP 服务（面向 AI agent 的原生访问）

`figspec-mcp` 通过 MCP（stdio）将整套工具链暴露给 AI agent：检查 PDF、
创建/读取/写入 figspec.json，以及编辑布局（拆分/关闭面板、设置提示）——
全部为无状态的文件操作。

```bash
pip install "figspec[mcp]"
claude mcp add figspec -- figspec-mcp
```

工具：`lint_pdf`、`new_spec`、`read_spec`、`write_spec`、`split_panel`、
`close_panel`、`set_panel_hint`、`list_presets`。

## 输出示例

内置自检，针对包内自动生成的样例运行：

```
$ figspec lint --self-test
[ok] good sample is ready
[ok] bad sample: tiny text detected
[ok] bad sample: thin line detected
[ok] form xobject: nested scaling detected
self-test passed
```

对一个问题样例执行检查（面板被缩放至 40%，使 8 pt 标签的有效字号降至
3.2 pt，通过 `figspec.selftest.samples.write_samples` 生成）：

```
$ figspec lint bad.pdf --width 183
figspec lint bad.pdf
[FAIL] FONT-EFFECTIVE: Text effective size 3.20 pt below 5 pt minimum (1 run(s))
  - page 1: 'Scaled tiny text' nominal 8 pt x scale 0.400 = 3.20 pt
[FAIL] LINEWIDTH-EFFECTIVE: Stroke effective width 0.20 pt below 0.25 pt minimum (1 stroke(s))
  - page 1: nominal 0.5 pt x scale 0.400 = 0.20 pt
[PASS] FINAL-WIDTH: Page width 183.0 mm matches target 183.0 mm
[PASS] PAGE-PARSE: All pages parsed cleanly
[PASS] RASTER-DPI: No raster images placed
[PASS] TEXT-PRESENT: 1 text run(s) found
summary: 4 pass, 0 warn, 2 fail
verdict: FIX BEFORE SUBMISSION
note: figspec lint checks the finished artifact geometry; it does not validate scientific content
```

许可证：Apache-2.0
