"""Judgement layer: thresholds applied to extracted geometry."""
from __future__ import annotations
from dataclasses import dataclass, field
from figspec.pdf.interpreter import DocumentContent
from figspec.units import pt_to_mm

EPS = 0.01

@dataclass
class LintConfig:
    min_font_pt: float = 5.0
    min_linewidth_pt: float = 0.25
    width_pt: float | None = None
    width_tol_mm: float = 2.0
    min_raster_dpi: float = 300.0

@dataclass
class Finding:
    check_id: str
    level: str  # PASS | WARN | FAIL
    message: str
    evidence: list[str] = field(default_factory=list)
    page: int | None = None
    boxes_pt: list[tuple] = field(default_factory=list)
    bbox_mm: tuple | None = None
    nominal_pt: float | None = None
    scale: float | None = None
    effective_pt: float | None = None

def _union_mm(boxes) -> tuple | None:
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    return tuple(round(pt_to_mm(v), 2) for v in (x0, y0, x1, y1))

def _check_font(doc, cfg):
    bad = [r for r in doc.text_runs if r.effective_pt < cfg.min_font_pt - EPS]
    if not bad:
        yield Finding("FONT-EFFECTIVE", "PASS",
                      f"All text at or above {cfg.min_font_pt:g} pt effective")
        return
    groups: dict[tuple, list] = {}
    for r in bad:
        groups.setdefault((r.page_index, round(r.nominal_pt, 1), round(r.scale, 3)), []).append(r)
    for (page, nominal, scale), runs in sorted(groups.items()):
        eff = nominal * scale
        ev = [f"page {page + 1}: {r.text!r} nominal {r.nominal_pt:g} pt x scale "
              f"{r.scale:.3f} = {r.effective_pt:.2f} pt" for r in runs[:3]]
        if len(runs) > 3:
            ev.append(f"...and {len(runs) - 3} more runs at this size")
        yield Finding(
            "FONT-EFFECTIVE", "FAIL",
            f"Text effective size {eff:.2f} pt below {cfg.min_font_pt:g} pt minimum "
            f"({len(runs)} run(s))",
            evidence=ev, page=page, boxes_pt=[r.bbox_pt for r in runs],
            bbox_mm=_union_mm([r.bbox_pt for r in runs]),
            nominal_pt=nominal, scale=scale, effective_pt=round(eff, 2),
        )

def _check_linewidth(doc, cfg):
    bad = [s for s in doc.strokes if s.effective_w_pt < cfg.min_linewidth_pt - EPS]
    if not bad:
        yield Finding("LINEWIDTH-EFFECTIVE", "PASS",
                      f"All stroked lines at or above {cfg.min_linewidth_pt:g} pt effective")
        return
    groups: dict[tuple, list] = {}
    for s in bad:
        scale = (s.effective_w_pt / s.nominal_w_pt) if s.nominal_w_pt > 0 else 1.0
        groups.setdefault((s.page_index, round(s.nominal_w_pt, 2), round(scale, 3)), []).append(s)
    for (page, nominal, scale), strokes in sorted(groups.items()):
        eff = strokes[0].effective_w_pt
        if nominal == 0:
            msg = (f"{len(strokes)} stroke(s) use line width 0 "
                   f"(PDF 'thinnest renderable line'; prints unpredictably)")
        else:
            msg = (f"Stroke effective width {eff:.2f} pt below "
                   f"{cfg.min_linewidth_pt:g} pt minimum ({len(strokes)} stroke(s))")
        yield Finding(
            "LINEWIDTH-EFFECTIVE", "FAIL", msg,
            evidence=[f"page {page + 1}: nominal {nominal:g} pt x scale {scale:.3f} "
                      f"= {eff:.2f} pt"],
            page=page, boxes_pt=[s.bbox_pt for s in strokes],
            bbox_mm=_union_mm([s.bbox_pt for s in strokes]),
            nominal_pt=nominal, scale=scale, effective_pt=round(eff, 2),
        )

def _check_width(doc, cfg):
    if cfg.width_pt is None or not doc.pages:
        return
    actual_mm = pt_to_mm(doc.pages[0].width_pt)
    target_mm = pt_to_mm(cfg.width_pt)
    if abs(actual_mm - target_mm) <= cfg.width_tol_mm:
        yield Finding("FINAL-WIDTH", "PASS",
                      f"Page width {actual_mm:.1f} mm matches target {target_mm:.1f} mm")
    else:
        yield Finding("FINAL-WIDTH", "WARN",
                      f"Page width {actual_mm:.1f} mm does not match target "
                      f"{target_mm:.1f} mm (tolerance +/-{cfg.width_tol_mm:g} mm)")

def _check_text_present(doc, cfg):
    if doc.text_runs:
        yield Finding("TEXT-PRESENT", "PASS",
                      f"{len(doc.text_runs)} text run(s) found")
    else:
        yield Finding("TEXT-PRESENT", "WARN",
                      "No text objects found: text may be outlined (converted to paths) "
                      "or the figure may be a pure bitmap; font checks cannot run")

def _check_raster(doc, cfg):
    if not doc.images:
        yield Finding("RASTER-DPI", "PASS", "No raster images placed")
        return
    bad = [im for im in doc.images if im.effective_dpi < cfg.min_raster_dpi - EPS]
    if not bad:
        yield Finding("RASTER-DPI", "PASS",
                      f"All {len(doc.images)} raster image(s) at or above "
                      f"{cfg.min_raster_dpi:g} dpi effective")
        return
    for im in bad:
        yield Finding(
            "RASTER-DPI", "WARN",
            f"Raster image {im.px_w}x{im.px_h}px displayed at "
            f"{im.effective_dpi:.0f} dpi effective (below {cfg.min_raster_dpi:g} dpi)",
            page=im.page_index, boxes_pt=[im.bbox_pt], bbox_mm=_union_mm([im.bbox_pt]),
            effective_pt=None,
        )

def _check_parse_errors(doc, cfg):
    for page, msg in doc.parse_errors:
        yield Finding("PAGE-PARSE", "WARN",
                      f"Page {page + 1} only partially analyzed",
                      evidence=[msg], page=page)

def run_checks(doc: DocumentContent, cfg: LintConfig) -> list:
    findings = []
    for chk in (_check_font, _check_linewidth, _check_width,
                _check_text_present, _check_raster, _check_parse_errors):
        findings.extend(chk(doc, cfg))
    return findings
