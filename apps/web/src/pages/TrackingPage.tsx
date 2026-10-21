import { Link, useParams } from "react-router-dom";
import { useSerie } from "../api/hooks";
import { AppShell } from "../components/AppShell";
import { PageTitle } from "../components/PageTitle";
import { Panel } from "../components/Panel";
import { RemeasureButton } from "../components/RemeasureButton";
import { SerieChart } from "../components/SerieChart";
import { rutaNoDisponible } from "../api/client";
import { ErrorState, Skeleton } from "../components/States";
import { fmtDay, fmtNum, fmtSigned, fmtUnidad, ordinal } from "../lib/format";
import { SIN_CAMBIOS, type CambioSerie, type SerieMarca } from "../types/tracking";

/**
 * Nombre y unidad de `CambioSerie.metrica` (domain/tracking_schemas.py): el delta va en puntos de
 * score, en fracción para las tasas de aparición y en puestos para la posición.
 */
function metrica(clave: string): { nombre: string; fmt: (n: number) => string } {
  const pts = (n: number) => `${fmtSigned(n)} pts`;
  if (clave === "score" || clave === "score_global") return { nombre: "Score", fmt: pts };
  if (clave === "diferencia_vs_competidores") return { nombre: "Diferencia con competidores", fmt: pts };
  if (clave === "posicion") return { nombre: "Puesto", fmt: (n) => `${fmtSigned(n, 0)} puestos` };
  if (clave.startsWith("aparicion_espontanea")) {
    const ambito = clave.split(":")[1];
    return {
      nombre: `Aparición espontánea${ambito && ambito !== "global" ? ` en ${ambito}` : ""}`,
      fmt: (n) => `${fmtSigned(n * 100, 1)} pp`,
    };
  }
  return { nombre: clave, fmt: (n) => fmtSigned(n) };
}

function Cambio({ c, fechas }: { c: CambioSerie; fechas: Map<string, string> }) {
  const sube = c.delta > 0;
  // En la posición, bajar de puesto (delta negativo) es mejorar.
  const mejora = c.metrica === "posicion" ? c.delta < 0 : sube;
  const tono = c.delta === 0 ? "text-muted" : mejora ? "text-pill-pos-ink" : "text-pill-neg-ink";
  const ic = c.significancia?.intervalo;
  const m = metrica(c.metrica);
  const desde = fechas.get(c.desde_study_id);
  const hasta = fechas.get(c.hasta_study_id);
  return (
    <li className="flex gap-3 border-t border-rule px-5 py-3 first:border-t-0" data-testid="cambio-significativo">
      <span aria-hidden className={`num mt-0.5 flex-none font-semibold ${tono}`}>
        {sube ? "▲" : c.delta < 0 ? "▼" : "■"}
      </span>
      <div className="min-w-0">
        <p>{c.texto}</p>
        <p className="num mt-0.5 text-meta text-muted">
          {m.nombre} {m.fmt(c.delta)}
          {ic && ` · IC ${fmtNum(ic.nivel * 100, 0)} % del cambio: ${m.fmt(ic.inf)} a ${m.fmt(ic.sup)}`}
          {desde && hasta && ` · ${desde} → ${hasta}`}
          {c.relativo_a_competidores && (
            <span className="pill ml-2 bg-raised text-muted">frente a competidores</span>
          )}
        </p>
      </div>
    </li>
  );
}

function Mediciones({ serie }: { serie: SerieMarca }) {
  return (
    <Panel title="Mediciones" id="mediciones" flush meta={<span>Cada fila es un estudio completado</span>}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-body" data-testid="tabla-mediciones">
          <caption className="sr-only">Mediciones de {serie.nombre}</caption>
          <thead>
            <tr className="text-meta text-muted">
              <th scope="col" className="px-5 pb-2 text-left font-normal">Fecha</th>
              <th scope="col" className="pb-2 text-right font-normal">Score</th>
              <th scope="col" className="pb-2 text-right font-normal">Intervalo</th>
              <th scope="col" className="pb-2 text-right font-normal">Puesto</th>
              <th scope="col" className="pb-2 text-right font-normal">Media comp.</th>
              <th scope="col" className="pb-2 text-right font-normal">Diferencia</th>
              <th scope="col" className="px-5 pb-2 text-left font-normal">Comparable</th>
            </tr>
          </thead>
          <tbody>
            {serie.puntos.map((p, i) => (
              <tr key={p.study_id} className="border-t border-rule align-top">
                <th scope="row" className="px-5 py-2.5 text-left font-normal">
                  <Link to={`/studies/${encodeURIComponent(p.study_id)}/diagnostico`} className="underline decoration-[var(--control)] underline-offset-2 hover:decoration-current">
                    {fmtDay(p.fecha)}
                  </Link>
                  <span className="block text-meta text-faint">
                    método {p.version_metodologia} · score {p.score_version}
                  </span>
                </th>
                <td className="num py-2.5 text-right font-medium">{fmtNum(p.score)}</td>
                <td className="num py-2.5 text-right text-muted">
                  {p.intervalo ? `${fmtNum(p.intervalo.inf)} – ${fmtNum(p.intervalo.sup)}` : "—"}
                </td>
                <td className="num py-2.5 text-right">{p.posicion ? `${ordinal(p.posicion)} de ${p.n_marcas}` : "—"}</td>
                <td className="num py-2.5 text-right text-muted">{fmtNum(p.score_medio_competidores)}</td>
                <td className="num py-2.5 text-right">{fmtSigned(p.diferencia_vs_competidores)}</td>
                <td className="px-5 py-2.5 text-meta">
                  {i === 0 ? (
                    <span className="text-muted">Línea base</span>
                  ) : p.comparable_con_anterior ? (
                    <span className="text-pill-pos-ink">Sí</span>
                  ) : (
                    <span className="text-pill-warn-ink" data-testid="motivo-no-comparable">
                      No: {p.motivos_no_comparable.join("; ")}
                    </span>
                  )}
                  {p.avisos.length > 0 && <span className="mt-0.5 block text-muted">{p.avisos.join(" ")}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Indicadores({ serie }: { serie: SerieMarca }) {
  if (serie.indicadores.length === 0) return null;
  return (
    <Panel
      title="Indicadores adelantados"
      id="indicadores"
      flush
      meta={<span>Se mueven antes que el score: sirven para re-priorizar el plan entre mediciones</span>}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-body" data-testid="tabla-indicadores">
          <caption className="sr-only">Indicadores adelantados por medición</caption>
          <thead>
            <tr className="text-meta text-muted">
              <th scope="col" className="px-5 pb-2 text-left font-normal">Indicador</th>
              {serie.puntos.map((p) => (
                <th key={p.study_id} scope="col" className="pb-2 pr-5 text-right font-normal">
                  {fmtDay(p.fecha)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="num">
            {serie.indicadores.map((ind) => {
              const porEstudio = new Map(ind.valores.map((v) => [v.study_id, v.valor]));
              return (
                <tr key={ind.clave} className="border-t border-rule">
                  <th scope="row" className="px-5 py-2.5 text-left font-normal">{ind.nombre}</th>
                  {serie.puntos.map((p) => (
                    <td key={p.study_id} className="py-2.5 pr-5 text-right">
                      {fmtUnidad(porEstudio.get(p.study_id), ind.unidad)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/** Seguimiento de una marca: la serie de mediciones con sus intervalos y solo los cambios significativos. */
export function TrackingPage() {
  const { brandId = "" } = useParams();
  const q = useSerie(brandId);

  if (q.isPending) {
    return (
      <AppShell>
        <div className="space-y-4" aria-busy="true" aria-label="Cargando el seguimiento">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-64 w-full" />
        </div>
      </AppShell>
    );
  }
  if (q.isError) {
    return (
      <AppShell>
        <ErrorState
          error={q.error}
          titulo={rutaNoDisponible(q.error) ? "Seguimiento no disponible todavía" : "No se pudo cargar el seguimiento"}
          noEncontrado="No tienes ninguna marca con ese identificador."
          noDisponible="Esta API todavía no ofrece la serie de mediciones por marca (GET /brands/{id}/serie). El estudio sigue disponible; la serie aparecerá aquí cuando la API la publique."
        >
          <div className="flex flex-wrap gap-2">
            {rutaNoDisponible(q.error) ? (
              <Link to="/" className="btn-secondary">Nuevo estudio</Link>
            ) : (
              <>
                <button type="button" className="btn-secondary" onClick={() => q.refetch()}>
                  Reintentar
                </button>
                <Link to="/marcas" className="btn-ghost">Volver a mis marcas</Link>
              </>
            )}
          </div>
        </ErrorState>
      </AppShell>
    );
  }

  const serie = q.data;
  const ultimo = serie.puntos[serie.puntos.length - 1];
  const fechas = new Map(serie.puntos.map((p) => [p.study_id, fmtDay(p.fecha)]));
  const significativos = serie.cambios_significativos;

  return (
    <AppShell>
      <PageTitle
        title={serie.nombre}
        subtitle={
          ultimo
            ? `${serie.puntos.length} ${serie.puntos.length === 1 ? "medición" : "mediciones"} · última el ${fmtDay(ultimo.fecha)}`
            : "Aún no hay mediciones completadas."
        }
        actions={
          ultimo && (
            <>
              <Link to={`/studies/${encodeURIComponent(ultimo.study_id)}/diagnostico`} className="btn-ghost">
                Abrir la última medición
              </Link>
              <RemeasureButton studyId={ultimo.study_id} className="btn-primary" />
            </>
          )
        }
      >
        <Link to="/marcas" className="text-meta text-muted underline hover:text-ink">← Todas tus marcas</Link>
      </PageTitle>

      {serie.puntos.length === 0 ? (
        <div className="panel px-5 py-6 text-muted">
          Cuando un estudio de esta marca se complete, aparecerá aquí como línea base.
        </div>
      ) : (
        <div className="grid gap-6">
          <section aria-labelledby="resumen-titulo" className="rounded-card bg-raised px-5 py-4" data-testid="resumen-serie">
            <h2 id="resumen-titulo" className="font-semibold">Qué ha cambiado</h2>
            <ul className="mt-1.5 space-y-1">
              {(serie.resumen.length ? serie.resumen : [SIN_CAMBIOS]).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </section>

          <Panel title="Score de Citación en el tiempo" id="serie">
            <SerieChart puntos={serie.puntos} nombre={serie.nombre} />
          </Panel>

          <Panel
            title="Cambios fuera del margen de error"
            id="cambios"
            flush
            meta={<span className="num">{significativos.length} de {serie.cambios.length} cambios entre mediciones comparables</span>}
          >
            {significativos.length === 0 ? (
              <p className="px-5 pb-3 text-muted" data-testid="sin-cambios">{SIN_CAMBIOS}.</p>
            ) : (
              <ul>
                {significativos.map((c) => (
                  <Cambio key={`${c.desde_study_id}-${c.hasta_study_id}-${c.metrica}`} c={c} fechas={fechas} />
                ))}
              </ul>
            )}
          </Panel>

          <Mediciones serie={serie} />
          <Indicadores serie={serie} />
        </div>
      )}
    </AppShell>
  );
}
