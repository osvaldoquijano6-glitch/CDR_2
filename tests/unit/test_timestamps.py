import pandas as pd

from gcv.normalization.timestamps import combine_date_time, normalize_ampm, parse_datetime_series


def test_ampm_espanol():
    assert normalize_ampm("01/02/2026 03:15:00.000 p. m.").endswith("PM")
    parsed, report = parse_datetime_series(
        pd.Series(["01/02/2026 03:15:00.000 p. m.", "01/02/2026 03:15:01.000 p. m."]))
    assert report.estrategia == "ampm"
    assert parsed.iloc[0].hour == 15


def test_desambiguacion_dia_mes_por_monotonia():
    # 13/01 solo es válido day-first: la serie cruza el mediodía del día 13
    serie = pd.Series([
        "13/01/2026 10:00:00", "13/01/2026 10:00:01", "13/01/2026 10:00:02",
    ])
    parsed, report = parse_datetime_series(serie)
    assert report.estrategia == "dayfirst"
    assert parsed.iloc[0].day == 13


def test_ambiguedad_reportada():
    # 01..05 de febrero vs 1 de cada mes: ambas interpretaciones parsean
    serie = pd.Series([f"0{d}/02/2026 12:00:00" for d in range(1, 6)])
    parsed, report = parse_datetime_series(serie)
    assert report.ambiguo_dia_mes is True
    assert report.confianza < 1.0
    # day-first produce paso de 1 día (mediana menor) → debe ganar
    assert report.estrategia == "dayfirst"


def test_dayfirst_declarado_gana():
    serie = pd.Series(["03/04/2026 00:00:00", "03/04/2026 00:00:01"])
    _, r_day = parse_datetime_series(serie, dayfirst=True)
    _, r_month = parse_datetime_series(serie, dayfirst=False)
    assert r_day.estrategia == "dayfirst"
    assert r_month.estrategia == "monthfirst"
    assert r_day.confianza == 1.0


def test_epoch_unix():
    serie = pd.Series([1767225600, 1767225601, 1767225602])
    parsed, report = parse_datetime_series(serie)
    assert report.estrategia == "epoch"
    assert parsed.iloc[0].year == 2026


def test_iso():
    serie = pd.Series(["2026-07-01 10:00:00", "2026-07-01 10:00:01"])
    _, report = parse_datetime_series(serie)
    assert report.estrategia == "iso"


def test_combinar_fecha_y_hora_separadas():
    fecha = pd.Series(["2026-07-01", "2026-07-01"])
    hora = pd.Series(["10:00:00", "10:00:01"])
    parsed, _ = combine_date_time(fecha, hora)
    assert parsed.iloc[1].second == 1
