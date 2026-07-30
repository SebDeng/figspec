"""Synthetic ground-truth figures: matplotlib panels + pypdf scaled assembly."""
from pathlib import Path

def make_panel(path: Path, fontsize: float = 7.0, fonttype: int = 42,
               linewidth: float = 0.5) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "pdf.fonttype": fonttype, "font.size": fontsize,
        "axes.labelsize": fontsize, "xtick.labelsize": fontsize,
        "ytick.labelsize": fontsize, "axes.linewidth": linewidth,
        "xtick.major.width": linewidth, "ytick.major.width": linewidth,
    })
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    ax.plot([0, 1, 2], [0, 1, 0], linewidth=linewidth)
    ax.set_xlabel("Vds (V)")
    ax.set_ylabel("Current (uA)")
    fig.savefig(path)
    plt.close(fig)

def make_textpath_panel(path: Path) -> None:
    """All text converted to paths -> zero text objects."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.patches import PathPatch
    from matplotlib.textpath import TextPath
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.set_axis_off()
    tp = TextPath((0.1, 0.5), "Outlined", size=0.2)
    ax.add_patch(PathPatch(tp, facecolor="black", linewidth=0))
    ax.set_xlim(0, 2); ax.set_ylim(0, 1)
    fig.savefig(path)
    plt.close(fig)

def make_raster_panel(path: Path, px: int = 100, inches: float = 2.0) -> None:
    """A px-by-px image displayed at `inches` -> effective dpi = px / inches."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig = plt.figure(figsize=(inches, inches))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.imshow(np.random.default_rng(0).random((px, px)), interpolation="none")
    fig.savefig(path, dpi=72)
    plt.close(fig)

def compose_scaled(panel: Path, out: Path, scale: float,
                   page_w_mm: float = 183.0, page_h_mm: float = 120.0) -> None:
    """Simulate Illustrator 'place + scale' with pypdf."""
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf import PageObject
    reader = PdfReader(str(panel))
    src = reader.pages[0]
    w, h = page_w_mm * 72 / 25.4, page_h_mm * 72 / 25.4
    page = PageObject.create_blank_page(width=w, height=h)
    page.merge_transformed_page(src, Transformation().scale(scale).translate(20, 20))
    writer = PdfWriter()
    writer.add_page(page)
    with open(out, "wb") as fh:
        writer.write(fh)
