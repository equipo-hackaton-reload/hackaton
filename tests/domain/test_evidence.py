from posiq.domain.evidence import evidence_coverage
from posiq.domain.schemas import Finding, Phase, Plan
from tests.domain.factories import action, evaluation


def finding(id: str, evaluation_ids: list[str]) -> Finding:
    return Finding(
        id=id,
        study_id="S-1",
        titulo="t",
        descripcion="d",
        impacto="M",
        confianza=0.6,
        cifra=0.1,
        origen_cifra="x",
        evaluation_ids=evaluation_ids,
    )


def test_cobertura_de_evidencia() -> None:
    evals = [evaluation(run_id="EJ-1"), evaluation(run_id="EJ-2")]
    findings = [finding("F1", ["EJ-1:alborada"]), finding("F2", ["EJ-1:alborada", "EJ-9:otra"])]
    plan = Plan(
        study_id="S-1",
        objetivos=[],
        fases=[
            Phase(
                nombre="F0",
                semanas=1,
                objetivo="o",
                acciones=[
                    action(id="A1", finding_ids=["F1"]),
                    action(id="A2", finding_ids=["F1", "F2"]),
                    action(id="A3", finding_ids=["F7"]),
                ],
            )
        ],
        presupuesto_estimado_eur=0,
        respeta_restricciones=True,
    )
    c = evidence_coverage(findings, plan, evals)
    assert (c.hallazgos_con_evidencia, c.pct_hallazgos) == (1, 0.5)
    assert c.hallazgos_sin_evidencia == ["F2"]
    assert (c.acciones_con_hallazgos, c.acciones_sin_hallazgos) == (1, ["A2", "A3"])


def test_sin_plan_ni_hallazgos() -> None:
    c = evidence_coverage([], None, [])
    assert c.pct_hallazgos is None and c.pct_acciones is None and c.n_acciones == 0
