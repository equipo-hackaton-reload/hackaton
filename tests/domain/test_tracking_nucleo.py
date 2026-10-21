"""Serie temporal (ADR 0016): juez, núcleo común del banco y configuración versionada.

Mediciones SINTÉTICAS (las de `test_tracking`): marcas inventadas con apariciones fijadas a mano.
No son datos del reto.
"""

from dataclasses import replace
from datetime import datetime

import pytest
from pydantic import ValidationError

from posiq.domain.schemas import Market, Trace
from posiq.domain.tracking import (
    MOTIVO_BANCO,
    MOTIVO_COMPETIDORES,
    MOTIVO_JUEZ,
    MedicionSerie,
    clave_pregunta,
    comparabilidad,
    exactitud_con_perfil,
    exactitud_en_fecha,
    juez_medicion,
    restringir_a_preguntas,
    vigente_en,
)
from posiq.domain.tracking_schemas import (
    CambioConfiguracion,
    NucleoComun,
    VersionMercado,
    VersionPerfil,
)
from tests.domain import factories as f
from tests.domain.test_tracking import MARCAS, PROMPTS, T1, T2, T3, _medicion, _serie


def _traza(study_id: str, nodo: str, modelo: str) -> Trace:
    return Trace(
        study_id=study_id,
        nodo=nodo,
        modelo=modelo,
        prompt_version="v1",
        tokens_in=0,
        tokens_out=0,
        coste_eur=0.0,
        duracion_ms=0,
        fecha=T1,
    )


def _con_origen(med: MedicionSerie, origenes: dict[int, str]) -> MedicionSerie:
    """La medición con el `origen` de algunas evaluaciones (por índice) cambiado."""
    evals = [
        e.model_copy(update={"origen": origenes[i]}) if i in origenes else e
        for i, e in enumerate(med.muestra.evaluations)
    ]
    return replace(med, muestra=replace(med.muestra, evaluations=evals))


# --- Juez -----------------------------------------------------------------------------------------


def test_juez_declarado_trazas_y_origen() -> None:
    med = _medicion("S-1", T1, 10)
    # Sin trazas ni juez declarado: las etiquetas de los tests son humanas.
    assert juez_medicion(med) == "humano"
    # Que una persona revise alguna evaluación de Jev no cambia el juez.
    assert juez_medicion(_con_origen(med, {0: "jev"})) == "jev"
    todas_reglas = {i: "fallback" for i in range(len(med.muestra.evaluations))}
    assert juez_medicion(_con_origen(med, todas_reglas)) == "reglas"
    # Las trazas del juez (`judge:<proveedor>`) mandan sobre el origen; las de otros nodos o de
    # otros estudios no cuentan.
    trazas = [
        _traza("S-1", "judge:jev", "jev-1.13"),
        _traza("S-1", "judge:jev", "jev-1.13"),
        _traza("S-1", "plan_guard:jev", "jev-1.13"),
        _traza("S-1", "run:openai", "gpt-5"),
        _traza("S-9", "judge:deepseek", "deepseek-chat"),
    ]
    assert juez_medicion(replace(med, trazas=trazas)) == "jev/jev-1.13"
    consenso = [*trazas, _traza("S-1", "judge:llm", "deepseek-chat")]
    assert juez_medicion(replace(med, trazas=consenso)) == "jev/jev-1.13 + llm/deepseek-chat"
    # Lo declarado manda sobre todo.
    assert juez_medicion(replace(med, juez="jev/jev-1.14", trazas=trazas)) == "jev/jev-1.14"
    vacia = replace(med, muestra=replace(med.muestra, evaluations=[]))
    assert juez_medicion(vacia) is None


def test_cambio_de_juez_no_es_comparable() -> None:
    serie = _serie(
        replace(_medicion("S-1", T1, 10), juez="jev/jev-1.13"),
        replace(_medicion("S-2", T2, 10), juez="llm/deepseek-chat"),
    )
    a, b = serie.puntos
    assert a.juez == "jev/jev-1.13" and b.juez == "llm/deepseek-chat"
    assert not b.comparable_con_anterior
    assert b.motivos_no_comparable == [f"{MOTIVO_JUEZ} (jev/jev-1.13 → llm/deepseek-chat)."]
    assert serie.cambios == []
    assert MOTIVO_JUEZ in serie.resumen[0]


def test_mismo_juez_comparable_y_juez_que_no_consta_da_aviso() -> None:
    serie = _serie(
        replace(_medicion("S-1", T1, 10), juez="jev/jev-1.13"),
        replace(_medicion("S-2", T2, 10), juez="jev/jev-1.13"),
    )
    a, b = serie.puntos
    assert b.comparable_con_anterior and serie.cambios
    sin_juez = b.model_copy(update={"juez": None})
    comp = comparabilidad(a, sin_juez)
    assert comp.comparable
    assert any("No consta el juez" in x for x in comp.avisos)


# --- Núcleo común del banco -----------------------------------------------------------------------


NUEVA = f.prompt(
    "P-3", instanciacion="ciudad", ciudad="Valencia", texto="¿Mejor clínica de ojos en Valencia?"
)
RENOMBRADOS = [p.model_copy(update={"id": f"Q-{p.id}"}) for p in PROMPTS]
"""Las mismas preguntas con otros ids de instancia: siguen siendo las mismas (`clave_pregunta`)."""


def test_clave_pregunta_ignora_el_id_y_no_el_texto() -> None:
    assert clave_pregunta(RENOMBRADOS[0]) == clave_pregunta(PROMPTS[0])
    otra = PROMPTS[0].model_copy(update={"texto": "Otra cosa"})
    assert clave_pregunta(otra) != clave_pregunta(PROMPTS[0])


def test_banco_ampliado_se_compara_sobre_el_nucleo_comun() -> None:
    antes = _medicion("S-1", T1, 5)
    despues = _medicion("S-2", T2, 35, prompts=[*RENOMBRADOS, NUEVA])
    serie = _serie(antes, despues)
    a, b = serie.puntos
    assert a.banco_prompts != b.banco_prompts
    # Comparable sobre el núcleo común, con aviso; el score del banco completo se informa aparte.
    assert b.comparable_con_anterior and b.motivos_no_comparable == []
    aviso = next(x for x in b.avisos if x.startswith(MOTIVO_BANCO))
    assert "2 preguntas comunes" in aviso and "banco completo se informa aparte" in aviso
    nucleo = b.nucleo_comun
    assert nucleo is not None
    assert nucleo.n_prompts_comunes == 2
    assert (nucleo.n_prompts_anterior, nucleo.n_prompts_actual) == (2, 3)
    # El anterior tenía exactamente el núcleo: su score sobre el núcleo es su score.
    assert nucleo.score_anterior == a.score
    # El actual, sobre el núcleo, no es el del banco completo.
    claves = {clave_pregunta(p) for p in PROMPTS}
    recortada = restringir_a_preguntas(despues, claves)
    assert {p.id for p in recortada.muestra.prompts} == {"Q-P-1", "Q-P-2"}
    assert nucleo.score_actual == recortada.metrics.score_global.score
    assert nucleo.score_actual != b.score
    # Todos los cambios se calcularon sobre el núcleo y lo dicen.
    assert serie.cambios and all(c.sobre_nucleo_comun for c in serie.cambios)
    assert all("(núcleo común de 2 preguntas)" in c.texto for c in serie.cambios)
    score = next(c for c in serie.cambios if c.metrica == "score")
    assert score.significativo
    assert nucleo.score_actual is not None and nucleo.score_anterior is not None
    assert score.delta == pytest.approx(nucleo.score_actual - nucleo.score_anterior, abs=0.01)
    assert serie.resumen[0] == f"Del 15/01/2026 al 15/04/2026: {aviso}"
    assert any("núcleo común" in x for x in serie.resumen[1:])


def test_mismo_banco_no_tiene_nucleo_ni_marca_cambios() -> None:
    serie = _serie(_medicion("S-1", T1, 10), _medicion("S-2", T2, 10, prompts=RENOMBRADOS))
    b = serie.puntos[1]
    assert b.nucleo_comun is None and b.comparable_con_anterior
    assert not any(c.sobre_nucleo_comun for c in serie.cambios)
    assert not any(x.startswith(MOTIVO_BANCO) for x in b.avisos)


def test_banco_cambiado_y_otra_metodologia_no_usa_el_nucleo() -> None:
    serie = _serie(
        _medicion("S-1", T1, 5),
        _medicion("S-2", T2, 35, prompts=[*PROMPTS, NUEVA], version_metodologia="metodo-2"),
    )
    b = serie.puntos[1]
    assert not b.comparable_con_anterior and b.nucleo_comun is None
    assert serie.cambios == []
    comp = comparabilidad(serie.puntos[0], b, n_comunes=2)
    assert not comp.comparable and comp.avisos_banco == [] and not comp.nucleo_comun


def test_nucleo_comun_coherente() -> None:
    with pytest.raises(ValidationError):
        NucleoComun(
            huella="sha256:x",
            n_prompts_comunes=3,
            n_prompts_anterior=2,
            n_prompts_actual=3,
            score_anterior=None,
            score_actual=None,
        )
    serie = _serie(_medicion("S-1", T1, 10))
    nucleo = NucleoComun(
        huella="sha256:x",
        n_prompts_comunes=1,
        n_prompts_anterior=1,
        n_prompts_actual=1,
        score_anterior=None,
        score_actual=None,
    )
    # La línea base no se compara con nada: no puede llevar núcleo común.
    datos = serie.puntos[0].model_dump() | {"nucleo_comun": nucleo.model_dump()}
    with pytest.raises(ValidationError, match="núcleo común"):
        type(serie.puntos[0]).model_validate(datos)


# --- Configuración versionada ---------------------------------------------------------------------


def test_cambios_de_configuracion_para_el_grafico() -> None:
    serie = _serie(
        replace(_medicion("S-1", T1, 10), version_perfil="perfil-1", version_mercado="mercado-1"),
        replace(_medicion("S-2", T2, 10), version_perfil="perfil-2", version_mercado="mercado-1"),
        replace(_medicion("S-3", T3, 10), version_perfil="perfil-2", version_mercado="mercado-2"),
    )
    a, b, c = serie.puntos
    assert (a.version_perfil, a.version_mercado) == ("perfil-1", "mercado-1")
    assert [(x.study_id, x.que_cambia) for x in serie.cambios_configuracion] == [
        ("S-2", ["perfil"]),
        ("S-3", ["mercado"]),
    ]
    assert serie.cambios_configuracion[0].texto.startswith("Desde el 15/04/2026 cambia el perfil")
    # Cambio de perfil: no afecta a nada de la comparación.
    assert b.comparable_con_anterior and b.competidores_comparables
    assert {"score", "posicion"} <= {x.metrica for x in serie.cambios if x.hasta_study_id == "S-2"}
    # Cambio de mercado (mismas marcas, otra versión): puesto y diferencia no comparables.
    assert c.comparable_con_anterior and not c.competidores_comparables
    motivo = next(x for x in c.avisos if x.startswith(MOTIVO_COMPETIDORES))
    assert "mercado-1 → mercado-2" in motivo
    del_s3 = {x.metrica for x in serie.cambios if x.hasta_study_id == "S-3"}
    assert "score" in del_s3 and not {"posicion", "diferencia_vs_competidores"} & del_s3


def test_sin_versiones_no_hay_cambios_de_configuracion() -> None:
    serie = _serie(
        replace(_medicion("S-1", T1, 10), version_perfil="perfil-1"),
        _medicion("S-2", T2, 10),
    )
    assert serie.cambios_configuracion == []
    assert serie.puntos[1].competidores_comparables


def test_cambio_de_configuracion_validado() -> None:
    with pytest.raises(ValidationError):
        CambioConfiguracion(study_id="S-1", que_cambia=[], texto="x")
    with pytest.raises(ValidationError):
        CambioConfiguracion(study_id="S-1", que_cambia=["perfil", "perfil"], texto="x")
    serie = _serie(_medicion("S-1", T1, 10))
    datos = serie.model_dump() | {
        "cambios_configuracion": [{"study_id": "S-9", "que_cambia": ["perfil"], "texto": "x"}]
    }
    with pytest.raises(ValidationError, match="fuera de la serie"):
        type(serie).model_validate(datos)


# --- Exactitud contra el perfil vigente -----------------------------------------------------------


PERFIL_1 = VersionPerfil(
    version="perfil-1",
    vigente_desde=datetime(2026, 1, 1),
    perfil=f.brief(servicios_prioritarios=["Cirugía refractiva"]),
)
PERFIL_2 = VersionPerfil(
    version="perfil-2",
    vigente_desde=datetime(2026, 3, 1),
    perfil=f.brief(servicios_prioritarios=["Cirugía refractiva", "Cirugía de cataratas"]),
)


def test_vigente_en() -> None:
    versiones = [PERFIL_2, PERFIL_1]
    assert vigente_en(versiones, datetime(2026, 2, 1)) == PERFIL_1
    assert vigente_en(versiones, datetime(2026, 3, 1)) == PERFIL_2
    assert vigente_en(versiones, datetime(2025, 12, 31)) is None
    mercado = VersionMercado(
        version="m", vigente_desde=datetime(2026, 1, 1), mercado=Market(marcas=MARCAS)
    )
    assert vigente_en([mercado], datetime(2026, 1, 1)) == mercado
    with pytest.raises(ValueError, match="misma fecha"):
        vigente_en([PERFIL_1, PERFIL_1.model_copy(update={"version": "otra"})], T1)


def test_exactitud_contra_el_perfil_vigente_en_la_fecha() -> None:
    marca = MARCAS[0]
    texto = "Clínica Alborada Visión ofrece cirugía de cataratas y cirugía refractiva en Madrid."
    enero = _medicion("S-1", datetime(2026, 2, 1), 10).study
    abril = _medicion("S-2", T2, 10).study
    run_enero = f.run("R-1", texto, study_id="S-1")
    run_abril = f.run("R-2", texto, study_id="S-2")
    versiones = [PERFIL_1, PERFIL_2]
    h_enero, _ = exactitud_en_fecha(enero, marca, versiones, [run_enero])
    h_abril, _ = exactitud_en_fecha(abril, marca, versiones, [run_abril])
    # La misma respuesta se verifica contra el perfil de su fecha: en enero las cataratas no eran
    # un servicio declarado; en abril, sí.
    assert h_enero.study_id == "S-1" and h_abril.study_id == "S-2"
    assert h_enero.n_correctas < h_abril.n_correctas
    assert exactitud_con_perfil(abril, marca, PERFIL_1, [run_abril])[0].n_correctas == (
        h_enero.n_correctas
    )
    with pytest.raises(ValueError, match="posterior a la medición"):
        exactitud_con_perfil(enero, marca, PERFIL_2, [run_enero])
    with pytest.raises(ValueError, match="no hay perfil vigente"):
        exactitud_en_fecha(
            _medicion("S-0", datetime(2025, 6, 1), 10).study, marca, versiones, [run_enero]
        )
