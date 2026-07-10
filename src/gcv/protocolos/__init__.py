"""Generación de protocolos de pruebas fiel a las plantillas del usuario.

El documento final ES la plantilla del usuario (portada, encabezados, estilos,
tablas): solo se sustituyen los datos del proyecto y se reconstruye el capítulo
de pruebas desde el catálogo YAML según las pruebas seleccionadas.
"""

from gcv.protocolos.builder import ProyectoProtocolo, generar_protocolo
from gcv.protocolos.checklist import generar_checklist, universo_pruebas
from gcv.protocolos.diseno_v2 import generar_protocolo_v2
from gcv.protocolos.revisiones import generar_revisiones

__all__ = ["ProyectoProtocolo", "generar_protocolo", "generar_protocolo_v2",
           "generar_checklist", "universo_pruebas", "generar_revisiones"]
