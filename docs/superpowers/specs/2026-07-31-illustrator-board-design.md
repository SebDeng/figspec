# Illustrator 拼版底板与单 panel 画板（批次 H）

**日期**：2026-07-31
**状态**：Shipped 2026-07-31（批次 H 三任务全部落地；出口 lint 与入口预报数值一致性已在测试与 CLI 演示中验证）
**范围**：把"输出 AI 文件"翻译为"输出 Illustrator 原生可开、物理尺寸精确、分图层的 PDF"。两个产品形态：整图拼版底板（框线图层 + 资产 1:1 预置）、单 panel 画板（作图卡片金路径的可执行版）。

## 决策

1. **不伪造 .ai。** 现代 .ai = PDF + Adobe 私有数据流（无公开规范）；Illustrator 原生打开规矩 PDF 且对象可编辑。输出扩展名诚实用 `.pdf`，UI 文案 "Opens in Illustrator at exact size"。
2. **图层用 PDF OCG**（Optional Content Groups，AI 打开时映射为图层）：`figspec layout`（panel 框线、字母、mm 注记——用户拼完隐藏/删除）与 `figspec content`（预置资产）。绘制顺序 content 在下、layout 在上。
3. **AI guides 无法导出**（私有数据），以 layout 图层里的框线替代——期刊模板通行做法。框线用参考线蓝（0.29,0.56,0.85）0.5 pt，明示"这不是成品墨"。
4. **几何**：MediaBox = TrimBox = 整图 mm 精确换算 pt（`units.mm_to_pt`）；spec 坐标左上原点 y 向下 → PDF 左下原点 y 向上，`lly = H − y_mm − h_mm` 换算。单 panel 画板 MediaBox = panel 尺寸，内容平移到原点。
5. **字体**：base-14 Helvetica / Helvetica-Bold，不嵌入（`selftest/samples.py` 先例）；字母 = `constraints.max_font_pt` Bold，经 `format_label` 按刊风格显示；mm 注记 5 pt 灰。最终嵌入由用户从 AI 导出时完成，lint 在成品端把关。
6. **资产 1:1 预置**：PDF 资产经 `Page.as_form_xobject()` + `copy_foreign` 原样嵌入（矢量保真，板上文字对 lint 解释器仍可读）；raster 资产以 image XObject 嵌入（原始 RGB 字节交给 qpdf 保存期 Flate 压缩）。放置缩放 k 与侧栏完全同一套：PDF 用内在尺寸、raster 用声明 dpi（缺省 96），letterbox 取小轴、居中——**板上所见 = 侧栏所报**。缺失/不可读资产静默跳过，框线保留。
7. **单 panel 画板自带约束注记**（layout 图层，5 pt 灰）："panel c · 60.0 × 36.0 mm · fonts 5.0–7.0 pt · lines ≥ 0.25 pt"——把作图卡片的金路径从"告诉你画布该多大"变成"直接递给你那块画布"。
8. **自产自检**：验收用我们自己的 `figspec.pdf.interpreter.extract` 读回输出——字母字号、预置资产内文字的有效字号（= 资产内有效值 × k）、页面尺寸全部可断言。figspec 第一次同时站在流水线入口和出口。
9. 代码位置：`figspec/board.py`（纯 pikepdf，Qt-free，MCP/CLI 未来复用）；Designer 仅是调用方（File 菜单 + panel 右键）。

## Non-goals

真 .ai 私有数据；SVG；guides；资产的重采样/色彩管理（原样嵌入）；MCP 工具暴露（follow-up）。
