import pytest

from gcv.ingestion.base import FileFormat, read_file


@pytest.fixture
def comtrade_ascii(tmp_path):
    """Registro COMTRADE 1999 ASCII mínimo: 1 canal analógico, 1 digital, 4 muestras."""
    cfg = tmp_path / "registro.cfg"
    dat = tmp_path / "registro.dat"
    cfg.write_text(
        "SUBESTACION X,REG1,1999\n"
        "2,1A,1D\n"
        "1,VA,A,,V,0.01,0.0,0.0,-32768,32767,1200.0,1.0,P\n"
        "1,TRIP,,,0\n"
        "60\n"
        "1\n"
        "1200,4\n"
        "01/07/2026,10:00:00.000000\n"
        "01/07/2026,10:00:00.100000\n"
        "ASCII\n"
        "1.0\n",
        encoding="ascii",
    )
    dat.write_text(
        "1,0,13800,0\n"
        "2,833,13810,0\n"
        "3,1666,13790,0\n"
        "4,2500,13805,1\n",
        encoding="ascii",
    )
    return cfg


def test_comtrade_basico(comtrade_ascii):
    raw = read_file(comtrade_ascii)
    assert raw.formato == FileFormat.COMTRADE
    assert raw.header_resolved
    assert "VA" in raw.grid.columns
    assert "TRIP" in raw.grid.columns
    assert "timestamp" in raw.grid.columns
    assert len(raw.grid) == 4
    # factor a=0.01: 13800 crudo → 138.0 V
    assert raw.grid["VA"].iloc[0] == pytest.approx(138.0)
    assert raw.units["VA"] == "V"
    assert raw.metadata["frecuencia_nominal_hz"] == 60.0
    assert raw.grid["TRIP"].iloc[3] == 1


def test_comtrade_acepta_ruta_dat(comtrade_ascii):
    dat = comtrade_ascii.with_suffix(".dat")
    raw = read_file(dat)
    assert raw.formato == FileFormat.COMTRADE


def test_comtrade_falta_dat(tmp_path):
    cfg = tmp_path / "solo.cfg"
    cfg.write_text("X,Y,1999\n")
    with pytest.raises(FileNotFoundError):
        read_file(cfg)
