#!/bin/zsh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Creando entorno virtual en .venv..."
  python3 -m venv "$VENV_DIR"
fi

if [ ! -x "$VENV_PYTHON" ]; then
  echo "No fue posible preparar Python en $VENV_DIR"
  exit 1
fi

if ! "$VENV_PYTHON" -c "import streamlit, pandas, numpy, matplotlib, openpyxl, pyarrow, plotly" >/dev/null 2>&1; then
  echo "Instalando dependencias del proyecto..."
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"
fi

export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

exec "$VENV_PYTHON" "$SCRIPT_DIR/app.py" "$@"
