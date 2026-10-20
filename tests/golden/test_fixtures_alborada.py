"""Los datos de ejemplo compartidos con exportación, web y demo son válidos y estables."""

from posiq.domain.schemas import (
    BriefSummary,
    Finding,
    Plan,
    Proposal,
    validate_plan_against_brief,
)


def test_plan_alborada(
    plan_alborada: Plan, findings_alborada: list[Finding], alborada_brief: BriefSummary
) -> None:
    assert len(findings_alborada) == 7 and len(plan_alborada.fases) == 4
    assert [a.id for a in plan_alborada.acciones] == [
        "A0-1",
        "A0-2",
        "A1-1",
        "A1-2",
        "A2-1",
        "A2-2",
        "A2-3",
        "A3-1",
        "A3-2",
    ]
    ids = {f.id for f in findings_alborada}
    assert ids == {f for a in plan_alborada.acciones for f in a.finding_ids}
    assert validate_plan_against_brief(plan_alborada, alborada_brief) == []


def test_proposal_alborada(proposal_alborada: Proposal, plan_alborada: Plan) -> None:
    assert proposal_alborada.plan == plan_alborada
    assert proposal_alborada.contexto.datos_sinteticos
    assert len(proposal_alborada.hallazgos) == 7
    assert proposal_alborada.hoja_ruta.hitos[-1].semana == 42
    assert Proposal.model_validate_json(proposal_alborada.model_dump_json()) == proposal_alborada
