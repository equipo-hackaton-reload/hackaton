"""Serie temporal de Alborada con el kit (ADR 0016).

- **Misma medición dos veces:** el estudio del kit, re-etiquetado con otro `study_id` y otra fecha.
  Es lo que tiene que dar una re-medición sin cambios reales: 0 cambios significativos y el resumen
  «Sin cambios fuera del margen de error».
- **Segundo punto perturbado (SINTÉTICO):** el estudio del kit con 40 evaluaciones espontáneas de
  Alborada pasadas de «no aparece» a «1.ª, recomendación activa». No es un dato del reto: es una
  perturbación controlada para comprobar que el cambio se detecta.

Las cifras canónicas no cambian: el punto del kit da 25,93, 8.º de 10, IC [21,6; 30,15].
"""

from datetime import datetime

import pytest

from posiq.domain.accuracy import evaluar_exactitud
from posiq.domain.metrics import compute_metrics
from posiq.domain.schemas import ESPONTANEAS, BriefSummary, Evaluation, Study
from posiq.domain.scoring import SCORE_VERSION
from posiq.domain.stats import Muestra
from posiq.domain.tracking import SIN_CAMBIOS, MedicionSerie, construir_serie
from posiq.domain.tracking_schemas import SerieMarca
from tests.golden.conftest import Kit
from tests.golden.test_demo_canonico import FOCO, SCORE_CANONICO

NOMBRE = "Clínica Alborada Visión"
LINEA_BASE = datetime(2026, 9, 14)
TRIMESTRE_2 = datetime(2026, 12, 14)
N_PERTURBADAS = 40


def _medicion(
    kit: Kit,
    brief: BriefSummary,
    study_id: str,
    fecha: datetime,
    evaluations: list[Evaluation] | None = None,
) -> MedicionSerie:
    """El estudio del kit re-etiquetado como `study_id` (mismas respuestas y evaluaciones)."""
    runs = [r.model_copy(update={"study_id": study_id}) for r in kit.runs]
    evals = [e.model_copy(update={"study_id": study_id}) for e in evaluations or kit.evaluations()]
    metrics = compute_metrics(
        brief, kit.market, kit.prompts, runs, evals, kit.sources, study_id=study_id
    )
    study = Study(
        id=study_id,
        brand_id=FOCO,
        brief=brief,
        modo="kit",
        creado_en=fecha,
        version_metodologia="reload-geo-2026",
        score_version=SCORE_VERSION,
        estado="completado",
    )
    brand = next(b for b in kit.brands if b.id == FOCO)
    exactitud, _ = evaluar_exactitud(study_id, brand, brief, runs, marcas=kit.brands)
    return MedicionSerie(
        study,
        metrics,
        Muestra(evals, runs, kit.prompts),
        market=kit.market,
        catalogo=kit.sources,
        exactitud=exactitud,
    )


def _perturbadas(kit: Kit) -> list[Evaluation]:
    """SINTÉTICO: las 40 primeras no-apariciones espontáneas de Alborada pasan a 1.ª activa."""
    espontaneos = {p.id for p in kit.prompts if p.instanciacion in ESPONTANEAS}
    runs = {r.id for r in kit.runs if r.prompt_id in espontaneos}
    out: list[Evaluation] = []
    cambiadas = 0
    for e in sorted(kit.evaluations(), key=lambda e: e.id):
        if cambiadas < N_PERTURBADAS and e.brand_id == FOCO and not e.aparece and e.run_id in runs:
            cambiadas += 1
            datos = e.model_dump(exclude={"peso_posicion", "por_desconocimiento"})
            datos |= {
                "aparece": True,
                "posicion": 1,
                "fuerza": 3,
                "tipo_mencion": "Recomendación activa",
                "sentimiento": "positivo",
            }
            out.append(Evaluation.model_validate(datos))
        else:
            out.append(e)
    assert cambiadas == N_PERTURBADAS
    return out


@pytest.fixture(scope="module")
def base(kit: Kit, alborada_brief: BriefSummary) -> MedicionSerie:
    return _medicion(kit, alborada_brief, "S-serie-base", LINEA_BASE)


@pytest.fixture(scope="module")
def serie_igual(kit: Kit, alborada_brief: BriefSummary, base: MedicionSerie) -> SerieMarca:
    repetida = _medicion(kit, alborada_brief, "S-serie-repetida", TRIMESTRE_2)
    return construir_serie(FOCO, NOMBRE, [repetida, base])


@pytest.fixture(scope="module")
def serie_perturbada(kit: Kit, alborada_brief: BriefSummary, base: MedicionSerie) -> SerieMarca:
    perturbada = _medicion(
        kit, alborada_brief, "S-serie-perturbada-sintetica", TRIMESTRE_2, _perturbadas(kit)
    )
    return construir_serie(FOCO, NOMBRE, [base, perturbada])


def test_punto_del_kit_mantiene_las_cifras_canonicas(serie_igual: SerieMarca) -> None:
    p = serie_igual.puntos[0]
    assert p.study_id == "S-serie-base"
    assert p.score == SCORE_CANONICO
    assert p.intervalo is not None and (p.intervalo.inf, p.intervalo.sup) == (21.6, 30.15)
    assert (p.posicion, p.n_marcas) == (8, 10)
    assert (p.score_medio_competidores, p.diferencia_vs_competidores) == (34.52, -8.59)
    assert p.motores == ["ChatGPT", "Claude", "Gemini", "Perplexity"]
    assert p.modelos_motor == {}  # el kit no declara modelos


def test_misma_medicion_dos_veces_sin_cambios(serie_igual: SerieMarca) -> None:
    a, b = serie_igual.puntos
    assert [a.study_id, b.study_id] == ["S-serie-base", "S-serie-repetida"]
    assert b.comparable_con_anterior and b.avisos == []
    assert a.banco_prompts == b.banco_prompts
    # 1 score + aparición global + 4 motores + puesto + diferencia frente a competidores.
    assert len(serie_igual.cambios) == 8
    assert all(c.delta == 0 for c in serie_igual.cambios)
    assert serie_igual.cambios_significativos == []
    assert serie_igual.resumen == [SIN_CAMBIOS]


def test_indicadores_adelantados_del_kit(serie_igual: SerieMarca) -> None:
    valores = {i.clave: [v.valor for v in i.valores] for i in serie_igual.indicadores}
    assert valores == {
        "cuota_web_propia": [0.0585, 0.0585],  # 33 de 564 citas (5,9 %)
        "presencia_top_fuentes": [0.7413, 0.7413],
        "inexactitudes": [0.0, 0.0],
        "a_revisar": [21.0, 21.0],
    }


def test_segundo_punto_perturbado_detecta_el_cambio(serie_perturbada: SerieMarca) -> None:
    a, b = serie_perturbada.puntos
    assert b.comparable_con_anterior
    assert (a.score, b.score) == (SCORE_CANONICO, 41.81)
    assert (a.posicion, b.posicion) == (8, 3)
    significativos = {c.metrica: c for c in serie_perturbada.cambios_significativos}
    assert set(significativos) == {
        "score",
        "aparicion_espontanea:global",
        "aparicion_espontanea:ChatGPT",
        "aparicion_espontanea:Claude",
        "posicion",
        "diferencia_vs_competidores",
    }
    score = significativos["score"]
    assert score.delta == 15.88
    assert score.significancia is not None
    assert (score.significancia.intervalo.inf, score.significancia.intervalo.sup) == (9.51, 22.47)
    assert score.texto == (
        "Del 14/09/2026 al 14/12/2026: el Score de Citación sube de 25,9 a 41,8 (+15,9 puntos; "
        "IC 95 % del cambio: [+9,5; +22,5]). Sale del margen de error."
    )
    assert significativos["posicion"].delta == -5
    assert significativos["diferencia_vs_competidores"].relativo_a_competidores
    # Gemini y Perplexity suben 10 pp, pero dentro del margen: no van al resumen.
    no_sig = {c.metrica for c in serie_perturbada.cambios if not c.significativo}
    assert no_sig == {"aparicion_espontanea:Gemini", "aparicion_espontanea:Perplexity"}
    assert serie_perturbada.resumen == [c.texto for c in serie_perturbada.cambios_significativos]
