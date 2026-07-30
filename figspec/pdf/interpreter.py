"""Graphics-state machine over pikepdf.parse_content_stream.

Extracts geometric facts (text runs, stroked paths, placed images) with
*effective* (device-space) sizes. Judgement happens in figspec.lint.checks.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from pathlib import Path
import pikepdf
from figspec.pdf.geometry import Mat
from figspec.pdf.fonts import FontInfo, load_font, decode_codes

class LintInputError(Exception):
    """File cannot be read as a PDF (missing, encrypted, corrupt)."""

@dataclass
class TextRun:
    page_index: int
    text: str
    font_name: str
    nominal_pt: float
    effective_pt: float
    scale: float
    bbox_pt: tuple

@dataclass
class StrokePath:
    page_index: int
    nominal_w_pt: float
    effective_w_pt: float
    bbox_pt: tuple

@dataclass
class PlacedImage:
    page_index: int
    px_w: int
    px_h: int
    effective_dpi: float
    bbox_pt: tuple

@dataclass
class PageInfo:
    index: int
    width_pt: float
    height_pt: float

@dataclass
class DocumentContent:
    pages: list[PageInfo] = field(default_factory=list)
    text_runs: list[TextRun] = field(default_factory=list)
    strokes: list[StrokePath] = field(default_factory=list)
    images: list[PlacedImage] = field(default_factory=list)
    parse_errors: list[tuple[int, str]] = field(default_factory=list)

@dataclass
class _GState:
    ctm: Mat = field(default_factory=Mat)
    line_width: float = 1.0

@dataclass
class _TState:
    font: FontInfo | None = None
    size: float = 0.0
    char_spacing: float = 0.0
    word_spacing: float = 0.0
    h_scale: float = 1.0
    leading: float = 0.0
    rise: float = 0.0
    render_mode: int = 0

def _num(x) -> float:
    return float(x)

def _bbox_union(points) -> tuple:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))

class _Walker:
    def __init__(self, doc: DocumentContent, page_index: int):
        self.doc = doc
        self.page_index = page_index

    def walk(self, container, resources, ctm: Mat, form_stack: frozenset):
        gs = _GState(ctm=ctm)
        stack: list[tuple[_GState, _TState]] = []
        ts = _TState()
        tm = Mat()
        tlm = Mat()
        fonts: dict[str, FontInfo] = {}
        path_pts: list[tuple] = []
        in_text = False

        def font_for(name: str) -> FontInfo:
            if name not in fonts:
                try:
                    fonts[name] = load_font(resources["/Font"][name])
                except Exception:
                    fonts[name] = FontInfo(name=name.lstrip("/"))
            return fonts[name]

        for instr in pikepdf.parse_content_stream(container):
            if isinstance(instr, pikepdf.ContentStreamInlineImage):
                continue  # inline images: out of MVP scope
            op = str(instr.operator)
            ops = instr.operands

            if op == "q":
                # PDF32000 8.4/9.3: text-state parameters (Tc, Tw, Tz, TL,
                # Tf/Tfs, Tr, Ts) are part of the graphics state and must be
                # saved/restored by q/Q, unlike Tm/Tlm which reset at BT.
                stack.append((replace(gs), replace(ts)))
            elif op == "Q":
                if stack:
                    gs, ts = stack.pop()
            elif op == "cm":
                gs.ctm = Mat.from_seq(ops) @ gs.ctm
            elif op == "w":
                gs.line_width = _num(ops[0])
            elif op == "gs":
                self._apply_extgstate(gs, resources, ops)
            elif op == "BT":
                in_text, tm, tlm = True, Mat(), Mat()
            elif op == "ET":
                in_text = False
            elif op == "Tf":
                ts.font, ts.size = font_for(str(ops[0])), _num(ops[1])
            elif op == "Td":
                tlm = Mat(1, 0, 0, 1, _num(ops[0]), _num(ops[1])) @ tlm
                tm = tlm
            elif op == "TD":
                ts.leading = -_num(ops[1])
                tlm = Mat(1, 0, 0, 1, _num(ops[0]), _num(ops[1])) @ tlm
                tm = tlm
            elif op == "Tm":
                tm = tlm = Mat.from_seq(ops)
            elif op == "T*":
                tlm = Mat(1, 0, 0, 1, 0, -ts.leading) @ tlm
                tm = tlm
            elif op == "TL":
                ts.leading = _num(ops[0])
            elif op == "Tc":
                ts.char_spacing = _num(ops[0])
            elif op == "Tw":
                ts.word_spacing = _num(ops[0])
            elif op == "Tz":
                ts.h_scale = _num(ops[0]) / 100.0
            elif op == "Ts":
                ts.rise = _num(ops[0])
            elif op == "Tr":
                ts.render_mode = int(ops[0])
            elif op == "Tj":
                tm = self._show(bytes(ops[0]), ts, tm, gs)
            elif op == "'":
                tlm = Mat(1, 0, 0, 1, 0, -ts.leading) @ tlm
                tm = self._show(bytes(ops[0]), ts, tlm, gs)
            elif op == '"':
                ts.word_spacing, ts.char_spacing = _num(ops[0]), _num(ops[1])
                tlm = Mat(1, 0, 0, 1, 0, -ts.leading) @ tlm
                tm = self._show(bytes(ops[2]), ts, tlm, gs)
            elif op == "TJ":
                for item in ops[0]:
                    if isinstance(item, pikepdf.String):
                        tm = self._show(bytes(item), ts, tm, gs)
                    else:
                        dx = -_num(item) / 1000.0 * ts.size * ts.h_scale
                        tm = Mat(1, 0, 0, 1, dx, 0) @ tm
            # path + XObject operators land in Tasks 7-8:
            elif op in ("m", "l", "re", "c", "v", "y", "h",
                        "S", "s", "B", "B*", "b", "b*", "f", "F", "f*", "n"):
                path_pts = self._path_op(op, ops, gs, path_pts)
            elif op == "Do":
                self._do_xobject(str(ops[0]), resources, gs, form_stack)

    def _show(self, data: bytes, ts: _TState, tm: Mat, gs: _GState) -> Mat:
        if ts.font is None or ts.size == 0:
            return tm
        pairs = decode_codes(ts.font, data)
        advance = 0.0
        for code, _ in pairs:
            w = ts.font.widths.get(code, ts.font.default_width)
            advance += w * ts.size + ts.char_spacing
            if code == 32 and ts.font.code_size == 1:
                advance += ts.word_spacing
        advance *= ts.h_scale

        combined = tm @ gs.ctm
        scale = combined.vertical_scale()
        if ts.render_mode not in (3, 7):  # skip invisible / clip-only text
            corners = [
                combined.apply(0, ts.rise - 0.25 * ts.size),
                combined.apply(advance, ts.rise - 0.25 * ts.size),
                combined.apply(0, ts.rise + 0.85 * ts.size),
                combined.apply(advance, ts.rise + 0.85 * ts.size),
            ]
            text = "".join(u for _, u in pairs)
            self.doc.text_runs.append(TextRun(
                page_index=self.page_index,
                text=text if text.strip() else "(undecoded text)",
                font_name=ts.font.name,
                nominal_pt=ts.size,
                effective_pt=ts.size * scale,
                scale=scale,
                bbox_pt=_bbox_union(corners),
            ))
        return Mat(1, 0, 0, 1, advance, 0) @ tm

    def _apply_extgstate(self, gs, resources, ops):
        pass  # Task 8

    def _path_op(self, op, ops, gs, path_pts):
        nums = [_num(v) for v in ops]
        if op == "m" or op == "l":
            path_pts.append(gs.ctm.apply(nums[0], nums[1]))
        elif op == "c":
            for i in range(0, 6, 2):
                path_pts.append(gs.ctm.apply(nums[i], nums[i + 1]))
        elif op == "v" or op == "y":
            for i in range(0, 4, 2):
                path_pts.append(gs.ctm.apply(nums[i], nums[i + 1]))
        elif op == "re":
            x, y, w, h = nums
            for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
                path_pts.append(gs.ctm.apply(px, py))
        elif op == "h":
            pass
        elif op in ("S", "s", "B", "B*", "b", "b*"):
            if path_pts:
                _, s_min = gs.ctm.singular_values()
                self.doc.strokes.append(StrokePath(
                    page_index=self.page_index,
                    nominal_w_pt=gs.line_width,
                    effective_w_pt=gs.line_width * s_min,
                    bbox_pt=_bbox_union(path_pts),
                ))
            return []
        elif op in ("f", "F", "f*", "n"):
            return []
        return path_pts

    def _do_xobject(self, name, resources, gs, form_stack):
        try:
            xobj = resources["/XObject"][name]
        except Exception:
            return
        subtype = str(xobj.get("/Subtype", ""))
        if subtype == "/Image":
            px_w, px_h = int(xobj.Width), int(xobj.Height)
            ex = (gs.ctm.a ** 2 + gs.ctm.b ** 2) ** 0.5   # device length of unit x edge, pt
            ey = (gs.ctm.c ** 2 + gs.ctm.d ** 2) ** 0.5
            dpi_x = px_w / (ex / 72.0) if ex > 1e-9 else float("inf")
            dpi_y = px_h / (ey / 72.0) if ey > 1e-9 else float("inf")
            corners = [gs.ctm.apply(x, y) for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))]
            self.doc.images.append(PlacedImage(
                page_index=self.page_index, px_w=px_w, px_h=px_h,
                effective_dpi=min(dpi_x, dpi_y), bbox_pt=_bbox_union(corners),
            ))
        elif subtype == "/Form":
            pass  # Task 8

def _page_resources(page) -> pikepdf.Object:
    res = page.get("/Resources")
    return res if res is not None else pikepdf.Dictionary()

def extract(path) -> DocumentContent:
    path = Path(path)
    doc = DocumentContent()
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError as e:
        raise LintInputError(f"{path}: encrypted PDF (password required)") from e
    except Exception as e:
        raise LintInputError(f"{path}: cannot open as PDF: {e}") from e
    with pdf:
        for i, page in enumerate(pdf.pages):
            try:
                box = [float(v) for v in page.MediaBox]
                doc.pages.append(PageInfo(index=i, width_pt=box[2] - box[0], height_pt=box[3] - box[1]))
            except Exception as e:
                doc.parse_errors.append((i, f"{type(e).__name__}: {e}"))
                doc.pages.append(PageInfo(index=i, width_pt=0.0, height_pt=0.0))
                continue  # no usable page geometry; skip walking this page's content
            try:
                _Walker(doc, i).walk(page, _page_resources(page), Mat(), frozenset())
            except Exception as e:
                doc.parse_errors.append((i, f"{type(e).__name__}: {e}"))
    return doc
