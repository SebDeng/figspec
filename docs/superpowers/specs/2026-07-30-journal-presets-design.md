# 期刊预设修正与每预设约束（已批准）

**日期**：2026-07-30
**状态**：Approved（基于四社官方规范调研——约 30 条关键数字经独立核验零错配；用户对修正表与方案回复"都做"）
**数据来源**：2026-07-30 调研 workflow（Nature/Science/APS/ACS 官方文档），完整结构化结果与来源 URL 见调研输出；本次落库为 `docs/journal-figure-specs.md`。

## 1. PRESETS 修正与扩充（`designer/figspec_designer/presets.py`）

| key | 宽 mm | 依据 |
|---|---|---|
| nature_single / nature_double | 89.0 / 183.0（不变） | Nature final-submission + artwork 指南（正式指南与 formatting guide 的 90/180 冲突，取前者为权威并在文档记录） |
| **nature_research_single / _double**（新增） | 88.0 / 180.0 | Nature 子刊 + Nature Communications AIP 指南 |
| **science_single / science_double**（新增） | 90.0 / 183.0 | Science《Guide to Preparing Figures》2025 PDF（21p3 / 43p4；HTML 页的 57/121/184 三栏制冲突记录在文档） |
| acs_single | 82.5 → **84.7** | JACS 指南（2026-07-03 版）：单栏上限 240 pt |
| acs_double | 178.0 → **177.8** | 504 pt（双栏区间 300–504 pt，预设取上限） |
| aps_single | 86.0 → **85.0** | APS Style Guide 2026-02：8.5 cm |
| aps_double | 172.0 → **178.0** | 仅存于 2011 legacy 指南（现行指南无双栏数字），文档标注 |

## 2. 每预设约束默认（新增 `PRESET_CONSTRAINTS: dict[str, dict]`）

| preset 族 | min_font_pt | max_font_pt | min_linewidth_pt | 备注 |
|---|---|---|---|---|
| nature_* / nature_research_* | 5.0 | 7.0 | 0.25 | panel 标号 8pt 为唯一例外；NComms 线宽 ≥1pt 的特例记录在文档不进预设 |
| science_* | 5.0 | 10.0 | 0.5 | 字号 HTML 口径（5 底 7 目标），panel 标号 10pt；线宽取两口径（0.5 vs 0.28）中保守者 |
| acs_* | 4.5 | 8.0 | 0.5 | ACS 无官方字号上限，8.0 为工具默认值（文档标注非官方） |
| aps_* | 8.0 | 10.0 | 0.5 | **派生值**：APS 规定最小大写字高 2mm，按 Helvetica cap≈0.717em 折算名义 ≈7.9pt，取 8.0，文档明示派生逻辑 |

语义：TopBar 选中期刊预设时，宽度与三个约束 spinbox 一并写入（blockSignals 批量设置后发一次 `settings_changed`）；选 "custom" 只解锁宽度、**不动**约束当前值。

## 3. `docs/journal-figure-specs.md`（新文件）

完整四社对比表 + 每个数字的来源 URL + 访问日期（2026-07-30）+ 单位换算标注 + "出版社自相矛盾处"专节（Nature 89/183/247 vs 90/180/170；Science 三栏 HTML vs 双栏 PDF；Science 0.5 vs 0.28 pt；APS 双栏仅 legacy；NComms 2080px≠180mm）+ 未核验残留清单。数据取自调研 workflow 结构化输出（含 verifier 核验结论）。中文正文、URL 原样。

## 4. 验收

- 现有测试全绿（个别断言旧预设值的测试同步更新——仅限数值，语义不变）；新增：预设→约束联动、custom 不动约束、新预设键存在性。
- 明确不做：figlint CLI 默认值变更（5/0.25 与 Nature 口径一致，保持）；README 数值表不动。
