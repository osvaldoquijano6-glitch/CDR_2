"""Mapeo columna original → señal canónica y construcción del dataset normalizado.

Orquesta la capa de normalización completa:
    rejilla cruda → encabezado → mapeo (alias/manual) → unidades →
    timestamps → limpieza → NormalizedDataset (df canónico + calidad + bitácora)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from gcv.ingestion.base import RawDataset
from gcv.models import ChannelMapping, DataQualityReport, MappingMethod
from gcv.normalization import cleaning
from gcv.normalization.aliases import match_signal
from gcv.normalization.audit import CleaningLog
from gcv.normalization.cleaning import ManualCorrections
from gcv.normalization.header_detect import apply_header, detect_header
from gcv.normalization.sampling import analyze_sampling
from gcv.normalization.timestamps import combine_date_time, localize, parse_datetime_series
from gcv.normalization.units import convert_series, parse_unit, unit_from_header

_MODULO = "normalization.column_mapper"
TIME_COL = "timestamp"


@dataclass
class NormalizedDataset:
    """Salida de la capa de normalización; entrada de las capas de cálculo."""

    df: pd.DataFrame  # columnas canónicas, índice ordinal, columna 'timestamp'
    mappings: list[ChannelMapping]
    quality: DataQualityReport
    log: CleaningLog
    source_sha256: str | None = None
    source_path: str | None = None
    metadata: dict = field(default_factory=dict)

    def has_signals(self, señales: list[str]) -> list[str]:
        """Señales requeridas que faltan en el dataset (vacío = completo)."""
        return [s for s in señales if s not in self.df.columns]


def map_columns(
    headers: list[str],
    declared_units: dict[str, str] | None = None,
    manual_map: dict[str, str] | None = None,
) -> list[ChannelMapping]:
    """Genera mapeos columna→señal. Lo manual tiene precedencia sobre alias."""
    declared_units = declared_units or {}
    manual_map = manual_map or {}
    mappings: list[ChannelMapping] = []
    used: set[str] = set()

    for header in headers:
        if header in manual_map:
            signal = manual_map[header]
            metodo, confianza = MappingMethod.MANUAL, 1.0
        else:
            found = match_signal(header)
            if found is None or found.señal in used:
                continue
            signal, metodo, confianza = found.señal, MappingMethod.AUTO_ALIAS, found.score
        if signal in used:
            continue
        used.add(signal)

        unit_raw = declared_units.get(header) or unit_from_header(header)
        info = parse_unit(unit_raw)
        mappings.append(
            ChannelMapping(
                columna_original=header,
                senal_canonica=signal,
                unidad_original=unit_raw,
                unidad_canonica=info.canonica if info else None,
                factor_conversion=info.factor if info else 1.0,
                metodo=metodo,
                confianza=confianza,
            )
        )
    return mappings


def normalize(
    raw: RawDataset,
    manual_map: dict[str, str] | None = None,
    corrections: ManualCorrections | None = None,
    tz: str | None = None,
) -> NormalizedDataset:
    """Pipeline completo de normalización de un RawDataset."""
    corrections = corrections or ManualCorrections()
    log = CleaningLog(fuente=str(raw.source_path))

    # 1. Encabezado
    if raw.header_resolved:
        table = raw.grid.copy()
        log.add(_MODULO, "encabezado", "Encabezados resueltos por el formato de origen (COMTRADE)")
    else:
        detection = detect_header(raw.grid)
        table = apply_header(raw.grid, detection)
        log.add(_MODULO, "encabezado",
                f"Encabezado detectado en fila {detection.row_index} (score {detection.score})",
                fila=detection.row_index, score=detection.score)
        if detection.score < 0.5:
            log.add(_MODULO, "advertencia",
                    "Confianza baja en la detección de encabezado: requiere confirmación del usuario")

    if corrections.rename_columns:
        table = cleaning.apply_manual_corrections(
            table, ManualCorrections(rename_columns=corrections.rename_columns,
                                     motivo=corrections.motivo),
            TIME_COL, log)

    headers = [str(c) for c in table.columns]

    # 2. Mapeo de columnas
    declared_units = dict(raw.units)
    for col, unit in corrections.force_units.items():
        declared_units[col] = unit
        log.add(_MODULO, "unidad_forzada", f"Unidad de '{col}' forzada a '{unit}'",
                columna=col, unidad=unit, motivo=corrections.motivo)
    mappings = map_columns(headers, declared_units=declared_units, manual_map=manual_map)
    if not mappings:
        raise ValueError(f"Ninguna columna reconocida en {raw.source_path}. Encabezados: {headers}")

    # 3. Eje temporal
    by_signal = {m.senal_canonica: m for m in mappings}
    if TIME_COL in table.columns and pd.api.types.is_datetime64_any_dtype(table[TIME_COL]):
        times, report = parse_datetime_series(table[TIME_COL])
    elif "timestamp" in by_signal:
        times, report = parse_datetime_series(
            table[by_signal["timestamp"].columna_original], dayfirst=corrections.dayfirst)
    elif "date" in by_signal and "time_of_day" in by_signal:
        times, report = combine_date_time(
            table[by_signal["date"].columna_original],
            table[by_signal["time_of_day"].columna_original],
            dayfirst=corrections.dayfirst)
        log.add(_MODULO, "fecha_hora_combinadas",
                f"Columnas '{by_signal['date'].columna_original}' + "
                f"'{by_signal['time_of_day'].columna_original}' combinadas en timestamp")
    else:
        raise ValueError(
            "No se encontró columna de tiempo (timestamp, o fecha+hora). "
            f"Mapeos: {[m.senal_canonica for m in mappings]}")
    log.add(_MODULO, "parse_timestamps",
            f"Estrategia '{report.estrategia}', {report.n_validos}/{report.n_total} válidos, "
            f"confianza {report.confianza}",
            estrategia=report.estrategia, confianza=report.confianza,
            ambiguo_dia_mes=report.ambiguo_dia_mes)
    if report.ambiguo_dia_mes:
        log.add(_MODULO, "advertencia",
                "Formato de fecha ambiguo día/mes: se eligió por monotonía; "
                "declarar 'dayfirst' en correcciones para fijarlo")

    tz_effective = tz or corrections.tz
    times = localize(times, tz_effective)
    log.add(_MODULO, "zona_horaria",
            f"Zona horaria: {tz_effective or 'naive (sin declarar)'}", tz=tz_effective)

    # 4. Construir DF canónico y convertir unidades
    signal_mappings = [m for m in mappings
                       if m.senal_canonica not in ("timestamp", "date", "time_of_day")]
    out = pd.DataFrame({TIME_COL: times.values})
    for m in signal_mappings:
        series = pd.to_numeric(
            table[m.columna_original].astype(str).str.replace(",", ".", regex=False),
            errors="coerce")
        if m.factor_conversion != 1.0:
            series = convert_series(series, parse_unit(m.unidad_original))  # type: ignore[arg-type]
            log.add(_MODULO, "conversion_unidad",
                    f"'{m.columna_original}' ({m.unidad_original}) → "
                    f"{m.senal_canonica} [{m.unidad_canonica}] ×{m.factor_conversion}",
                    columna=m.columna_original, factor=m.factor_conversion)
        out[m.senal_canonica] = series.values

    # 5. Limpieza estándar (todo con bitácora)
    value_cols = [m.senal_canonica for m in signal_mappings]
    out = cleaning.drop_invalid_time(out, TIME_COL, log)
    out = cleaning.sort_by_time(out, TIME_COL, log)
    out = cleaning.dedup_timestamps(out, TIME_COL, log)
    if corrections.drop_time_ranges:
        out = cleaning.apply_manual_corrections(
            out, ManualCorrections(drop_time_ranges=corrections.drop_time_ranges,
                                   motivo=corrections.motivo),
            TIME_COL, log)
    outlier_counts = cleaning.mark_outliers(out, value_cols, log)

    # 6. Calidad
    quality = analyze_sampling(out, TIME_COL)
    quality.outliers_por_columna = outlier_counts

    return NormalizedDataset(
        df=out,
        mappings=mappings,
        quality=quality,
        log=log,
        source_sha256=raw.sha256,
        source_path=str(raw.source_path),
        metadata=dict(raw.metadata),
    )
