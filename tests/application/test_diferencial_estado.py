"""Los modelos del diferencial viajan en el estado del grafo y sobreviven al checkpointer."""

from pydantic import BaseModel

from posiq.application.diferencial import EscenarioGuardado, Rigor
from posiq.application.graph import serializer
from posiq.domain.accuracy_schemas import AccionMitigacion, HallazgoExactitud
from posiq.domain.scenario_schemas import EntradaEscenario, EscenarioPlan
from posiq.domain.source_map_schemas import OportunidadFuente
from posiq.domain.stats_schemas import Intervalo, Significancia


def roundtrip(value: BaseModel) -> object:
    s = serializer()
    return s.loads_typed(s.dumps_typed(value))


def intervalo(valor: float = 0.4) -> Intervalo:
    return Intervalo(valor=valor, inf=valor - 0.1, sup=valor + 0.1, n=50, metodo="wilson")


def test_rigor_survives_the_checkpointer() -> None:
    delta = Significancia(
        delta=0.0,
        intervalo=Intervalo(valor=0.0, inf=-0.1, sup=0.1, n=40, metodo="diferencia_proporciones"),
        significativa=False,
    )
    rigor = Rigor(
        score_global=intervalo(25.93),
        score_por_motor={"Claude": intervalo(30.0)},
        aparicion_por_motor={"Gemini": intervalo(0.39)},
        hallazgos={"F-brecha-lider": delta},
        deltas={"score_global": delta},
    )
    assert roundtrip(rigor) == rigor


def test_scenarios_opportunities_and_accuracy_survive_the_checkpointer() -> None:
    plan = EscenarioPlan(
        nombre="minimo_viable",
        entrada=EntradaEscenario(capacidad=3),
        mantenidas=["A1"],
        aplazadas=[],
        hallazgos_sin_cubrir=[],
        esfuerzo_total=2,
    )
    guardado = EscenarioGuardado(id="E1", elegido=True, escenario=plan)
    oportunidad = OportunidadFuente(
        brand_id="alborada",
        dominio="medio.example",
        cuota_sector=0.2,
        presencia_marca=0.1,
        presencia_competidores=0.5,
        gap=0.4,
        valor=0.08,
        puntuacion="Alta",
        evaluation_ids=["EJ-1:alborada"],
    )
    exactitud = HallazgoExactitud(
        id="X-alborada",
        study_id="s1",
        brand_id="alborada",
        afirmaciones=[],
        verificaciones=[],
        n_correctas=0,
        n_incorrectas=0,
        n_no_verificables=0,
        n_riesgo_regulatorio=0,
        evaluation_ids=[],
    )
    mitigacion = AccionMitigacion(
        id="M1",
        afirmacion_ids=["AF1"],
        palanca="entidad_datos",
        descripcion="Corregir la ficha del directorio",
        evaluation_ids=["EJ-1:alborada"],
    )
    for value in (guardado, oportunidad, exactitud, mitigacion):
        assert roundtrip(value) == value
