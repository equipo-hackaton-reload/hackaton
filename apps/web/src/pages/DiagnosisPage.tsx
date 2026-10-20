import { Link } from "react-router-dom";
import { FindingsList } from "../components/FindingsList";
import { KitNotice } from "../components/KitNotice";
import { PageTitle } from "../components/PageTitle";
import { RankingChart } from "../components/RankingChart";
import { ScoreCard } from "../components/ScoreCard";
import { SourcesPanel } from "../components/SourcesPanel";
import { Waiting } from "../components/States";
import { VisibilityTables } from "../components/VisibilityTables";
import { fmtNum, ordinal } from "../lib/format";
import { nombres, scoreDe } from "../lib/study";
import { useStudyContext } from "./studyContext";

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
          status.plan && (
            <Link to={`/studies/${id}/plan`} className="btn-primary">
              {status.revision_pendiente === "plan" ? "Revisar el plan" : "Ver el plan"}
            </Link>
          )
        }
      >
        {kit && <KitNotice />}
      </PageTitle>

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
