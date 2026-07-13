"""Informe PDF directo: imprime el informe HTML con Chromium headless.

Orden de resolución del motor de impresión:
1. Chromium/Chrome del sistema (variable GCV_CHROMIUM, rutas conocidas o PATH);
2. weasyprint, si está instalado con sus librerías de sistema.

El HTML autocontenido (plotly inline) se imprime con presupuesto de tiempo
virtual para que las gráficas terminen de renderear antes de la captura.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from gcv.reporting.context import ReportContext
from gcv.reporting.html_report import render_html

_CANDIDATOS = (
    os.environ.get("GCV_CHROMIUM", ""),
    "/opt/pw-browsers/chromium",
    "chromium",
    "chromium-browser",
    "google-chrome",
    "chrome",
)


def _chromium() -> str | None:
    for cand in _CANDIDATOS:
        if not cand:
            continue
        if os.path.sep in cand and Path(cand).exists():
            return cand
        found = shutil.which(cand)
        if found:
            return found
    return None


def _via_chromium(html: str, path: Path, timeout_s: int = 120) -> bool:
    exe = _chromium()
    if exe is None:
        return False
    with tempfile.TemporaryDirectory(prefix="gcv_pdf_") as tmp:
        src = Path(tmp) / "informe.html"
        src.write_text(html, encoding="utf-8")
        cmd = [
            exe, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--no-first-run", "--disable-dev-shm-usage",
            "--virtual-time-budget=15000", "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={path}", "--no-pdf-header-footer",
            src.resolve().as_uri(),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=timeout_s)
        except (subprocess.TimeoutExpired, OSError):
            return False
    return res.returncode == 0 and path.exists() and path.stat().st_size > 1000


def _via_weasyprint(html: str, path: Path) -> bool:
    try:
        from weasyprint import HTML  # noqa: PLC0415
    except Exception:
        return False
    try:
        HTML(string=html).write_pdf(str(path))
    except Exception:
        return False
    return path.exists() and path.stat().st_size > 1000


def export_pdf(ctx: ReportContext, path: Path) -> Path:
    """Genera el informe técnico en PDF. RuntimeError si no hay motor disponible."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(ctx)
    if _via_chromium(html, path) or _via_weasyprint(html, path):
        return path
    raise RuntimeError(
        "Sin motor de impresión PDF: instale Chromium/Chrome (o defina "
        "GCV_CHROMIUM con la ruta al ejecutable) o weasyprint. "
        "El informe HTML queda disponible como alternativa.")


def pdf_disponible() -> bool:
    """True si hay un motor con el que export_pdf puede funcionar."""
    if _chromium() is not None:
        return True
    try:
        import weasyprint  # noqa: F401,PLC0415
        return True
    except Exception:
        return False
