"""Contratos aditivos del diferencial: estadística, escenarios, mapa de fuentes y exactitud."""

import pytest
from pydantic import ValidationError

from posiq.domain.accuracy_schemas import (
    AccionMitigacion,
    Afirmacion,
    HallazgoExactitud,
    Verificacion,
)
from posiq.domain.scenario_schemas import AccionAplazada, EntradaEscenario, EscenarioPlan
from posiq.domain.source_map_schemas import FuenteSector, MapaFuentes, OportunidadFuente
from posiq.domain.stats_schemas import Intervalo, Significancia


def _intervalo(valor: float = 0.3, inf: float = 0.2, sup: float = 0.4) -> Intervalo:
    return Intervalo(valor=valor, inf=inf, sup=sup, n=240, metodo="wilson")


# --- estadística -------------------------------------------------------------------------------


def test_intervalo_ordenado_y_margen() -> None:
    i = _intervalo(0.3, 0.25, 0.4)
    assert i.nivel == 0.95
    assert i.margen == pytest.approx(0.1)


def test_intervalo_desordenado_falla() -> None:
    with pytest.raises(ValidationError):
        _intervalo(0.5, 0.2, 0.4)


@pytest.mark.parametrize(("inf", "sup", "significativa"), [(0.01, 0.09, True), (-0.02, 0.1, False)])
def test_significancia_coherente_con_el_intervalo(
    inf: float, sup: float, significativa: bool
) -> None:
    s = Significancia(
        delta=0.05,
        intervalo=Intervalo(valor=0.05, inf=inf, sup=sup, n=100, metodo="diferencia_proporciones"),
        significativa=significativa,
    )
    assert s.significativa is significativa


def test_significancia_incoherente_falla() -> None:
    with pytest.raises(ValidationError):
        Significancia(
            delta=0.05,
            intervalo=Intervalo(valor=0.05, inf=-0.02, sup=0.1, n=100, metodo="bootstrap"),
            significativa=True,
        )


# --- escenarios --------------------------------------------------------------------------------


def test_entrada_por_defecto_no_inventa_costes() -> None:
    e = EntradaEscenario()
    assert e.acciones_activas is None
    assert e.presupuesto_eur is None
    assert e.costes_declarados == {}


def test_entrada_con_coste_negativo_falla() -> None:
    with pytest.raises(ValidationError):
        EntradaEscenario(costes_declarados={"A1": -10.0})


def test_escenario_mantenida_y_aplazada_a_la_vez_falla() -> None:
    with pytest.raises(ValidationError):
        EscenarioPlan(
            nombre="personalizado",
            entrada=EntradaEscenario(),
            mantenidas=["A1"],
            aplazadas=[AccionAplazada(action_id="A1", motivo="capacidad", detalle="x")],
            hallazgos_sin_cubrir=[],
            esfuerzo_total=1,
        )


def test_escenario_valido() -> None:
    e = EscenarioPlan(
        nombre="minimo_viable",
        entrada=EntradaEscenario(capacidad=4),
        mantenidas=["A1"],
        aplazadas=[AccionAplazada(action_id="A2", motivo="dependencia", detalle="depende de A3")],
        hallazgos_sin_cubrir=["F-2"],
        esfuerzo_total=2,
        intervalo=_intervalo(),
    )
    assert e.simulacion is None
    assert e.aplazadas[0].motivo == "dependencia"


# --- mapa de fuentes ---------------------------------------------------------------------------


def _fuente(**kw: object) -> FuenteSector:
    data: dict[str, object] = {
        "dominio": "directoriomedico.example",
        "tipo": "Directorio / comparador",
        "propiedad": "ganado",
        "citas": 40,
        "cuota_citas": 0.1,
        "por_motor": {"ChatGPT": 0.2},
        "n_estudios": 1,
        "n_marcas": 5,
    } | kw
    return FuenteSector.model_validate(data)


def test_fuente_sector_valida_y_mapa() -> None:
    mapa = MapaFuentes(
        sector="oftalmología", fuentes=[_fuente()], n_estudios=1, n_marcas=10, n_citas=400
    )
    assert mapa.min_marcas == 2


def test_fuente_de_una_sola_marca_no_entra_en_el_mapa() -> None:
    with pytest.raises(ValidationError):
        _fuente(n_marcas=1)


def test_propio_si_y_solo_si_web_propia() -> None:
    assert _fuente(tipo="Web propia", propiedad="propio").propiedad == "propio"
    with pytest.raises(ValidationError):
        _fuente(tipo="Web propia", propiedad="ganado")
    with pytest.raises(ValidationError):
        _fuente(propiedad="propio")


def test_cuota_por_motor_fuera_de_rango_falla() -> None:
    with pytest.raises(ValidationError):
        _fuente(por_motor={"Gemini": 1.5})


def test_oportunidad_necesita_dominio_o_tipo_y_evidencias() -> None:
    base: dict[str, object] = {
        "brand_id": "clinica-alborada-vision",
        "cuota_sector": 0.1,
        "presencia_marca": 0.05,
        "presencia_competidores": 0.3,
        "gap": 0.25,
        "valor": 0.025,
        "puntuacion": "Alta",
        "evaluation_ids": ["EJ-1:clinica-alborada-vision"],
    }
    assert OportunidadFuente.model_validate(base | {"tipo": "Medio"}).tipo == "Medio"
    with pytest.raises(ValidationError):
        OportunidadFuente.model_validate(base)
    with pytest.raises(ValidationError):
        OportunidadFuente.model_validate(base | {"dominio": "x.example", "evaluation_ids": []})


# --- exactitud de marca ------------------------------------------------------------------------


def _afirmacion(id: str = "C1") -> Afirmacion:
    return Afirmacion(
        id=id,
        texto="tiene centro en Valencia",
        tipo="sede",
        brand_id="clinica-alborada-vision",
        evaluation_id="EJ-1:clinica-alborada-vision",
        run_id="EJ-1",
        fuentes_citadas=["directoriomedico.example"],
    )


def test_riesgo_regulatorio_exige_expresion() -> None:
    with pytest.raises(ValidationError):
        Verificacion(afirmacion_id="C1", estado="riesgo_regulatorio", motivo="x")
    v = Verificacion(
        afirmacion_id="C1",
        estado="riesgo_regulatorio",
        motivo="x",
        expresiones_riesgo=["sin riesgo"],
    )
    assert v.expresiones_riesgo == ["sin riesgo"]


def test_hallazgo_exactitud_vacio_es_valido() -> None:
    h = HallazgoExactitud(
        id="F-exactitud",
        study_id="S",
        brand_id="clinica-alborada-vision",
        afirmaciones=[],
        verificaciones=[],
        n_correctas=0,
        n_incorrectas=0,
        n_no_verificables=0,
        n_riesgo_regulatorio=0,
        evaluation_ids=[],
    )
    assert h.n_inexactitudes == 0


def test_hallazgo_exactitud_recuentos_deben_cuadrar() -> None:
    v = Verificacion(afirmacion_id="C1", estado="incorrecta", motivo="sede no está en el brief")
    kw: dict[str, object] = {
        "id": "F-exactitud",
        "study_id": "S",
        "brand_id": "clinica-alborada-vision",
        "afirmaciones": [_afirmacion()],
        "verificaciones": [v],
        "n_correctas": 0,
        "n_no_verificables": 0,
        "n_riesgo_regulatorio": 0,
        "evaluation_ids": ["EJ-1:clinica-alborada-vision"],
    }
    assert HallazgoExactitud.model_validate(kw | {"n_incorrectas": 1}).n_inexactitudes == 1
    with pytest.raises(ValidationError):
        HallazgoExactitud.model_validate(kw | {"n_incorrectas": 0})
    with pytest.raises(ValidationError):
        HallazgoExactitud.model_validate(kw | {"n_incorrectas": 1, "evaluation_ids": []})


def test_mitigacion_enlazada_a_evidencias() -> None:
    m = AccionMitigacion(
        id="M1",
        afirmacion_ids=["C1"],
        fuente_dominio="directoriomedico.example",
        palanca="entidad_datos",
        descripcion="Corregir la ficha en directoriomedico.example",
        evaluation_ids=["EJ-1:clinica-alborada-vision"],
    )
    assert m.palanca == "entidad_datos"
    with pytest.raises(ValidationError):
        AccionMitigacion(
            id="M2", afirmacion_ids=[], palanca="contenido", descripcion="x", evaluation_ids=["e"]
        )
