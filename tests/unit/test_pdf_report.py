"""Test del informe PDF directo (Chromium/weasyprint)."""

import pandas as pd
import pytest

from gcv.evaluation.frequency.rango_frecuencia import RangoFrecuencia
from gcv.models import Category, Installation, InstallationKind, Technology
from gcv.reporting.context import ReportContext
from gcv.reporting.pdf_report import export_pdf, pdf_disponible
from gcv.visualization.evidence import build_figures

from tests.unit.helpers import make_dataset, make_spec, ts


def _ctx():
    df = pd.DataFrame({"timestamp": ts(40), "frequency": [60.0] * 40,
                       "active_power": [80.0] * 40})
    ds = make_dataset(df)
    spec = make_spec("CE-F-01", ["timestamp", "frequency", "active_power"],
                     limites={"bandas": [{"f_min": 59.5, "f_max": 61.0, "t_min_s": 10}]})
    r = RangoFrecuencia(spec).run(ds)
    inst = Installation(nombre="Central X", kind=InstallationKind.CENTRAL_ELECTRICA,
                        tech=Technology.ASINCRONA, category=Category.C)
    return ReportContext(proyecto="Demo", installation=inst, resultados=[r],
                         datasets=[ds], figuras={r.test_id: build_figures(r, ds)})


@pytest.mark.skipif(not pdf_disponible(), reason="sin Chromium ni weasyprint")
def test_export_pdf(tmp_path):
    path = export_pdf(_ctx(), tmp_path / "informe.pdf")
    assert path.exists()
    assert path.read_bytes()[:5] == b"%PDF-"
    assert path.stat().st_size > 10_000


def test_export_pdf_sin_motor(monkeypatch, tmp_path):
    """Sin motor disponible, export_pdf falla con mensaje claro (no silencioso)."""
    import gcv.reporting.pdf_report as mod
    monkeypatch.setattr(mod, "_chromium", lambda: None)
    monkeypatch.setattr(mod, "_via_weasyprint", lambda *a: False)
    with pytest.raises(RuntimeError, match="motor de impresión"):
        export_pdf(_ctx(), tmp_path / "x.pdf")
