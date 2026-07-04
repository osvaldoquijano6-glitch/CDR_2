#!/usr/bin/env bash
# Arranca el borrador de interfaz Streamlit (FASE 4).
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/src"
exec streamlit run src/gcv/app/streamlit_app.py "$@"
