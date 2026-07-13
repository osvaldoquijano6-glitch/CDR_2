from gcv.normalization.aliases import match_signal, normalize_header


def test_normalize_header_quita_acentos_y_unidades():
    assert normalize_header("Potencia Activa [kW]") == "potencia activa"
    assert normalize_header("Tensión (kV)") == "tension"


def test_alias_exactos():
    assert match_signal("Frequency").señal == "frequency"
    assert match_signal("f").señal == "frequency"
    assert match_signal("Hz").señal == "frequency"
    assert match_signal("Vab").señal == "voltage_ab"
    assert match_signal("MVAr").señal == "reactive_power"
    assert match_signal("Power Factor").señal == "power_factor"
    assert match_signal("Pst").señal == "pst"


def test_grupo_tokens_encabezados_largos():
    m = match_signal("POI Active Power Total [MW]")
    assert m.señal == "active_power"
    assert m.metodo == "grupo_tokens"
    assert match_signal("Frecuencia del sistema").señal == "frequency"
    assert match_signal("THD Voltage L1").señal == "thd_voltage"


def test_armonicos_numerados():
    m = match_signal("H5 Voltage")
    assert m.señal == "harmonic_voltage_5"


def test_sin_match_devuelve_none():
    assert match_signal("Comentarios del operador") is None
    assert match_signal("") is None
