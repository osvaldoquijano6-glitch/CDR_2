import textwrap

import pytest

from gcv.ingestion.base import FileFormat, read_file
from gcv.ingestion.csv_reader import detect_separator
from gcv.normalization.header_detect import apply_header, detect_header


@pytest.fixture
def csv_con_preambulo(tmp_path):
    path = tmp_path / "elspec_export.csv"
    path.write_text(textwrap.dedent("""\
        Equipo;Elspec G4500
        Campania;POI Central X
        ;
        Date/Time;Frequency [Hz];Active Power [kW];Voltage (kV)
        2026-07-01 10:00:00;60.01;25000;230.1
        2026-07-01 10:00:01;60.02;25010;230.2
        2026-07-01 10:00:02;59.99;25005;230.0
        """), encoding="utf-8")
    return path


def test_detect_separator():
    assert detect_separator("a;b;c\n1;2;3") == ";"
    assert detect_separator("a,b,c\n1,2,3") == ","
    assert detect_separator("a\tb\tc\n1\t2\t3") == "\t"


def test_csv_crudo_y_header_detect(csv_con_preambulo):
    raw = read_file(csv_con_preambulo)
    assert raw.formato == FileFormat.CSV
    assert len(raw.sha256) == 64
    assert not raw.header_resolved

    det = detect_header(raw.grid)
    assert det.row_index == 3  # tras el preámbulo de 3 filas
    assert "Frequency [Hz]" in det.headers

    table = apply_header(raw.grid, det)
    assert len(table) == 3
    assert list(table.columns)[0] == "Date/Time"


def test_excel_reader(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "datos.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Configuracion"  # hoja a ignorar por heurística
    ws2 = wb.create_sheet("Trend Data")
    ws2.append(["Date/Time", "Frequency", "Active Power"])
    ws2.append(["2026-07-01 10:00:00", 60.0, 25.0])
    ws2.append(["2026-07-01 10:00:01", 60.01, 25.1])
    wb.save(path)

    raw = read_file(path)
    assert raw.formato == FileFormat.XLSX
    assert raw.hoja == "Trend Data"
    det = detect_header(raw.grid)
    assert det.row_index == 0


def test_formato_no_soportado(tmp_path):
    path = tmp_path / "algo.txt"
    path.write_text("x")
    with pytest.raises(ValueError, match="no soportado"):
        read_file(path)
