"""Round-trip de persistencia de proyectos."""

import pandas as pd

from gcv.evaluation.frequency.rango_frecuencia import RangoFrecuencia
from gcv.models import Category, Installation, InstallationKind, SyncArea, Technology
from gcv.persistence import (
    cargar_proyecto, guardar_proyecto, listar_proyectos, slugify)
from gcv.visualization.evidence import build_figures

from tests.unit.helpers import make_dataset, make_spec, ts


def _corrida():
    df = pd.DataFrame({"timestamp": ts(40), "frequency": [60.0] * 40,
                       "active_power": [80.0] * 40})
    ds = make_dataset(df)
    spec = make_spec("CE-F-01", ["timestamp", "frequency", "active_power"],
                     limites={"bandas": [{"f_min": 59.5, "f_max": 61.0, "t_min_s": 10}]})
    r = RangoFrecuencia(spec).run(ds)
    return ds, r


def test_slugify():
    assert slugify("Central Fotovoltaica Niña") == "CENTRAL_FOTOVOLTAICA_NINA"
    assert slugify("  ") == "PROYECTO"


def test_guardar_y_cargar(tmp_path):
    ds, r = _corrida()
    inst = Installation(nombre="Central Demo Norte", kind=InstallationKind.CENTRAL_ELECTRICA,
                        tech=Technology.ASINCRONA, category=Category.C,
                        area_sincrona=SyncArea.SIN, capacidad_instalada_neta_mw=25.0)
    figs = {r.test_id: build_figures(r, ds)}
    carpeta = guardar_proyecto(inst, [r], [ds], figuras=figs,
                               result_ds_index={r.test_id: 0},
                               responsable="Ing. X", base=tmp_path)
    assert (carpeta / "proyecto.json").exists()
    assert (carpeta / "datos" / "0.csv").exists()

    pj = cargar_proyecto(carpeta)
    assert pj.installation.nombre == "Central Demo Norte"
    assert pj.installation.category == Category.C
    assert pj.responsable == "Ing. X"
    assert len(pj.resultados) == 1
    assert pj.resultados[0].test_id == "CE-F-01"
    assert pj.resultados[0].status == r.status
    assert pj.result_ds_index == {"CE-F-01": 0}
    # dataset re-hidratado con df para re-ejecutar
    assert len(pj.datasets) == 1 and not pj.datasets[0].df.empty
    assert "frequency" in pj.datasets[0].df.columns
    # figuras previsualizables
    assert pj.figuras["CE-F-01"] and pj.figuras["CE-F-01"][0].data


def test_listar_proyectos(tmp_path):
    ds, r = _corrida()
    inst = Installation(nombre="Central A", kind=InstallationKind.CENTRAL_ELECTRICA,
                        tech=Technology.ASINCRONA, category=Category.B)
    guardar_proyecto(inst, [r], [ds], base=tmp_path)
    lista = listar_proyectos(base=tmp_path)
    assert len(lista) == 1
    assert lista[0]["nombre"] == "Central A"
    assert lista[0]["n_resultados"] == 1


def test_listar_ignora_formato_legado(tmp_path):
    # una carpeta con metadata.json del formato viejo no debe aparecer
    (tmp_path / "VIEJO").mkdir()
    (tmp_path / "VIEJO" / "proyecto.json").write_text('{"schema": "otro"}')
    assert listar_proyectos(base=tmp_path) == []
