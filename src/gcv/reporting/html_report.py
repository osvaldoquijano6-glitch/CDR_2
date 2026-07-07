"""Informe técnico HTML autocontenido (jinja2 + plotly embebido).

Un solo archivo: plotly.js se incrusta una vez y cada figura como fragmento.
Sirve como informe interactivo y como base del PDF (weasyprint, si está
disponible en el entorno de producción).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, BaseLoader

from gcv.reporting.context import ReportContext

_STATUS_CLASS = {
    "CUMPLE": "ok", "NO_CUMPLE": "fail",
    "NO_EVALUABLE": "warn", "PENDIENTE_DOCUMENTAL": "pend",
}

_TEMPLATE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Informe técnico — {{ ctx.proyecto }}</title>
<style>
 /* Identidad única del sistema (misma paleta que la app y las gráficas):
    tinta #1e2430 · marino #2a3f54 · primario #2a78d6 · superficie #f4f5f7 */
 :root{--ink:#1e2430;--ink-2:#5b6472;--navy:#2a3f54;--accent:#2a78d6;
   --surface:#f4f5f7;--card:#fff;--line:#e3e6ea;
   --ok-bg:#e4f4e4;--ok-fg:#0a5c0a;--fail-bg:#fbe7e7;--fail-fg:#8f1f1f;
   --warn-bg:#fdf2d8;--warn-fg:#7a5a00;--pend-bg:#ececec;--pend-fg:#4a4a4a}
 body{font-family:"Segoe UI",system-ui,Helvetica,Arial,sans-serif;color:var(--ink);
   margin:0;background:var(--surface)}
 .page{max-width:1080px;margin:0 auto;padding:28px 40px 40px;background:var(--card)}
 .banner{display:flex;align-items:center;gap:16px;
   background:linear-gradient(100deg,var(--navy) 0%,#33506e 55%,#3c6a99 100%);
   border-radius:14px;padding:18px 26px;margin-bottom:20px;color:#fff}
 .banner .t{font-size:22px;font-weight:700;margin:0}
 .banner .s{color:#c7d5e4;font-size:13px;margin-top:3px}
 h2{font-size:19px;color:var(--navy);margin-top:36px;
   border-bottom:2px solid var(--line);padding-bottom:6px}
 h3{font-size:16px;margin-top:24px;color:var(--navy)}
 table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0}
 th{background:var(--navy);color:#fff;text-align:left;padding:6px 8px}
 td{border-bottom:1px solid var(--line);padding:5px 8px;vertical-align:top}
 tr:nth-child(even) td{background:#fafbfc}
 .chip{display:inline-block;padding:4px 14px;border-radius:14px;font-weight:700;
   font-size:12px;letter-spacing:.02em;vertical-align:middle}
 .ok{background:var(--ok-bg);color:var(--ok-fg)}.fail{background:var(--fail-bg);color:var(--fail-fg)}
 .warn{background:var(--warn-bg);color:var(--warn-fg)}.pend{background:var(--pend-bg);color:var(--pend-fg)}
 .meta td:first-child{font-weight:600;width:220px;color:var(--ink-2)}
 .warns{background:var(--warn-bg);border-left:4px solid #eda100;padding:8px 12px;
   font-size:13px;margin:8px 0;border-radius:0 8px 8px 0}
 .small{font-size:12px;color:var(--ink-2)}
 .figure{margin:14px 0;border:1px solid var(--line);border-radius:12px;
   padding:6px;overflow:hidden}
</style></head><body><div class="page">

<div class="banner">
 <svg width="46" height="46" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" rx="11" fill="#1f3350"/>
  <path d="M6 30 L14 30 L18 16 L24 34 L28 22 L32 30 L42 30" fill="none"
   stroke="#5fa8ff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="24" cy="34" r="2.4" fill="#5fa8ff"/></svg>
 <div><p class="t">Informe técnico de verificación — Código de Red</p>
 <div class="s">Manual INTE · Manual CONE · POC/Anexo 5 — evaluación determinística y trazable</div></div>
</div>
<table class="meta">
 <tr><td>Proyecto</td><td>{{ ctx.proyecto }}</td></tr>
 <tr><td>Instalación</td><td>{{ ctx.installation.nombre }} ({{ ctx.installation.kind.value }})</td></tr>
 <tr><td>Clasificación</td><td>Categoría {{ ctx.installation.category.value if ctx.installation.category else "pendiente" }} ·
   {{ ctx.installation.tech.value if ctx.installation.tech else "—" }} ·
   Área {{ ctx.installation.area_sincrona.value if ctx.installation.area_sincrona else "—" }}</td></tr>
 <tr><td>Fecha de emisión</td><td>{{ ctx.fecha.strftime("%Y-%m-%d %H:%M") }}</td></tr>
 {% if ctx.responsable %}<tr><td>Responsable</td><td>{{ ctx.responsable }}</td></tr>{% endif %}
</table>

<h2>1. Objetivo</h2><p>{{ ctx.objetivo }}</p>
{% if ctx.alcance %}<h2>2. Alcance</h2><p>{{ ctx.alcance }}</p>{% endif %}
<h2>3. Metodología</h2><p>{{ ctx.metodologia }}</p>

<h2>4. Archivos analizados</h2>
<table><tr><th>Fuente</th><th>SHA-256</th><th>Filas</th><th>fs detectada</th><th>Inicio</th><th>Fin</th></tr>
{% for ds in ctx.datasets %}
 <tr><td>{{ ds.source_path }}</td><td class="small">{{ (ds.source_sha256 or "")[:16] }}…</td>
 <td>{{ ds.quality.n_filas }}</td>
 <td>{{ "%.4g Hz"|format(ds.quality.fs_detectada_hz) if ds.quality.fs_detectada_hz else "—" }}</td>
 <td>{{ ds.quality.inicio or "—" }}</td><td>{{ ds.quality.fin or "—" }}</td></tr>
{% endfor %}</table>

<h2>5. Resumen de resultados</h2>
<table><tr>{% for k, v in ctx.resumen.items() %}<th>{{ k.replace("_"," ") }}</th>{% endfor %}</tr>
<tr>{% for k, v in ctx.resumen.items() %}<td>{{ v }}</td>{% endfor %}</tr></table>

<h2>6. Resultados por prueba</h2>
{% for r in ctx.resultados %}
 <h3>{{ r.test_id }} — {{ r.test_name }}
   <span class="chip {{ status_class[r.status.value] }}">{{ r.status.value.replace("_"," ") }}</span></h3>
 <p class="small">Referencia normativa:
  {% for n in r.normative_reference %}{{ n.documento }} {{ n.numeral or "(numeral pendiente)" }}{{ "; " if not loop.last }}{% endfor %}
  {% if not r.normative_reference %}—{% endif %}
  · Estado del criterio: {{ r.estado_normativo }}</p>
 {% if objetivos.get(r.test_id) %}<p><b>Objetivo:</b> {{ objetivos[r.test_id] }}</p>{% endif %}

 {% for tit, b64 in figuras_norma.get(r.test_id, []) %}
 <div class="figure"><img src="data:image/png;base64,{{ b64 }}" style="max-width:100%">
 <p class="small" style="font-style:italic">{{ tit }} (referencia normativa)</p></div>
 {% endfor %}

 {% if r.pass_fail_details %}
 <table><tr><th>Criterio</th><th>Medido</th><th>Límite</th><th>Unidad</th><th>Cumple</th><th>Detalle</th></tr>
 {% for c in r.pass_fail_details %}
  <tr><td>{{ c.nombre }}</td><td>{{ c.valor_medido if c.valor_medido is not none else "—" }}</td>
  <td>{{ c.comparacion or "" }} {{ c.limite if c.limite is not none else "—" }}</td><td>{{ c.unidad or "" }}</td>
  <td>{{ {True:"SÍ", False:"NO"}.get(c.cumple, "NO EVALUABLE") }}</td><td>{{ c.detalle or "" }}</td></tr>
 {% endfor %}</table>
 {% endif %}

 {% if r.measured_values %}
 <table><tr><th>Variable medida</th><th>Valor</th><th>Unidad</th><th>Detalle</th></tr>
 {% for m in r.measured_values %}
  <tr><td>{{ m.nombre }}</td><td>{{ "%.6g"|format(m.valor) if m.valor is not none else "—" }}</td>
  <td>{{ m.unidad or "" }}</td><td>{{ m.detalle or "" }}</td></tr>
 {% endfor %}</table>
 {% endif %}

 {% for w in r.warnings %}<div class="warns">Advertencia: {{ w }}</div>{% endfor %}
 {% for fig_html in figuras.get(r.test_id, []) %}<div class="figure">{{ fig_html }}</div>{% endfor %}
 <p><b>Conclusión:</b> {{ conclusiones[r.test_id] }}</p>
{% endfor %}

<h2>7. Pendientes</h2>
{% if ctx.pendientes %}
<table><tr><th>ID</th><th>Prueba</th><th>Motivo</th></tr>
{% for r in ctx.pendientes %}
 <tr><td>{{ r.test_id }}</td><td>{{ r.test_name }}</td><td>{{ r.warnings|join("; ") or r.conclusion }}</td></tr>
{% endfor %}</table>
{% else %}<p>Sin pendientes.</p>{% endif %}

<h2>8. Trazabilidad y bitácora de procesamiento</h2>
<p class="small">Cada resultado enlaza el hash SHA-256 del archivo fuente, el mapeo de columnas
originales a señales canónicas y las transformaciones aplicadas.</p>
{% for ds in ctx.datasets %}
 <h3 class="small">{{ ds.source_path }}</h3>
 <table><tr><th>Columna original</th><th>Señal</th><th>Unidad orig.</th><th>Factor</th><th>Método</th></tr>
 {% for m in ds.mappings %}
  <tr><td>{{ m.columna_original }}</td><td>{{ m.senal_canonica }}</td>
  <td>{{ m.unidad_original or "—" }}</td><td>{{ m.factor_conversion }}</td><td>{{ m.metodo.value }}</td></tr>
 {% endfor %}</table>
 <table><tr><th>Momento (UTC)</th><th>Acción</th><th>Detalle</th><th>Filas</th></tr>
 {% for a in ds.log.acciones %}
  <tr><td class="small">{{ a.timestamp.strftime("%H:%M:%S") }}</td><td>{{ a.accion }}</td>
  <td>{{ a.detalle }}</td>
  <td>{{ a.filas_antes if a.filas_antes is not none else "" }}{{ "→" + a.filas_despues|string if a.filas_despues is not none else "" }}</td></tr>
 {% endfor %}</table>
{% endfor %}

<p class="small">Generado por gcv — sistema de verificación de Código de Red.
Los resultados NO EVALUABLE por criterio normativo pendiente no constituyen dictamen.</p>
</div></body></html>"""


def render_html(ctx: ReportContext) -> str:
    from gcv.reporting import plantillas

    from gcv.reporting.figuras_normativas import figura_b64, figuras_para

    nombre = ctx.installation.nombre
    tec = ctx.installation.tech.value if ctx.installation.tech else None
    tipo = ctx.installation.category.value if ctx.installation.category else None
    objetivos = {r.test_id: plantillas.objetivo(r.test_id, nombre) for r in ctx.resultados}
    conclusiones = {r.test_id: plantillas.conclusion(r, nombre) for r in ctx.resultados}
    figuras_norma = {r.test_id: [(t, figura_b64(p)) for t, p in
                                 figuras_para(r.test_id, tec, tipo)]
                     for r in ctx.resultados}
    figuras: dict[str, list[str]] = {}
    first = True
    for tid, figs in ctx.figuras.items():
        frags = []
        for fig in figs:
            frags.append(fig.to_html(
                full_html=False,
                include_plotlyjs="inline" if first else False,
                config={"displaylogo": False}))
            first = False
        figuras[tid] = frags
    env = Environment(loader=BaseLoader(), autoescape=False)
    return env.from_string(_TEMPLATE).render(
        ctx=ctx, figuras=figuras, status_class=_STATUS_CLASS,
        objetivos=objetivos, conclusiones=conclusiones,
        figuras_norma=figuras_norma)


def export_html(ctx: ReportContext, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(ctx), encoding="utf-8")
    return path


def export_pdf(ctx: ReportContext, path: Path) -> Path:
    """PDF vía weasyprint (requiere librerías del sistema; opcional)."""
    try:
        from weasyprint import HTML
    except Exception as exc:  # ImportError u OSError por libs del sistema
        raise RuntimeError(
            "weasyprint no disponible en este entorno; genera el HTML y "
            "conviértelo a PDF en el entorno de producción") from exc
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # sin plotly.js para el PDF (las gráficas interactivas no aplican en papel)
    figuras, ctx.figuras = ctx.figuras, {}
    try:
        HTML(string=render_html(ctx)).write_pdf(str(path))
    finally:
        ctx.figuras = figuras
    return path
