"""Rigor estadístico (`domain/stats.py`): Wilson, Newcombe, bootstrap y significancia."""

import pytest

from posiq.domain.findings import detect_findings
from posiq.domain.metrics import compute_metrics, diff_metrics
from posiq.domain.schemas import Evaluation, Finding, Market, Metrics, PromptInstance, Run
from posiq.domain.stats import (
    SIN_CONTRASTE_FUENTE_LIDER,
    Muestra,
    aparicion_por_motor,
    diferencia_proporciones,
    diferencia_scores,
    formato_intervalo,
    formato_margen,
    intervalo_score,
    intervalos_aparicion,
    intervalos_score_por_motor,
    significancia_hallazgos,
    significancia_remedicion,
    wilson,
)
from posiq.domain.stats_schemas import Intervalo
from tests.domain.factories import brand, brief, evaluation, prompt, run

# --- Wilson y Newcombe contra valores publicados ----------------------------------------------

# Newcombe (1998), «Two-sided confidence intervals for the single proportion», tabla I, método 3.
WILSON_REFERENCIA = [
    (81, 263, 0.2553, 0.3662),
    (15, 148, 0.0624, 0.1605),
    (0, 20, 0.0, 0.1611),
    (1, 29, 0.0061, 0.1718),
    (0, 10, 0.0, 0.2775),
    (10, 10, 0.7225, 1.0),
]


@pytest.mark.parametrize(("x", "n", "inf", "sup"), WILSON_REFERENCIA)
def test_wilson_contra_referencia(x: int, n: int, inf: float, sup: float) -> None:
    i = wilson(x, n)
    assert (round(i.inf, 4), round(i.sup, 4)) == (inf, sup)
    assert i.valor == x / n
    assert (i.n, i.nivel, i.metodo) == (n, 0.95, "wilson")


def test_wilson_extremos_exactos() -> None:
    assert wilson(0, 7).inf == 0.0
    assert wilson(7, 7).sup == 1.0


@pytest.mark.parametrize(("x", "n"), [(1, 0), (-1, 5), (6, 5)])
def test_wilson_rechaza_entradas_imposibles(x: int, n: int) -> None:
    with pytest.raises(ValueError):
        wilson(x, n)


# Newcombe (1998), «Interval estimation for the difference between independent proportions»,
# tabla II, método 10.
NEWCOMBE_REFERENCIA = [
    (56, 70, 48, 80, 0.0524, 0.3339, True),
    (9, 10, 3, 10, 0.1705, 0.8090, True),
    (6, 7, 2, 7, 0.0582, 0.8062, True),
    (5, 56, 0, 29, -0.0381, 0.1926, False),
    (0, 10, 0, 20, -0.1611, 0.2775, False),
    (10, 10, 0, 20, 0.6791, 1.0, True),
]


@pytest.mark.parametrize(("x1", "n1", "x2", "n2", "inf", "sup", "sig"), NEWCOMBE_REFERENCIA)
def test_newcombe_contra_referencia(
    x1: int, n1: int, x2: int, n2: int, inf: float, sup: float, sig: bool
) -> None:
    s = diferencia_proporciones(x1, n1, x2, n2)
    assert (s.intervalo.inf, s.intervalo.sup) == (inf, sup)
    assert s.delta == round(x1 / n1 - x2 / n2, 4)
    assert s.significativa is sig
    assert s.intervalo.metodo == "diferencia_proporciones"
    assert s.p_valor is None


def test_newcombe_antisimetrico() -> None:
    ab, ba = diferencia_proporciones(9, 10, 3, 10), diferencia_proporciones(3, 10, 9, 10)
    assert ba.delta == -ab.delta
    assert (ba.intervalo.inf, ba.intervalo.sup) == (-ab.intervalo.sup, -ab.intervalo.inf)


# --- Datos sintéticos -------------------------------------------------------------------------

FOCO, LIDER = "alborada", "lider"
MOTORES = ("ChatGPT", "Gemini")


def _muestra(
    tasa_foco: float, tasa_lider: float, n_prompts: int = 10, study_id: str = "S-1"
) -> tuple[Muestra, Market]:
    """`n_prompts` prompts genéricos × 2 motores × 2 repeticiones; aparece según la tasa."""
    prompts: list[PromptInstance] = [
        prompt(id=f"P-{i}", ciudad="Madrid" if i % 2 else "Barcelona") for i in range(n_prompts)
    ]
    runs: list[Run] = []
    evals: list[Evaluation] = []
    k = 0
    for p in prompts:
        for motor in MOTORES:
            for rep in (1, 2):
                rid = f"{p.id}-{motor}-{rep}"
                runs.append(
                    run(
                        id=rid,
                        prompt_id=p.id,
                        motor=motor,
                        repeticion=rep,
                        study_id=study_id,
                        marcas=[FOCO, LIDER],
                    )
                )
                total = n_prompts * len(MOTORES) * 2
                for b, tasa in ((FOCO, tasa_foco), (LIDER, tasa_lider)):
                    aparece = k < round(tasa * total)
                    evals.append(
                        evaluation(
                            b, rid, aparece, study_id=study_id, posicion=1 if aparece else None
                        )
                    )
                k += 1
    market = Market(marcas=[brand(FOCO), brand(LIDER, nombre="Grupo Valdecruz", rol="lider")])
    return Muestra(evals, runs, prompts), market


def _metrics(m: Muestra, market: Market, study_id: str = "S-1") -> Metrics:
    return compute_metrics(brief(), market, m.prompts, m.runs, m.evaluations, [], study_id)


# --- Bootstrap del score ----------------------------------------------------------------------


def test_intervalo_score_contiene_el_score_y_es_determinista() -> None:
    muestra, market = _muestra(0.4, 0.8)
    metrics = _metrics(muestra, market)
    a = intervalo_score(muestra, FOCO, replicas=300)
    b = intervalo_score(muestra, FOCO, replicas=300)
    assert a is not None and a == b
    assert a.valor == metrics.score_global.score
    assert a.inf < a.valor < a.sup
    assert (a.n, a.metodo) == (40, "bootstrap")


def test_intervalo_score_cambia_con_la_semilla() -> None:
    muestra, _ = _muestra(0.4, 0.8)
    a = intervalo_score(muestra, FOCO, replicas=300, semilla=1)
    b = intervalo_score(muestra, FOCO, replicas=300, semilla=2)
    assert a is not None and b is not None
    assert (a.inf, a.sup) != (b.inf, b.sup)
    assert a.valor == b.valor


def test_intervalo_score_por_motor_y_sin_poblacion() -> None:
    muestra, _ = _muestra(0.4, 0.8)
    por_motor = intervalo_score(muestra, FOCO, "ChatGPT", replicas=200)
    assert por_motor is not None and por_motor.n == 20
    assert intervalo_score(muestra, FOCO, "Claude", replicas=200) is None


def test_bootstrap_por_prompt_es_mas_ancho_si_las_repeticiones_coinciden() -> None:
    """Todas las ejecuciones de un prompt coinciden: remuestrear prompts da más error."""
    prompts = [prompt(id=f"P-{i}") for i in range(12)]
    runs, evals = [], []
    for p in prompts:
        aparece = int(p.id.split("-")[1]) < 6
        for rep in (1, 2, 3):
            rid = f"{p.id}-{rep}"
            runs.append(run(id=rid, prompt_id=p.id, repeticion=rep))
            evals.append(evaluation(FOCO, rid, aparece, posicion=1 if aparece else None))
    muestra = Muestra(evals, runs, prompts)
    por_ejecucion = intervalo_score(muestra, FOCO, replicas=500)
    por_prompt = intervalo_score(muestra, FOCO, replicas=500, unidad="prompt")
    assert por_ejecucion is not None and por_prompt is not None
    assert por_prompt.margen > por_ejecucion.margen


def test_evaluacion_duplicada_es_un_error() -> None:
    muestra, _ = _muestra(0.4, 0.8)
    duplicada = Muestra(
        [*muestra.evaluations, muestra.evaluations[0]], muestra.runs, muestra.prompts
    )
    with pytest.raises(ValueError, match="más de una evaluación"):
        intervalo_score(duplicada, FOCO, replicas=10)


def test_diferencia_scores_emparejada() -> None:
    muestra, _ = _muestra(0.2, 0.9)
    s = diferencia_scores(muestra, LIDER, FOCO, replicas=300)
    assert s is not None and s.significativa
    assert s.intervalo.inf <= s.delta <= s.intervalo.sup
    igual, _ = _muestra(0.5, 0.5)
    t = diferencia_scores(igual, LIDER, FOCO, replicas=300)
    assert t is not None and t.delta == 0 and not t.significativa


# --- Aparición por segmento -------------------------------------------------------------------


def test_intervalos_aparicion_por_segmento() -> None:
    muestra, market = _muestra(0.25, 0.8)
    metrics = _metrics(muestra, market)
    segmentos = intervalos_aparicion(metrics)
    assert {s.brand_id for s in segmentos} == {FOCO}
    celdas = metrics.cells(FOCO, "espontaneo", "motor")
    for c in celdas:
        s = next(
            s
            for s in segmentos
            if (s.tipo, s.dimension, s.valor) == ("espontaneo", "motor", c.valor)
        )
        assert s.intervalo == wilson(c.apariciones, c.n)
    sin_datos = [s for s in segmentos if s.tipo == "asistido"]
    assert sin_datos and all(s.intervalo is None for s in sin_datos)


# --- Significancia de hallazgos ---------------------------------------------------------------


def test_significancia_hallazgos_coherente_con_las_cifras() -> None:
    muestra, market = _muestra(0.25, 0.9)
    metrics = _metrics(muestra, market)
    findings = detect_findings(metrics, brief())
    assert findings
    resultado = significancia_hallazgos(findings, metrics, muestra, replicas=200)
    assert list(resultado) == [f.id for f in findings]
    assert {"F-brecha-lider", "F-ciudad-madrid"} <= set(resultado)
    assert {r.significativo for r in resultado.values()} == {True, False}
    for f in findings:
        r = resultado[f.id]
        if f.id == "F-brecha-lider":
            assert r.significancia is not None and r.significancia.delta == f.cifra
        if r.significancia is not None:
            i = r.significancia.intervalo
            assert r.significativo == (not i.inf <= 0 <= i.sup)


def test_hallazgos_sin_contraste_se_declaran() -> None:
    muestra, market = _muestra(0.25, 0.9)
    metrics = _metrics(muestra, market)
    base = {"study_id": "S-1", "titulo": "t", "descripcion": "d", "impacto": "M"}
    findings = [
        Finding.model_validate(
            base
            | {
                "id": i,
                "confianza": 0.5,
                "cifra": 3,
                "unidad": "recuento",
                "origen_cifra": "x",
                "evaluation_ids": ["e"],
            }
        )
        for i in ("F-fuente-lider", "F-menciones-negativas", "F-nueva-regla")
    ]
    r = significancia_hallazgos(findings, metrics, muestra, replicas=10)
    assert all(h.significancia is None and h.significativo is None for h in r.values())
    assert r["F-fuente-lider"].sin_contraste == SIN_CONTRASTE_FUENTE_LIDER
    assert "F-nueva-regla" in (r["F-nueva-regla"].sin_contraste or "")


def test_ciudad_baja_contra_el_umbral() -> None:
    muestra, market = _muestra(0.1, 0.9)
    metrics = _metrics(muestra, market)
    ciudades = [f for f in detect_findings(metrics, brief()) if f.id.startswith("F-ciudad-")]
    assert ciudades
    r = significancia_hallazgos(ciudades, metrics, muestra, replicas=10)
    for f in ciudades:
        s = r[f.id].significancia
        assert s is not None and s.intervalo.metodo == "wilson"
        assert s.delta == round(f.cifra - 0.30, 4)


# --- Re-medición ------------------------------------------------------------------------------


def test_significancia_remedicion_alineada_con_diff_metrics() -> None:
    antes, market = _muestra(0.2, 0.8, study_id="S-0")
    ahora, _ = _muestra(0.7, 0.8, study_id="S-1")
    m_antes, m_ahora = _metrics(antes, market, "S-0"), _metrics(ahora, market, "S-1")
    delta = diff_metrics(m_ahora, m_antes)
    s = significancia_remedicion(m_ahora, m_antes, ahora, antes, replicas=300)
    assert (s.study_id, s.comparado_con, s.marca_foco_id) == ("S-1", "S-0", FOCO)
    assert s.score is not None and s.score.delta == delta.score_delta and s.score.significativa
    assert [(t.tipo, t.dimension, t.valor) for t in s.tasas] == [
        (v.tipo, v.dimension, v.valor) for v in delta.visibilidad_delta
    ]
    for t, v in zip(s.tasas, delta.visibilidad_delta, strict=True):
        if v.delta is None:
            assert t.significancia is None
        else:
            assert t.significancia is not None and t.significancia.delta == v.delta
    claves = s.por_clave()
    assert claves["score_global"] == s.score
    esp = next(
        v for v in delta.visibilidad_delta if (v.tipo, v.dimension) == ("espontaneo", "global")
    )
    assert claves["espontaneo:global:global"].delta == esp.delta
    assert not any(k.startswith("asistido:") for k in claves)  # sin datos asistidos: se omiten
    global_esp = next(t for t in s.tasas if (t.tipo, t.dimension) == ("espontaneo", "global"))
    assert global_esp.significancia is not None and global_esp.significancia.significativa


def test_remedicion_sin_cambio_no_es_significativa() -> None:
    antes, market = _muestra(0.4, 0.8, study_id="S-0")
    ahora, _ = _muestra(0.4, 0.8, study_id="S-1")
    m_antes, m_ahora = _metrics(antes, market, "S-0"), _metrics(ahora, market, "S-1")
    s = significancia_remedicion(m_ahora, m_antes, ahora, antes, replicas=300)
    assert s.score is not None and s.score.delta == 0 and not s.score.significativa
    assert all(t.significancia is None or not t.significancia.significativa for t in s.tasas)


def test_remedicion_con_muestra_ajena_es_un_error() -> None:
    antes, market = _muestra(0.2, 0.8, study_id="S-0")
    ahora, _ = _muestra(0.7, 0.8, study_id="S-1")
    m_antes, m_ahora = _metrics(antes, market, "S-0"), _metrics(ahora, market, "S-1")
    with pytest.raises(ValueError, match="la muestra actual"):
        significancia_remedicion(m_ahora, m_antes, antes, antes, replicas=10)


# --- Formato ----------------------------------------------------------------------------------


def test_formato_en_espanol() -> None:
    score = Intervalo(valor=25.93, inf=21.6, sup=30.15, n=240, metodo="bootstrap")
    assert formato_intervalo(score) == "25,9 [21,6–30,1]"
    tasa = wilson(9, 60)
    assert formato_intervalo(tasa, 0, porcentaje=True) == "15 % [8–26 %]"
    assert formato_margen(tasa) == "± 11 pp"
    assert formato_margen(score, 1, porcentaje=False) == "± 4,3"
    negativo = Intervalo(valor=-0.2583, inf=-0.2926, sup=-0.0976, n=24, metodo="wilson")
    assert formato_intervalo(negativo, 2) == "−0,26 [−0,29; −0,10]"
    cruza = Intervalo(valor=0.004, inf=-0.0004, sup=0.01, n=24, metodo="wilson")
    assert formato_intervalo(cruza, 2) == "0,00 [0,00–0,01]"


def test_diccionarios_por_motor() -> None:
    muestra, market = _muestra(0.25, 0.8)
    metrics = _metrics(muestra, market)
    aparicion = aparicion_por_motor(metrics)
    assert list(aparicion) == list(MOTORES)
    for c in metrics.cells(FOCO, "espontaneo", "motor"):
        assert aparicion[c.valor] == wilson(c.apariciones, c.n)  # type: ignore[index]
    scores = intervalos_score_por_motor(muestra, FOCO, replicas=100)
    assert list(scores) == list(MOTORES)
    assert scores["ChatGPT"] == intervalo_score(muestra, FOCO, "ChatGPT", replicas=100)
