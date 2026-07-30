import pytest
from tests.fixtures import (compose_scaled, make_panel, make_raster_panel,
                            make_textpath_panel)

@pytest.fixture(scope="session")
def mpl_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("mpl")
    make_panel(d / "panel42.pdf", fontsize=7.0, fonttype=42)
    make_panel(d / "panel3.pdf", fontsize=7.0, fonttype=3)
    compose_scaled(d / "panel42.pdf", d / "assembled045.pdf", scale=0.45)
    make_textpath_panel(d / "outlined.pdf")
    make_raster_panel(d / "raster.pdf", px=100, inches=2.0)  # 50 dpi effective
    return d
