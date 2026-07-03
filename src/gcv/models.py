"""Entidades compartidas del dominio (docs/FASE1_ARQUITECTURA.md §5).

Todo modelo que cruza fronteras de capa vive aquí; los modelos internos de una
capa (p. ej. TestSpec, TestResult) viven en su capa.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Clasificación de la instalación ─────────────────────────────────────────
class InstallationKind(str, enum.Enum):
    CENTRAL_ELECTRICA = "CENTRAL_ELECTRICA"
    CENTRO_DE_CARGA = "CENTRO_DE_CARGA"


class Technology(str, enum.Enum):
    SINCRONA = "SINCRONA"
    ASINCRONA = "ASINCRONA"
    MIXTA = "MIXTA"


class Category(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class SyncArea(str, enum.Enum):
    """Áreas síncronas consideradas por el Manual INTER."""

    SIN = "SIN"
    BCA = "BCA"
    BCS = "BCS"
    MULEGE = "MULEGE"


class Installation(BaseModel):
    """Instalación bajo verificación."""

    nombre: str
    kind: InstallationKind
    tech: Technology | None = None  # solo Centrales Eléctricas
    category: Category | None = None  # A/B/C/D; su asignación requiere numeral validado
    area_sincrona: SyncArea | None = None
    capacidad_instalada_neta_mw: float | None = None
    tension_poi_kv: float | None = None
    f_nominal_hz: float = 60.0
    punto_interconexion: str | None = None


# ─── Referencias normativas ──────────────────────────────────────────────────
class NormRef(BaseModel):
    """Cita documental exacta. Un veredicto sin NormRef no es defendible."""

    documento: str  # p. ej. "Manual INTER"
    numeral: str | None = None
    version: str | None = None  # versión / fecha DOF


# ─── Mapeo de canales (trazabilidad columna → señal) ─────────────────────────
class MappingMethod(str, enum.Enum):
    AUTO_ALIAS = "AUTO_ALIAS"  # diccionario determinístico de alias
    AUTO_ML_SUGERIDO = "AUTO_ML_SUGERIDO"  # sugerido por ML, confirmado por usuario
    MANUAL = "MANUAL"  # asignado por el usuario


class ChannelMapping(BaseModel):
    """Traza una columna del archivo original a una señal canónica."""

    columna_original: str
    senal_canonica: str
    unidad_original: str | None = None
    unidad_canonica: str | None = None
    factor_conversion: float = 1.0
    metodo: MappingMethod = MappingMethod.AUTO_ALIAS
    confianza: float = 1.0  # 0..1; <1 exige confirmación en UI


# ─── Calidad de datos ────────────────────────────────────────────────────────
class GapInfo(BaseModel):
    inicio: datetime
    fin: datetime
    duracion_s: float
    muestras_faltantes_estimadas: int


class DataQualityReport(BaseModel):
    """Resultado del análisis de muestreo/calidad (normalization.sampling)."""

    n_filas: int = 0
    fs_detectada_hz: float | None = None
    periodo_mediano_s: float | None = None
    inicio: datetime | None = None
    fin: datetime | None = None
    duracion_s: float | None = None
    timestamps_duplicados: int = 0
    saltos_no_monotonicos: int = 0
    huecos: list[GapInfo] = Field(default_factory=list)
    nan_por_columna: dict[str, int] = Field(default_factory=dict)
    outliers_por_columna: dict[str, int] = Field(default_factory=dict)

    @property
    def es_regular(self) -> bool:
        return not self.huecos and self.saltos_no_monotonicos == 0
