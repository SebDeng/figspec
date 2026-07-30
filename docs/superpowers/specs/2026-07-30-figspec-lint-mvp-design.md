# figspec lint MVP 设计（已批准）

**日期**：2026-07-30
**状态**：Approved
**上游文档**：`figspec-设计文档.md`（Draft v0.1）§6 MVP 章节
**决策背景**：对 nature-skills（32k stars）的竞品调研确认"成品 PDF 有效字号/线宽校验"生态位完全敞开，但技术窗口以月计——其校验器加一个 PDF 解析检查只差一个 import。先做 Linter，快速开源占位。

## 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 发布意图 | 尽快开源发布（PyPI） | 抢占生态位；宽松协议是硬约束 |
| 包名/命令 | 包 `figspec`，命令 `figspec lint`（子命令结构，将来 `figspec gen`） | 一个名字贯穿工具链，用户拍板 |
| PDF 技术栈 | pikepdf（MPL-2.0）`parse_content_stream` + 自写图形状态机；pypdfium2（BSD/Apache）渲染 | 用户选定。矩阵数学是本工具的灵魂，自有状态机可控且为 v2 反向导入复用；pikepdf 自带 tokenizer 使成本可控（约四五百行） |
| 协议 | Apache-2.0 | 带专利条款，与目标生态（nature-skills 亦为 Apache-2.0）一致 |
| 测试策略 | 合成真值集（无真实稿件样本） | matplotlib 出图 + pypdf 程序化缩放拼版，真值可精确断言 |
| 语言 | 英文 CLI/代码/注释；中英双 README | 开源可达性 |

## 1. 范围（MVP）

```
figspec lint final.pdf [--width 183mm] [--min-font 5] [--min-linewidth 0.25]
                       [--json [PATH]] [--annotate [PATH]] [--strict] [--self-test]
```

独立模式，不读 figspec.json（spec 输入是 v1）。检查项五个：

| check_id | 内容 | 违规级别 |
|---|---|---|
| `FONT-EFFECTIVE` | 文本有效字号（缩放后）< `--min-font`（默认 5 pt） | FAIL |
| `LINEWIDTH-EFFECTIVE` | 描边有效线宽 < `--min-linewidth`（默认 0.25 pt） | FAIL |
| `FINAL-WIDTH` | TrimBox（缺省 MediaBox）宽度 vs `--width`，容差 ±2 mm；未给 `--width` 则跳过 | WARN |
| `TEXT-PRESENT` | 整份文件无任何 text object（疑似全部转曲或纯位图） | WARN |
| `RASTER-DPI` | 置入位图有效 DPI（像素尺寸 ÷ 显示物理尺寸）< 300 | WARN |

明确不做（MVP 外）：spec 输入与 panel 归属、字体嵌入检查、panel 标签风格、色彩模式、CMYK、多页处理策略以外的排版检查。CLI 永不交互提问（CI 场景硬约束，竞品阻塞式问询是反面教材）。

## 2. 核心数学

- **文本**：累积渲染矩阵 = 字号 Tfs 与文本矩阵 Tm、各层 CTM 的连乘。取其 2×2 线性部分做 SVD，**有效字号 = 名义字号 × 竖直方向奇异值**；旋转文字（纵轴标题）由奇异值天然正确处理。
- **线宽**：有效线宽 = graphics state 的 `w` × CTM 奇异值；各向异性缩放取**最小奇异值**（报最坏情况）。`w=0`（PDF 规范的"最细线"）单独归为违规并特殊措辞。
- **Form XObject 递归是第一公民**：Illustrator 置入并缩放的 panel 即带 /Matrix 的 Form XObject。解释器遇 `Do` → 叠乘 placement CTM × XObject /Matrix → 递归其 content stream。嵌套无深度假设（防循环引用需 visited 集）。
- **单位**：内部一律 pt（1 pt = 1/72 in）；报告输出同时给 pt 与 mm。Type 3 字体经其 FontMatrix 换算后走同一条奇异值路径。
- **UserUnit**：页面若带 /UserUnit 需乘入物理尺寸换算（罕见但廉价）。

## 3. 架构

```
figspec/
  __init__.py         # __version__
  cli.py              # argparse 子命令路由：figspec lint ...
  units.py            # "183mm" / "6pt" / "3.5in" → pt；pt↔mm 换算
  pdf/
    interpreter.py    # 状态机：q/Q 栈、CTM、text state；遍历 pikepdf.parse_content_stream
                      # 产物：TextRun / StrokePath / PlacedImage（均带 page、bbox_pt、有效值）
    fonts.py          # 字体尺寸元数据；ToUnicode 尽力解码；Type3 FontMatrix
  lint/
    checks.py         # 检查注册表：吃解释器产物列表，产 Finding 列表
    report.py         # Finding schema + 文本渲染 + JSON 渲染 + 退出码
    annotate.py       # pypdfium2 渲染页面 → Pillow 叠加红(FAIL)/黄(WARN)框 + "3.2 pt ✗" 标签
  selftest/           # --self-test 用内嵌样本（好/坏各一，运行时以代码在临时目录合成，不带数据文件）
tests/
  fixtures.py         # 合成真值集生成器
  test_interpreter.py / test_checks.py / test_cli.py
```

运行依赖：`pikepdf`、`pypdfium2`、`Pillow`。测试依赖另加 `matplotlib`、`pypdf`、`pytest`。

**产物边界**：interpreter 只产几何事实（不判定）；checks 只判定（不解析）；report 只格式化。三层可独立测试。

## 4. 报告契约

Finding 结构与 nature-figure 的 validate_figure.py 同构以便互操作（两份报告可进同一个 agent 修复循环）：

```json
{
  "source": "final.pdf",
  "tool": {"name": "figspec", "version": "0.1.0"},
  "summary": {"ready": false, "strict": false, "counts": {"PASS": 3, "WARN": 1, "FAIL": 1}},
  "findings": [{
    "check_id": "FONT-EFFECTIVE",
    "level": "FAIL",
    "message": "Text effective size 3.2 pt below 5 pt minimum",
    "evidence": ["page 1: 'Vds (V)' nominal 7.0 pt x scale 0.45 = 3.2 pt"],
    "page": 1, "bbox_mm": [12.1, 40.3, 31.8, 43.0],
    "nominal_pt": 7.0, "scale": 0.457, "effective_pt": 3.2
  }]
}
```

- 同一 text run/同缩放系数的相邻违规聚簇为一条 finding；终端文本输出每类最多展示 10 条 + 汇总计数，JSON 全量。
- `--json` 不带参数 → 输出到 stdout（此时人读报告转 stderr）；`--json PATH` → 写文件，人读报告照常 stdout。
- 退出码：0 = ready（无 FAIL，`--strict` 下也无 WARN）；1 = not ready；2 = 输入/参数错误。
- 标注 PNG：`--annotate` 缺省输出 `<input>.lint.png`，页面渲染 150 dpi。

## 5. 测试（合成真值集）

`tests/fixtures.py` 生成、缓存于 tests/data/（生成脚本入库，产物不入库）：

1. **基准失效样本**：matplotlib 7 pt 字号 panel PDF → pypdf `Transformation().scale(0.45)` 置入 183 mm 宽页面 → 断言检出 effective 3.15 pt（±0.05）。
2. **字体路径**：同一 panel 以 `pdf.fonttype=42`（TrueType）与 `pdf.fonttype=3`（Type 3）各出一版，断言两者有效字号一致。
3. **旋转文字**：带 ylabel 的 panel，断言旋转 90° 文本字号计算正确。
4. **转曲样本**：matplotlib `TextPath` 出纯路径文字 → 断言触发 TEXT-PRESENT WARN 且无 FONT 误报。
5. **位图样本**：PNG 置入并缩放 → 断言 RASTER-DPI 按显示尺寸反推正确。
6. **通过样本**：1:1 摆放、7 pt、0.5 pt 线宽 → 断言全 PASS、退出码 0。

另内嵌 `--self-test`（好/坏样本 + 断言，运行不依赖 tests/），作为用户侧可信度自证。

## 6. 错误处理

- 加密/损坏 PDF：明确错误信息，退出码 2。
- 单页 content stream 解析异常：该页降级为 WARN（`PAGE-PARSE`，复用 evidence 字段带异常摘要），其余页继续。
- 未知操作符：按设计忽略（状态机只实现涉及几何与文本的算子子集）。
- 无 ToUnicode 的文字：evidence 显示 `(undecoded text)`，不影响字号判定。
- 多页 PDF：逐页全部检查，finding 带页码（论文 figure 通常单页，多页不特殊处理）。

## 7. 工程与发布

- `Desktop/FigSpec` git init；`pyproject.toml`（hatchling 或 setuptools，entry point `figspec = figspec.cli:main`）第一天即按 PyPI 发布配置；Apache-2.0 LICENSE。
- README 中英双语；首个 demo 素材：对 nature-skills 自带示例（711 mm/32 pt 过其自检）跑 figspec lint 的对比截图。
- skill/MCP 包装、上游互操作 PR 均为 MVP 后续，不在本期。
