"""Repositorio histórico de gráficas por central.

Cada corrida guarda sus figuras en `projects/<central>/graficas/`:
  * un `.html` autocontenible por figura (abrible con doble clic meses después;
    plotly.js se escribe UNA vez por carpeta como plotly.min.js),
  * un `.json` ligero por figura (para previsualizar dentro de la app),
  * un `indice.json` acumulativo con fecha, prueba, resultado y archivos.

Nombres trazables: <CENTRAL>_<PRUEBA>_<AAAAmmdd_HHMMSS>_<n>.html
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

from gcv.config.settings import PROJECTS_DIR


def _slug(nombre: str) -> str:
    text = unicodedata.normalize("NFKD", str(nombre))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return (text or "central").upper()


def carpeta_graficas(central: str, base: Path | None = None) -> Path:
    return Path(base or PROJECTS_DIR) / _slug(central) / "graficas"


def guardar_figuras(
    central: str,
    test_id: str,
    figs: list[go.Figure],
    resultado: str | None = None,
    base: Path | None = None,
) -> list[Path]:
    """Persiste las figuras de una corrida y actualiza el índice."""
    carpeta = carpeta_graficas(central, base)
    carpeta.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slug(central)
    indice_path = carpeta / "indice.json"
    indice = json.loads(indice_path.read_text(encoding="utf-8")) if indice_path.exists() else []

    rutas: list[Path] = []
    for n, fig in enumerate(figs, start=1):
        nombre = f"{slug}_{test_id}_{stamp}_{n}"
        html_path = carpeta / f"{nombre}.html"
        # plotly.min.js una sola vez por carpeta; cada html lo referencia
        fig.write_html(str(html_path), include_plotlyjs="directory",
                       config={"displaylogo": False})
        (carpeta / f"{nombre}.json").write_text(pio.to_json(fig), encoding="utf-8")
        indice.append({
            "archivo": html_path.name,
            "json": f"{nombre}.json",
            "prueba": test_id,
            "resultado": resultado,
            "fecha": stamp,
            "titulo": (fig.layout.title.text or test_id) if fig.layout.title else test_id,
        })
        rutas.append(html_path)

    indice_path.write_text(json.dumps(indice, indent=2, ensure_ascii=False), encoding="utf-8")
    return rutas


def listar_centrales(base: Path | None = None) -> list[str]:
    raiz = Path(base or PROJECTS_DIR)
    if not raiz.exists():
        return []
    return sorted(p.parent.parent.name for p in raiz.glob("*/graficas/indice.json"))


def listar_graficas(central: str, base: Path | None = None) -> list[dict]:
    """Entradas del índice (más recientes primero), con ruta absoluta."""
    carpeta = carpeta_graficas(central, base)
    indice_path = carpeta / "indice.json"
    if not indice_path.exists():
        return []
    entradas = json.loads(indice_path.read_text(encoding="utf-8"))
    for e in entradas:
        e["ruta"] = str(carpeta / e["archivo"])
        e["ruta_json"] = str(carpeta / e["json"]) if e.get("json") else None
    return sorted(entradas, key=lambda e: e["fecha"], reverse=True)


def cargar_figura(ruta_json: str) -> go.Figure:
    return pio.from_json(Path(ruta_json).read_text(encoding="utf-8"))
