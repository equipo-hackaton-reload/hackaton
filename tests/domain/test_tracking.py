"""Serie temporal de una marca (ADR 0016) con mediciones SINTÉTICAS.

Todas las mediciones de este fichero son sintéticas: dos marcas inventadas sobre el mismo esquema
del kit, con apariciones fijadas a mano para provocar cada caso (comparable o no, cambio dentro o
fuera del margen de error). No son datos del reto.
"""

import re
from datetime import datetime

import pytest

from posiq.domain.accuracy_schemas import HallazgoExactitud
from posiq.domain.metrics import compute_metrics
from posiq.domain.schemas import Evaluation, Market, Motor, PromptInstance, Run, Study
from posiq.domain.scoring import SCORE_VERSION
from posiq.domain.stats import Muestra
from posiq.domain.stats_schemas import Intervalo, Significancia
from posiq.domain.tracking import (
    MOTIVO_COMPETIDORES,
    MOTIVO_LINEA_BASE,
    NO_COMPARABLE,
    RESUMEN_LINEA_BASE,
    RESUMEN_SIN_MEDICIONES,
    SIN_CAMBIOS,
    SIN_CAMBIOS_COMPARABLES,
    MedicionSerie,
    comparabilidad,
    construir_serie,
    huella_banco,
)
from posiq.domain.tracking_schemas import CambioSerie, SerieMarca
from tests.domain import factories as f

FOCO = "alborada"
RIVAL = "rival"
REPLICAS = 300
"""Pocas réplicas para que los tests vayan rápido; la semilla sigue fija."""

MARCAS = [
    f.brand(FOCO, dominio="alborada.example"),
    f.brand(RIVAL, "Rival Visión", rol="lider", dominio="rival.example"),
]
MERCADO = Market(marcas=MARCAS, confirmado_por_humano=True)
TERCERA = "tercera"
MERCADO_AMPLIO = Market(
    marcas=[*MARCAS, f.brand(TERCERA, "Tercera Visión", rol="contexto", dominio="tercera.example")],
    confirmado_por_humano=True,
)
PROMPTS = [
    f.prompt("P-1", texto="¿Qué clínica oftalmológica me recomiendas?"),
    f.prompt("P-2", texto="¿Dónde me opero de miopía?"),
]


def _medicion(
    study_id: str,
    fecha: datetime,
    apariciones_foco: int,
    *,
    apariciones_rival: int = 20,
    n: int = 40,
    motores: tuple[Motor, ...] = ("ChatGPT", "Gemini"),
    modelo: str | None = None,
    version_metodologia: str = "metodo-1",
    prompts: list[PromptInstance] = PROMPTS,
    market: Market | None = None,
    exactitud: HallazgoExactitud | None = None,
    mercado_metricas: Market = MERCADO,
) -> MedicionSerie:
    """Medición sintética: `n` ejecuciones espontáneas; la marca foco aparece en las primeras
    `apariciones_foco` (1.ª, fuerza 3) y el rival en las primeras `apariciones_rival` (2.º).
    Con `mercado_metricas` = `MERCADO_AMPLIO`, la tercera marca se evalúa y no aparece nunca."""
    runs: list[Run] = []
    evaluations: list[Evaluation] = []
    for i in range(n):
        run = f.run(
            f"{study_id}-R{i:03d}",
            "Respuesta sintética",
            [b.id for b in mercado_metricas.marcas],
            study_id=study_id,
            prompt_id=prompts[i % len(prompts)].id,
            motor=motores[i % len(motores)],
            modelo=modelo,
            fecha=fecha,
            fuentes=[f.source("alborada.example", "Web propia"), f.source()],
        )
        runs.append(run)
        foco = i < apariciones_foco
        rival = i < apariciones_rival
        evaluations += [
            f.evaluation(FOCO, run.id, foco, study_id=study_id),
            f.evaluation(
                RIVAL,
                run.id,
                rival,
                study_id=study_id,
                posicion=2 if rival else None,
                fuerza=2 if rival else 0,
            ),
        ]
        if any(b.id == TERCERA for b in mercado_metricas.marcas):
            evaluations.append(f.evaluation(TERCERA, run.id, False, study_id=study_id))
    brief = f.brief()
    metrics = compute_metrics(
        brief, mercado_metricas, prompts, runs, evaluations, [], study_id=study_id
    )
    study = Study(
        id=study_id,
        brand_id=FOCO,
        brief=brief,
        modo="kit",
        creado_en=fecha,
        version_metodologia=version_metodologia,
        score_version=SCORE_VERSION,
        estado="completado",
    )
    return MedicionSerie(
        study, metrics, Muestra(evaluations, runs, prompts), market=market, exactitud=exactitud
    )


T1, T2, T3 = datetime(2026, 1, 15), datetime(2026, 4, 15), datetime(2026, 7, 15)


def _serie(*mediciones: MedicionSerie) -> SerieMarca:
    return construir_serie(FOCO, "Clínica Alborada Visión", mediciones, replicas=REPLICAS)


# --- Huella del banco -----------------------------------------------------------------------------


def test_huella_banco_determinista_e_independiente_del_orden_y_de_los_ids() -> None:
    h = huella_banco(PROMPTS)
    assert h.startswith("sha256:") and len(h) == len("sha256:") + 16
    assert huella_banco(list(reversed(PROMPTS))) == h
    renombrados = [p.model_copy(update={"id": f"X-{p.id}"}) for p in PROMPTS]
    assert huella_banco(renombrados) == h


def test_huella_banco_cambia_si_cambia_lo_que_se_pregunta() -> None:
    otro = [PROMPTS[0], PROMPTS[1].model_copy(update={"texto": "¿Dónde me opero de cataratas?"})]
    assert huella_banco(otro) != huella_banco(PROMPTS)
    assert huella_banco(PROMPTS[:1]) != huella_banco(PROMPTS)


# --- Comparabilidad -------------------------------------------------------------------------------


def test_mismas_condiciones_son_comparables() -> None:
    serie = _serie(_medicion("S-1", T1, 10), _medicion("S-2", T2, 10))
    a, b = serie.puntos
    assert comparabilidad(a, b).comparable
    assert b.comparable_con_anterior and b.motivos_no_comparable == [] and b.avisos == []


@pytest.mark.parametrize(
    ("cambio", "motivo"),
    [
        ({"version_metodologia": "metodo-2"}, "versión de la metodología"),
        (
            {"prompts": [PROMPTS[0], PROMPTS[1].model_copy(update={"texto": "Otra pregunta"})]},
            "banco de prompts",
        ),
        ({"motores": ("ChatGPT", "Gemini", "Claude")}, "motores"),
    ],
)
def test_no_comparable_con_motivo_explicito(cambio: dict[str, object], motivo: str) -> None:
    serie = _serie(_medicion("S-1", T1, 5), _medicion("S-2", T2, 35, **cambio))  # type: ignore[arg-type]
    b = serie.puntos[1]
    assert not b.comparable_con_anterior
    assert any(motivo in m for m in b.motivos_no_comparable)
    # Sin comparabilidad no hay cambios, aunque el score se haya movido mucho.
    assert serie.cambios == [] and serie.cambios_significativos == []
    # Y el resumen no dice «Sin cambios»: dice que no es comparable y por qué.
    assert len(serie.resumen) == 1 and SIN_CAMBIOS not in serie.resumen[0]
    linea = serie.resumen[0]
    assert linea.startswith(f"Del 15/01/2026 al 15/04/2026: {NO_COMPARABLE.lower()}: ")
    assert motivo in linea


def test_cambio_de_version_del_score_no_es_comparable() -> None:
    serie = _serie(_medicion("S-1", T1, 10), _medicion("S-2", T2, 10))
    a, b = serie.puntos
    otro = b.model_copy(update={"score_version": "2.0"})
    comp = comparabilidad(a, otro)
    assert not comp.comparable
    assert comp.motivos == ["Cambia la versión del score (1.0 → 2.0)."]


def test_cambio_de_modelo_sigue_comparable_con_aviso() -> None:
    serie = _serie(
        _medicion("S-1", T1, 10, modelo="gpt-4o"), _medicion("S-2", T2, 10, modelo="gpt-5")
    )
    a, b = serie.puntos
    assert a.modelos_motor == {"ChatGPT": "gpt-4o", "Gemini": "gpt-4o"}
    assert b.comparable_con_anterior
    assert any("El modelo de ChatGPT cambia (gpt-4o → gpt-5)" in x for x in b.avisos)
    assert serie.cambios  # se compara igualmente


def test_modelo_que_no_consta_en_una_medicion_da_aviso() -> None:
    serie = _serie(_medicion("S-1", T1, 10), _medicion("S-2", T2, 10, modelo="gpt-5"))
    b = serie.puntos[1]
    assert b.comparable_con_anterior
    assert any("No consta el modelo de ChatGPT" in x for x in b.avisos)


# --- Orden y línea base ---------------------------------------------------------------------------


def test_ordena_por_fecha_y_la_primera_es_linea_base() -> None:
    serie = _serie(_medicion("S-3", T3, 12), _medicion("S-1", T1, 10), _medicion("S-2", T2, 11))
    assert [p.study_id for p in serie.puntos] == ["S-1", "S-2", "S-3"]
    base = serie.puntos[0]
    assert not base.comparable_con_anterior
    assert base.motivos_no_comparable == [MOTIVO_LINEA_BASE]
    assert {(c.desde_study_id, c.hasta_study_id) for c in serie.cambios} == {
        ("S-1", "S-2"),
        ("S-2", "S-3"),
    }


def test_punto_con_score_intervalo_posicion_y_competidores() -> None:
    serie = _serie(_medicion("S-1", T1, 8, apariciones_rival=20))
    p = serie.puntos[0]
    assert p.score is not None and p.intervalo is not None
    assert p.intervalo.inf <= p.score <= p.intervalo.sup
    assert (p.posicion, p.n_marcas) == (2, 2)
    assert p.score_medio_competidores is not None
    assert p.diferencia_vs_competidores == round(p.score - p.score_medio_competidores, 2)
    assert p.motores == ["ChatGPT", "Gemini"]
    assert p.banco_prompts == huella_banco(PROMPTS)


# --- Cambios --------------------------------------------------------------------------------------


def test_cambio_significativo_entra_en_el_resumen() -> None:
    serie = _serie(_medicion("S-1", T1, 6), _medicion("S-2", T2, 34))
    por_metrica = {c.metrica: c for c in serie.cambios}
    score = por_metrica["score"]
    assert score.significativo and score.delta > 0
    assert por_metrica["aparicion_espontanea:global"].significativo
    assert {"aparicion_espontanea:ChatGPT", "aparicion_espontanea:Gemini"} <= set(por_metrica)
    assert por_metrica["posicion"].delta == -1  # del 2.º al 1.º
    assert por_metrica["posicion"].relativo_a_competidores
    dif = por_metrica["diferencia_vs_competidores"]
    assert dif.relativo_a_competidores and dif.significativo and dif.significancia is not None
    assert all(c.significativo for c in serie.cambios_significativos)
    assert serie.resumen == [c.texto for c in serie.cambios_significativos]
    assert score.texto in serie.resumen
    assert "Sale del margen de error" in score.texto


def test_cambio_dentro_del_margen_no_se_informa() -> None:
    serie = _serie(_medicion("S-1", T1, 20), _medicion("S-2", T2, 21))
    assert serie.cambios  # se calculan...
    assert not any(c.significativo for c in serie.cambios)  # ...pero ninguno sale del margen
    assert serie.cambios_significativos == []
    assert serie.resumen == [SIN_CAMBIOS]
    score = next(c for c in serie.cambios if c.metrica == "score")
    assert "dentro del margen de error" in score.texto


def test_textos_en_espanol_con_coma_decimal() -> None:
    serie = _serie(_medicion("S-1", T1, 6), _medicion("S-2", T2, 34))
    for c in serie.cambios:
        assert not re.search(r"\d\.\d", c.texto.replace(".º", "")), c.texto
        assert c.texto.startswith("Del 15/01/2026 al 15/04/2026: ")


def test_determinista() -> None:
    a = _serie(_medicion("S-1", T1, 6), _medicion("S-2", T2, 20))
    b = _serie(_medicion("S-1", T1, 6), _medicion("S-2", T2, 20))
    assert a == b


# --- Indicadores ----------------------------------------------------------------------------------


def test_indicadores_none_sin_datos() -> None:
    serie = _serie(_medicion("S-1", T1, 10), _medicion("S-2", T2, 12))
    claves = [i.clave for i in serie.indicadores]
    assert claves == ["cuota_web_propia", "presencia_top_fuentes", "inexactitudes", "a_revisar"]
    for ind in serie.indicadores:
        assert [v.study_id for v in ind.valores] == ["S-1", "S-2"]
        assert all(v.valor is None for v in ind.valores)


def test_indicadores_con_datos() -> None:
    exactitud = HallazgoExactitud(
        id="EXACT-alborada",
        study_id="S-1",
        brand_id=FOCO,
        afirmaciones=[],
        verificaciones=[],
        n_correctas=0,
        n_incorrectas=0,
        n_no_verificables=0,
        n_riesgo_regulatorio=0,
        evaluation_ids=[],
    )
    serie = _serie(_medicion("S-1", T1, 10, market=MERCADO, exactitud=exactitud))
    valores = {i.clave: i.valores[0].valor for i in serie.indicadores}
    # Cada respuesta cita alborada.example y rankingclinicas: la mitad va a la web propia.
    assert valores["cuota_web_propia"] == 0.5
    # Solo hay una fuente ganada (rankingclinicas) y la citan todas las respuestas.
    assert valores["presencia_top_fuentes"] == 1.0
    assert (valores["inexactitudes"], valores["a_revisar"]) == (0.0, 0.0)


# --- Validaciones ---------------------------------------------------------------------------------


def test_rechaza_estudios_repetidos_y_de_otra_marca() -> None:
    m = _medicion("S-1", T1, 10)
    with pytest.raises(ValueError, match="repetidos"):
        _serie(m, m)
    with pytest.raises(ValueError, match="de la marca"):
        construir_serie("otra", "Otra", [m], replicas=REPLICAS)


def test_rechaza_muestra_de_otro_estudio() -> None:
    m = _medicion("S-1", T1, 10)
    ajena = MedicionSerie(
        m.study.model_copy(update={"id": "S-9"}),
        m.metrics.model_copy(update={"study_id": "S-9"}),
        m.muestra,
    )
    with pytest.raises(ValueError, match="otros estudios"):
        _serie(ajena)


def test_esquemas_rechazan_incoherencias() -> None:
    s = Significancia(
        delta=1.0,
        intervalo=Intervalo(valor=1.0, inf=-1.0, sup=3.0, n=10, metodo="bootstrap"),
        significativa=False,
    )
    with pytest.raises(ValueError, match="significativo"):
        CambioSerie(
            desde_study_id="S-1",
            hasta_study_id="S-2",
            metrica="score",
            delta=1.0,
            significancia=s,
            significativo=True,
            texto="x",
        )
    with pytest.raises(ValueError, match="significativo"):
        CambioSerie(
            desde_study_id="S-1",
            hasta_study_id="S-2",
            metrica="posicion",
            delta=1.0,
            significancia=None,
            significativo=True,
            texto="x",
        )
    serie = _serie(_medicion("S-1", T1, 10), _medicion("S-2", T2, 12))
    with pytest.raises(ValueError, match="ordenados por fecha"):
        SerieMarca.model_validate(
            serie.model_dump() | {"puntos": list(reversed(serie.model_dump()["puntos"]))}
        )


def test_marca_que_no_aparece_tiene_score_cero_no_none() -> None:
    serie = _serie(_medicion("S-1", T1, 0), _medicion("S-2", T2, 0))
    p = serie.puntos[0]
    # Con 0 apariciones el score es 0 (hay población), no None: se mide, pero no aparece.
    assert p.score == 0 and p.posicion == 2
    assert serie.resumen == [SIN_CAMBIOS]


# --- Resumen: línea base, no comparable y sin cambios ---------------------------------------------


def test_un_solo_punto_es_linea_base_no_sin_cambios() -> None:
    serie = _serie(_medicion("S-1", T1, 10))
    assert serie.cambios == []
    assert serie.resumen == [RESUMEN_LINEA_BASE]
    assert construir_serie(FOCO, "x", [], replicas=REPLICAS).resumen == [RESUMEN_SIN_MEDICIONES]


def test_no_comparable_y_luego_sin_cambios() -> None:
    # S-1 → S-2 no comparable (otra metodología); S-2 → S-3 comparable y sin cambios reales.
    serie = _serie(
        _medicion("S-1", T1, 10),
        _medicion("S-2", T2, 10, version_metodologia="metodo-2"),
        _medicion("S-3", T3, 10, version_metodologia="metodo-2"),
    )
    assert serie.cambios and not serie.cambios_significativos
    assert serie.resumen[0].startswith(f"Del 15/01/2026 al 15/04/2026: {NO_COMPARABLE.lower()}")
    assert serie.resumen[1:] == [SIN_CAMBIOS_COMPARABLES]


# --- Cambio de competidores -----------------------------------------------------------------------


def test_cambio_de_competidores_no_compara_puesto_ni_diferencia() -> None:
    # Mismas respuestas para la marca: el score es idéntico, pero entra una tercera marca que no
    # aparece nunca. Antes salía un cambio «fuera del margen» en la diferencia vs competidores.
    serie = _serie(
        _medicion("S-1", T1, 10),
        _medicion("S-2", T2, 10, mercado_metricas=MERCADO_AMPLIO),
    )
    a, b = serie.puntos
    assert a.marcas_mercado == [FOCO, RIVAL]
    assert b.marcas_mercado == [FOCO, RIVAL, TERCERA]
    assert a.score == b.score
    assert a.diferencia_vs_competidores != b.diferencia_vs_competidores
    # Score y aparición siguen siendo comparables...
    assert b.comparable_con_anterior and b.motivos_no_comparable == []
    metricas = {c.metrica for c in serie.cambios}
    assert "score" in metricas and "aparicion_espontanea:global" in metricas
    # ...pero puesto y diferencia frente a competidores no se calculan como cambio.
    assert not b.competidores_comparables
    assert not {"posicion", "diferencia_vs_competidores"} & metricas
    assert not any(c.relativo_a_competidores for c in serie.cambios)
    assert serie.cambios_significativos == []
    motivo = next(x for x in b.avisos if x.startswith(f"{MOTIVO_COMPETIDORES}: "))
    assert "entran tercera" in motivo and "(2 → 3 marcas)" in motivo
    assert serie.resumen == [f"Del 15/01/2026 al 15/04/2026: {motivo}", SIN_CAMBIOS_COMPARABLES]
    comp = comparabilidad(a, b)
    assert comp.comparable and not comp.competidores_comparables
    assert comp.motivos_competidores == [motivo]


def test_mismo_mercado_compara_competidores() -> None:
    serie = _serie(_medicion("S-1", T1, 10), _medicion("S-2", T2, 10))
    b = serie.puntos[1]
    assert b.competidores_comparables
    assert {"posicion", "diferencia_vs_competidores"} <= {c.metrica for c in serie.cambios}
    # Si en un punto no consta el mercado (lista vacía), no se puede decir que cambie.
    sin_mercado = b.model_copy(update={"marcas_mercado": []})
    assert comparabilidad(serie.puntos[0], sin_mercado).competidores_comparables
