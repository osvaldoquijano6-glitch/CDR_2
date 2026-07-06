"""gcv — Sistema de verificación de pruebas de Código de Red.

Capas (ver docs/FASE1_ARQUITECTURA.md §4):
    normative/ (datos)  →  config  →  ingestion  →  normalization
    →  signal_processing / quality_power  →  evaluation  →  visualization / reporting

Regla de dependencia central: solo `evaluation` compara contra límites
normativos; `ml` nunca participa en un veredicto.
"""

__version__ = "1.0.0"
