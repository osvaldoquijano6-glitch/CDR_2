import textwrap

import pytest

from gcv.ingestion.base import read_file
from gcv.models import MappingMethod
from gcv.normalization.cleaning import ManualCorrections
from gcv.normalization.column_mapper import normalize


@pytest.fixture
def csv_sucio(tmp_path):
    """CSV con preámbulo, duplicado, desorden, valor no numérico y kW."""
    path = tmp_path / "poi.csv"
    path.write_text(textwrap.dedent("""\
        Analizador;Hioki PW3198
        ;
        Date/Time;Frequency [Hz];Active Power [kW];Comentario
        2026-07-01 10:00:00;60.01;25000;ok
        2026-07-01 10:00:02;59.99;25005;ok
        2026-07-01 10:00:01;60.02;error;mal
        2026-07-01 10:00:01;60.02;25010;dup
        """), encoding="utf-8")
    return path


def test_pipeline_completo(csv_sucio):
    ds = normalize(read_file(csv_sucio))

    # columnas canónicas
    assert list(ds.df.columns) == ["timestamp", "frequency", "active_power"]
    # ordenado y deduplicado: 3 filas
    assert len(ds.df) == 3
    assert ds.df["timestamp"].is_monotonic_increasing
    # kW → MW
    assert ds.df["active_power"].iloc[0] == pytest.approx(25.0)
    # 'error' → NaN
    assert ds.df["active_power"].isna().sum() == 1
    # trazabilidad del mapeo
    freq_map = next(m for m in ds.mappings if m.senal_canonica == "frequency")
    assert freq_map.columna_original == "Frequency [Hz]"
    assert freq_map.metodo == MappingMethod.AUTO_ALIAS
    # calidad
    assert ds.quality.n_filas == 3
    assert ds.quality.fs_detectada_hz == pytest.approx(1.0)
    # bitácora registró las transformaciones clave
    acciones = {a.accion for a in ds.log.acciones}
    assert {"encabezado", "parse_timestamps", "conversion_unidad",
            "reordenamiento_temporal", "dedup_timestamps"} <= acciones
    assert ds.source_sha256 is not None


def test_mapeo_manual_y_exclusion(csv_sucio):
    corr = ManualCorrections.from_dict({
        "drop_time_ranges": [["2026-07-01 10:00:02", "2026-07-01 10:00:03"]],
        "motivo": "ventana con maniobra ajena a la prueba",
    })
    ds = normalize(read_file(csv_sucio), corrections=corr)
    assert len(ds.df) == 2
    drop = next(a for a in ds.log.acciones if a.accion == "drop_rango_manual")
    assert drop.parametros["motivo"] == "ventana con maniobra ajena a la prueba"


def test_sin_columna_tiempo_falla(tmp_path):
    path = tmp_path / "sin_tiempo.csv"
    path.write_text("Frequency;Active Power\n60.0;25\n60.1;26\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columna de tiempo"):
        normalize(read_file(path))


def test_bitacora_serializable(csv_sucio, tmp_path):
    ds = normalize(read_file(csv_sucio))
    out = ds.log.save(tmp_path / "bitacora.json")
    assert out.exists() and out.read_text(encoding="utf-8").startswith("{")
