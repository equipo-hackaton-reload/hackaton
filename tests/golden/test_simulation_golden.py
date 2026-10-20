"""Simulación del plan de ejemplo de Alborada sobre las métricas del kit."""

from posiq.domain.schemas import Finding, Metrics, Plan
from posiq.domain.simulation import simulate_plan


def test_simulacion_del_plan_de_ejemplo(
    alborada_study: tuple[Metrics, list[Finding], Plan],
) -> None:
    metrics, findings, plan = alborada_study
    result = simulate_plan(plan, metrics, findings)
    print()
    print(f"score actual {result.score_actual} · tasa espontánea {result.tasa_espontanea_actual}")
    for p in result.proyecciones:
        print(
            f"{p.fase}: score {p.score.minimo} / {p.score.esperado} / {p.score.maximo} · "
            f"tasa {p.tasa_espontanea.esperado}"
        )
    for s in result.segmentos:
        print(f"  {s.segmento}: {s.tasa_actual} +{s.delta.esperado} ({', '.join(s.acciones)})")
    print("sin efecto:", [(a.action_id, a.motivo) for a in result.acciones_sin_efecto])

    assert len(plan.acciones) == 9 and len(result.proyecciones) == 4
    assert result.score_actual == metrics.score_global.score
    esperados = [p.score.esperado for p in result.proyecciones]
    assert esperados == sorted(esperados)
    assert result.score_actual is not None
    assert result.score_actual <= esperados[0] and esperados[-1] <= 100
    assert {a.action_id for a in result.acciones_sin_efecto} == {"A0-1", "A3-1"}
