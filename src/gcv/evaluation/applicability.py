"""Determinación de pruebas aplicables a una instalación.

Filtra la matriz normativa por tipo de instalación, categoría A/B/C/D y
tecnología. Cuando la matriz aún no define aplicabilidad (categorías vacías),
la prueba se incluye marcada como dudosa para que el usuario decida — nunca se
excluye en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass

from gcv.evaluation.spec import TestSpec
from gcv.models import Installation, InstallationKind, Technology


@dataclass(frozen=True)
class ApplicabilityDecision:
    spec: TestSpec
    aplica: bool
    dudosa: bool  # True si la matriz no tiene datos para decidir
    razon: str


def decide(spec: TestSpec, inst: Installation) -> ApplicabilityDecision:
    if spec.aplica_a != inst.kind:
        return ApplicabilityDecision(spec, False, False,
                                     f"Prueba de {spec.aplica_a.value}, instalación {inst.kind.value}")

    if inst.kind == InstallationKind.CENTRO_DE_CARGA:
        return ApplicabilityDecision(spec, True, False, "Prueba de Centro de Carga")

    # Central Eléctrica: categoría
    if not spec.categorias:
        return ApplicabilityDecision(spec, True, True,
                                     "Aplicabilidad por categoría pendiente en la matriz")
    if inst.category is None:
        return ApplicabilityDecision(spec, True, True,
                                     "Instalación sin categoría asignada")
    if inst.category.value not in spec.categorias:
        return ApplicabilityDecision(spec, False, False,
                                     f"Categoría {inst.category.value} fuera de {spec.categorias}")

    # Tecnología
    tec = (spec.tecnologia or "AMBAS").upper()
    if tec not in ("AMBAS", "") and inst.tech is not None and inst.tech != Technology.MIXTA:
        if inst.tech.value != tec:
            return ApplicabilityDecision(spec, False, False,
                                         f"Tecnología {inst.tech.value} ≠ {tec}")
    return ApplicabilityDecision(spec, True, False, "Aplica por categoría y tecnología")


def applicable_tests(matrix: dict[str, TestSpec], inst: Installation) -> list[ApplicabilityDecision]:
    """Decisión por prueba, en el orden de la matriz. Incluye no-aplicables con razón."""
    return [decide(spec, inst) for spec in matrix.values()]
