"""Persistencia de proyectos: guardar y reabrir una corrida completa.

Un proyecto se guarda en `projects/<slug>/` con:
    proyecto.json     — instalación, responsable, fecha, parámetros y resultados
    datos/<i>.csv     — cada dataset normalizado (df canónico) para re-ejecutar
    figuras/<id>_<n>.json — figuras Plotly ya construidas (previsualizables)

Reabrir reconstruye instalación, resultados y figuras sin volver a cargar datos,
de modo que las pestañas Resultados y Reportes quedan operativas al instante; el
df canónico persiste aparte para poder re-ejecutar si se desea.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from gcv.config.settings import PROJECTS_DIR
from gcv.evaluation.result import TestResult
from gcv.models import ChannelMapping, DataQualityReport, Installation
from gcv.normalization.audit import CleaningLog
from gcv.normalization.column_mapper import NormalizedDataset

SCHEMA = "gcv-proyecto/2"


def slugify(nombre: str) -> str:
    text = unicodedata.normalize("NFKD", nombre.upper())
    text = "".join(c for c in text if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() or c in " -_" else " " for c in text)
    return re.sub(r"\s+", "_", s.strip())[:60] or "PROYECTO"


def _dataset_to_dict(ds: NormalizedDataset) -> dict:
    return {
        "source_path": ds.source_path,
        "source_sha256": ds.source_sha256,
        "mappings": [m.model_dump(mode="json") for m in ds.mappings],
        "quality": ds.quality.model_dump(mode="json"),
        "log": ds.log.model_dump(mode="json"),
        "metadata": ds.metadata,
    }


def _dataset_from_dict(d: dict, df: pd.DataFrame) -> NormalizedDataset:
    return NormalizedDataset(
        df=df,
        mappings=[ChannelMapping.model_validate(m) for m in d["mappings"]],
        quality=DataQualityReport.model_validate(d["quality"]),
        log=CleaningLog.model_validate(d["log"]),
        source_sha256=d.get("source_sha256"),
        source_path=d.get("source_path"),
        metadata=d.get("metadata", {}),
    )


def guardar_proyecto(
    installation: Installation,
    resultados: list[TestResult],
    datasets: list[NormalizedDataset],
    figuras: dict[str, list[go.Figure]] | None = None,
    result_ds_index: dict[str, int] | None = None,
    responsable: str | None = None,
    base: Path | None = None,
) -> Path:
    """Escribe el proyecto y devuelve su carpeta. Reemplaza una corrida previa."""
    base = Path(base) if base else PROJECTS_DIR
    carpeta = base / slugify(installation.nombre)
    (carpeta / "datos").mkdir(parents=True, exist_ok=True)
    (carpeta / "figuras").mkdir(parents=True, exist_ok=True)

    for i, ds in enumerate(datasets):
        ds.df.to_csv(carpeta / "datos" / f"{i}.csv", index=False)

    figuras = figuras or {}
    fig_index: dict[str, list[str]] = {}
    for tid, figs in figuras.items():
        nombres = []
        for n, fig in enumerate(figs):
            nombre = f"{tid}_{n}.json"
            (carpeta / "figuras" / nombre).write_text(pio.to_json(fig), encoding="utf-8")
            nombres.append(nombre)
        fig_index[tid] = nombres

    doc = {
        "schema": SCHEMA,
        "guardado": datetime.now().isoformat(timespec="seconds"),
        "responsable": responsable,
        "installation": installation.model_dump(mode="json"),
        "datasets": [_dataset_to_dict(ds) for ds in datasets],
        "resultados": [r.model_dump(mode="json") for r in resultados],
        "result_ds_index": result_ds_index or {},
        "figuras": fig_index,
    }
    (carpeta / "proyecto.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return carpeta


class ProyectoCargado:
    """Resultado de reabrir un proyecto guardado."""

    def __init__(self, doc: dict, carpeta: Path):
        self.carpeta = carpeta
        self.guardado = doc.get("guardado")
        self.responsable = doc.get("responsable")
        self.installation = Installation.model_validate(doc["installation"])
        self.resultados = [TestResult.model_validate(r) for r in doc["resultados"]]
        self.result_ds_index: dict[str, int] = doc.get("result_ds_index", {})
        self.datasets: list[NormalizedDataset] = []
        for i, dd in enumerate(doc.get("datasets", [])):
            csv = carpeta / "datos" / f"{i}.csv"
            df = pd.read_csv(csv) if csv.exists() else pd.DataFrame()
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            self.datasets.append(_dataset_from_dict(dd, df))
        self.figuras: dict[str, list[go.Figure]] = {}
        for tid, nombres in doc.get("figuras", {}).items():
            figs = []
            for nombre in nombres:
                ruta = carpeta / "figuras" / nombre
                if ruta.exists():
                    figs.append(pio.from_json(ruta.read_text(encoding="utf-8")))
            self.figuras[tid] = figs


def cargar_proyecto(carpeta: Path) -> ProyectoCargado:
    carpeta = Path(carpeta)
    doc = json.loads((carpeta / "proyecto.json").read_text(encoding="utf-8"))
    return ProyectoCargado(doc, carpeta)


def listar_proyectos(base: Path | None = None) -> list[dict]:
    """[{slug, nombre, guardado, n_resultados}] de proyectos guardados (schema v2)."""
    base = Path(base) if base else PROJECTS_DIR
    if not base.exists():
        return []
    out = []
    for carpeta in sorted(base.iterdir()):
        pj = carpeta / "proyecto.json"
        if not pj.is_file():
            continue
        try:
            doc = json.loads(pj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if doc.get("schema") != SCHEMA:
            continue  # ignora proyectos del formato legado
        out.append({
            "slug": carpeta.name,
            "nombre": doc.get("installation", {}).get("nombre", carpeta.name),
            "guardado": doc.get("guardado"),
            "n_resultados": len(doc.get("resultados", [])),
        })
    return out
