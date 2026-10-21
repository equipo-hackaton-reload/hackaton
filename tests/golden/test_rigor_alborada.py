"""Rigor estadístico de la demo de Alborada (etiquetas del kit, como la cifra canónica 25,93).

Las cifras de ADR 0008 y `docs/estado/A.md`. El bootstrap va sembrado (`SEMILLA_BOOTSTRAP`,
`REPLICAS_BOOTSTRAP`), así que los intervalos son exactos y se fijan aquí.
"""

import importlib.util
from pathlib import Path

import pytest

from posiq.domain.schemas import Finding, Metrics
from posiq.domain.stats import (
    REPLICAS_BOOTSTRAP,
    SEMILLA_BOOTSTRAP,
    Muestra,
    formato_intervalo,
    formato_margen,
    informe_rigor,
    intervalo_score,
)
from posiq.domain.stats_schemas import InformeRigor, Intervalo
from tests.golden.conftest import Kit
from tests.golden.test_demo_canonico import FOCO, SCORE_CANONICO


@pytest.fixture(scope="module")
def muestra(kit: Kit) -> Muestra:
    return Muestra(kit.evaluations(), kit.runs, kit.prompts)


@pytest.fixture(scope="module")
def informe(
    metrics_alborada: Metrics, findings_alborada: list[Finding], muestra: Muestra
) -> InformeRigor:
    return informe_rigor(metrics_alborada, findings_alborada, muestra)


def _aparicion(informe: InformeRigor, dimension: str, valor: str) -> Intervalo:
    s = next(
        s
        for s in informe.aparicion
        if (s.tipo, s.dimension, s.valor) == ("espontaneo", dimension, valor)
    )
    assert s.intervalo is not None
    return s.intervalo


def test_ic_del_score_contiene_la_cifra_canonica(informe: InformeRigor) -> None:
    s = informe.score
    assert s is not None
    assert s.valor == SCORE_CANONICO
    assert s.inf < SCORE_CANONICO < s.sup
    assert (s.inf, s.sup, s.n, s.metodo) == (21.6, 30.15, 240, "bootstrap")
    assert formato_intervalo(s) == "25,9 [21,6–30,1]"
    assert (informe.replicas_bootstrap, informe.semilla_bootstrap) == (
        REPLICAS_BOOTSTRAP,
        SEMILLA_BOOTSTRAP,
    )


def test_ic_del_score_por_prompt_es_mas_ancho(informe: InformeRigor, muestra: Muestra) -> None:
    """Sensibilidad: remuestrear prompts enteros (las repeticiones se parecen) ensancha el IC."""
    por_prompt = intervalo_score(muestra, FOCO, unidad="prompt")
    assert por_prompt is not None and informe.score is not None
    assert (por_prompt.inf, por_prompt.sup) == (19.7, 31.84)
    assert por_prompt.margen > informe.score.margen


@pytest.mark.parametrize(
    ("motor", "tasa", "inf", "sup", "margen"),
    [
        ("ChatGPT", 0.1833, 0.1056, 0.2992, "± 12 pp"),
        ("Claude", 0.15, 0.081, 0.2611, "± 11 pp"),
        ("Gemini", 0.5667, 0.441, 0.6843, "± 13 pp"),
        ("Perplexity", 0.65, 0.5236, 0.7583, "± 13 pp"),
    ],
)
def test_aparicion_por_motor(
    informe: InformeRigor, motor: str, tasa: float, inf: float, sup: float, margen: str
) -> None:
    i = _aparicion(informe, "motor", motor)
    assert i.n == 60 and i.metodo == "wilson"
    assert (round(i.valor, 4), round(i.inf, 4), round(i.sup, 4)) == (tasa, inf, sup)
    assert formato_margen(i) == margen


def test_aparicion_global_y_por_ciudad(informe: InformeRigor) -> None:
    g = _aparicion(informe, "global", "global")
    assert (g.n, round(g.inf, 4), round(g.sup, 4)) == (240, 0.3281, 0.4504)
    assert formato_intervalo(g, 0, porcentaje=True) == "39 % [33–45 %]"
    bcn = _aparicion(informe, "ciudad", "Barcelona")
    assert formato_intervalo(bcn, 0, porcentaje=True) == "4 % [1–20 %]"


def test_significancia_de_los_hallazgos(
    informe: InformeRigor, findings_alborada: list[Finding]
) -> None:
    por_id = {h.finding_id: h for h in informe.hallazgos}
    assert list(por_id) == [f.id for f in findings_alborada]
    # Seis contrastables, todos significativos al 95 %; la brecha de fuentes no admite contraste.
    assert {k: h.significativo for k, h in por_id.items()} == {
        "F-motor-debil": True,
        "F-ciudad-barcelona": True,
        "F-brecha-lider": True,
        "F-caida-embudo": True,
        "F-fuente-lider": None,
        "F-asistida-vs-espontanea": True,
        "F-recomendacion-debil": True,
    }
    intervalos = {
        k: (h.significancia.delta, h.significancia.intervalo.inf, h.significancia.intervalo.sup)
        for k, h in por_id.items()
        if h.significancia is not None
    }
    assert intervalos == {
        "F-motor-debil": (0.5, 0.3317, 0.6284),
        "F-ciudad-barcelona": (-0.2583, -0.2926, -0.0976),
        "F-brecha-lider": (40.53, 35.34, 45.56),
        "F-caida-embudo": (0.197, 0.0365, 0.3289),
        "F-asistida-vs-espontanea": (0.6125, 0.5408, 0.6719),
        "F-recomendacion-debil": (-0.489, -0.5, -0.468),
    }
    cifras = {f.id: f.cifra for f in findings_alborada}
    assert intervalos["F-brecha-lider"][0] == cifras["F-brecha-lider"]
    assert intervalos["F-caida-embudo"][0] == cifras["F-caida-embudo"]
    assert intervalos["F-asistida-vs-espontanea"][0] == cifras["F-asistida-vs-espontanea"]


def test_las_cifras_canonicas_no_cambian(metrics_alborada: Metrics) -> None:
    """El rigor estadístico solo añade márgenes: el score y el ranking siguen siendo los mismos."""
    assert metrics_alborada.score_global.score == SCORE_CANONICO
    assert metrics_alborada.ranking.index(FOCO) + 1 == 8


def test_script_informe_rigor(
    informe: InformeRigor, metrics_alborada: Metrics, muestra: Muestra
) -> None:
    ruta = Path(__file__).resolve().parents[2] / "scripts" / "informe_rigor.py"
    spec = importlib.util.spec_from_file_location("informe_rigor", ruta)
    assert spec and spec.loader
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    texto = script.render(informe, metrics_alborada, muestra)
    assert "**25,9 [21,6–30,1]**" in texto
    assert "| Claude (n = 60) | 15 % [8–26 %] | ± 11 pp | 9,7 [4,2–15,7] |" in texto
    assert "| F-ciudad-barcelona |" in texto and "−0,2583 [−0,2926; −0,0976]" in texto
    assert "| F-fuente-lider |" in texto and "sin contraste" in texto
