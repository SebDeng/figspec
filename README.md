[English](README.md) | [中文](README.zh-CN.md)

# figspec

Lint finished figure PDFs for **effective** (post-scaling) font sizes and line widths.

When a matplotlib panel is placed into Illustrator and scaled to fit, a nominal
7 pt label can silently become a 3 pt label. Illustrator's font panel still
shows 7 pt. figspec opens the *finished* PDF, multiplies every text object's
font size through the full PDF transform stack (including Form XObjects —
i.e. placed, scaled panels), and reports what will actually print.

## Install

```bash
pip install figspec
```

## Use

```bash
figspec lint final.pdf --width 183mm
figspec lint final.pdf --json report.json --annotate
figspec lint --self-test
```

## Checks

| check_id | what it verifies | level |
|---|---|---|
| FONT-EFFECTIVE | effective text size >= --min-font (default 5 pt) | FAIL |
| LINEWIDTH-EFFECTIVE | effective stroke width >= --min-linewidth (default 0.25 pt) | FAIL |
| FINAL-WIDTH | page width matches --width (+/- 2 mm) | WARN |
| TEXT-PRESENT | document contains text objects (not outlined/rasterized) | WARN |
| RASTER-DPI | placed bitmaps >= 300 dpi at displayed size | WARN |
| PAGE-PARSE | page content parsed without errors (PASS when clean, WARN per partially-analyzed page) | WARN |

Exit codes: 0 ready, 1 findings, 2 input error. `--strict` promotes WARN.
JSON findings use `{check_id, level, message, evidence}` plus
`page/bbox_mm/nominal_pt/scale/effective_pt`.

Part of the FigSpec toolchain (layout spec -> exact-size generation -> artifact
lint). The `figspec.json` layout spec and generator are on the roadmap.

## FigSpec Designer (macOS app)

A visual layout editor for the other half of the workflow: split a
journal-width canvas into panels, drag gutters with live mm feedback, and
export `figspec.json` (Save or Copy) for your plotting agent. Panels carry
auto reading-order labels (a, b, c…) and per-panel mm / px / figsize values.

Run from source:

```bash
pip install -e . && pip install -e designer
python -m figspec_designer
```

Build a signed DMG (needs Apple Developer ID; see
`designer/packaging/build_macos.sh` for the env contract):

```bash
cd designer/packaging && ./build_macos.sh
```

## Example output

Built-in self test, run against the package's own generated samples:

```
$ figspec lint --self-test
[ok] good sample is ready
[ok] bad sample: tiny text detected
[ok] bad sample: thin line detected
[ok] form xobject: nested scaling detected
self-test passed
```

Linting a bad sample (a panel scaled to 40%, dropping an 8 pt label to an
effective 3.2 pt, generated via `figspec.selftest.samples.write_samples`):

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

License: Apache-2.0
