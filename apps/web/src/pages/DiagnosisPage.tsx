import { Link } from "react-router-dom";
import { FindingsList } from "../components/FindingsList";
import { KitNotice } from "../components/KitNotice";
import { PageTitle } from "../components/PageTitle";
import { RankingChart } from "../components/RankingChart";
import { RemeasureButton } from "../components/RemeasureButton";
import { ScoreCard } from "../components/ScoreCard";
import { SourcesPanel } from "../components/SourcesPanel";
import { Waiting } from "../components/States";
import { VisibilityTables } from "../components/VisibilityTables";
import { fmtNum, ordinal } from "../lib/format";
import { nombres, scoreDe } from "../lib/study";
import type { MetricsDelta } from "../types/schemas";
import { useStudyContext } from "./studyContext";

/** Signo, flecha y color a la vez: el sentido del cambio no depende solo del tono. Sin cambio, neutro. */
function DeltaValor({ valor }: { valor: number | null }) {
  if (valor == null) return <p className="num mt-1 text-xl font-semibold text-muted">—</p>;
  const sube = valor > 0;
  const baja = valor < 0;
  const tono = sube ? "text-pill-pos-ink" : baja ? "text-pill-neg-ink" : "text-muted";
  return (
    <p className={`num mt-1 flex items-center gap-1.5 text-xl font-semibold ${tono}`}>
      <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d={sube ? "M8 13V3M4 7l4-4 4 4" : baja ? "M8 3v10M4 9l4 4 4-4" : "M3 8h10"} />
      </svg>
      {`${sube ? "+" : ""}${fmtNum(valor, 2)} pts`}
      <span className="sr-only">{sube ? "(sube)" : baja ? "(baja)" : "(sin cambio)"}</span>
    </p>
  );
}

function DeltaPanel({ delta }: { delta: MetricsDelta }) {
  return (
    <section aria-labelledby="delta-titulo" className="mb-6 rounded-card bg-raised px-5 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="delta-titulo" className="font-semibold">Delta frente a la medición anterior</h2>
        <span className="text-meta text-muted">{delta.comparable ? "Comparación válida" : "Comparación orientativa"}</span>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-meta text-muted">Score anterior</p>
          <p className="num mt-1 text-xl">{fmtNum(delta.score_anterior, 2)}</p>
        </div>
        <div>
          <p className="text-meta text-muted">Score actual</p>
          <p className="num mt-1 text-xl">{fmtNum(delta.score_actual, 2)}</p>
        </div>
        <div>
          <p className="text-meta text-muted">Cambio</p>
          <DeltaValor valor={delta.score_delta} />
        </div>
      </div>
      {delta.avisos.length > 0 && <p className="mt-4 text-meta text-muted">{delta.avisos.join(" ")}</p>}
    </section>
  );
}

export function DiagnosisPage() {
  const { id, status } = useStudyContext();
  const { metrics, findings, market } = status;
  const kit = status.study.modo === "kit";

  if (!metrics || !findings) {
    return (
      <>
        <PageTitle title="Diagnóstico" subtitle="Midiendo la visibilidad de la marca y de sus competidores." />
        <Waiting
          title="Midiendo"
          detail={
            kit
              ? "Lee las 624 respuestas del kit, el juez evalúa cada marca en cada respuesta y el dominio calcula el Score de Citación y los hallazgos."
              : "Pregunta a los cuatro motores, el juez evalúa cada marca en cada respuesta y el dominio calcula el Score de Citación y los hallazgos."
          }
        />
      </>
    );
  }

  const nombre = nombres(market);
  const puesto = metrics.ranking.indexOf(metrics.marca_foco_id) + 1;
  const foco = metrics.score_global.score;
  const lider = scoreDe(metrics, metrics.lider_id);
  const nombreLider = metrics.lider_id ? nombre(metrics.lider_id) : "—";
  const resumen =
    puesto > 0 && foco != null && lider != null && metrics.lider_id !== metrics.marca_foco_id
      ? `${ordinal(puesto)} de ${metrics.ranking.length} marcas, a ${fmtNum(lider - foco)} puntos de ${nombreLider}.`
      : `Score de Citación de ${fmtNum(foco)} sobre 100.`;

  return (
    <>
      <PageTitle
        title="Diagnóstico"
        subtitle={resumen}
        actions={
          <div className="flex flex-wrap gap-2">
            {status.plan && (
              <Link to={`/studies/${id}/plan`} className="btn-primary">
                {status.revision_pendiente === "plan" ? "Revisar el plan" : "Ver el plan"}
              </Link>
            )}
            {status.estado === "completado" && <RemeasureButton studyId={id} />}
            <Link to={`/marcas/${encodeURIComponent(status.study.brand_id)}`} className="btn-ghost">
              Ver el seguimiento
            </Link>
          </div>
        }
      >
        {kit && <KitNotice />}
      </PageTitle>

      {status.metrics_delta && <DeltaPanel delta={status.metrics_delta} />}

      <div className="grid gap-6">
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <ScoreCard metrics={metrics} nombre={nombre} />
          <RankingChart metrics={metrics} nombre={nombre} />
        </div>
        <FindingsList studyId={id} findings={findings} marcas={market?.marcas ?? []} />
        <VisibilityTables metrics={metrics} ciudades={status.brief?.ciudades ?? []} nombreLider={nombreLider} />
        <SourcesPanel metrics={metrics} nombreLider={nombreLider} />
      </div>
    </>
  );
}
