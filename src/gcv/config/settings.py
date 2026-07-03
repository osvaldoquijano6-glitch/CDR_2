"""Rutas y configuración del sistema."""

from __future__ import annotations

from pathlib import Path

# Raíz del repositorio (src/gcv/config/settings.py → 3 niveles arriba)
REPO_ROOT = Path(__file__).resolve().parents[3]
NORMATIVE_DIR = REPO_ROOT / "normative"
MATRIX_PATH = NORMATIVE_DIR / "matriz_pruebas.yaml"
PROJECTS_DIR = REPO_ROOT / "projects"
