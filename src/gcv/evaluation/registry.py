"""Registro de implementaciones del motor de reglas.

Une la matriz normativa (TestSpec, datos) con las clases de prueba (código).
Una prueba puede existir en la matriz sin implementación (se reporta como tal)
pero no al revés: instanciar una implementación exige su TestSpec.
"""

from __future__ import annotations

from pathlib import Path

from gcv.evaluation.base import BaseTest
from gcv.evaluation.spec import TestSpec, load_matrix

# test_id → clase concreta. Se llena con register() al importar los módulos de pruebas.
_IMPLEMENTATIONS: dict[str, type[BaseTest]] = {}

DEFAULT_MATRIX_PATH = Path(__file__).resolve().parents[3] / "normative" / "matriz_pruebas.yaml"


def register(test_id: str):
    """Decorador: @register("CE-F-01") sobre una subclase de BaseTest."""

    def wrap(cls: type[BaseTest]) -> type[BaseTest]:
        if test_id in _IMPLEMENTATIONS:
            raise ValueError(f"Implementación duplicada para {test_id}")
        _IMPLEMENTATIONS[test_id] = cls
        return cls

    return wrap


def _load_builtin_implementations() -> None:
    """Importa los módulos de pruebas para poblar el registro."""
    import gcv.evaluation.frequency  # noqa: F401


def implemented_ids() -> list[str]:
    _load_builtin_implementations()
    return sorted(_IMPLEMENTATIONS)


def get_test(test_id: str, matrix: dict[str, TestSpec] | None = None) -> BaseTest:
    """Instancia la prueba `test_id` con su spec de la matriz."""
    _load_builtin_implementations()
    matrix = matrix if matrix is not None else load_matrix(DEFAULT_MATRIX_PATH)
    if test_id not in matrix:
        raise KeyError(f"'{test_id}' no existe en la matriz normativa")
    if test_id not in _IMPLEMENTATIONS:
        raise KeyError(
            f"'{test_id}' está en la matriz pero no tiene implementación. "
            f"Implementadas: {sorted(_IMPLEMENTATIONS)}")
    return _IMPLEMENTATIONS[test_id](matrix[test_id])
