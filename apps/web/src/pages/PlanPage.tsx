import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useResume } from "../api/hooks";
import { ActionEditor } from "../components/ActionEditor";
import { KitNotice } from "../components/KitNotice";
import { PageTitle } from "../components/PageTitle";
import { Panel } from "../components/Panel";
import { PlanQualityCard } from "../components/PlanQualityCard";
import { SimulationCard } from "../components/SimulationCard";
import { Waiting } from "../components/States";
import { fmtEur, fmtNum } from "../lib/format";
import type { Action, Plan } from "../types/schemas";
import { useStudyContext } from "./studyContext";

function Objetivos({ plan }: { plan: Plan }) {
  return (
    <Panel title="Objetivos" id="objetivos" flush>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-body">
          <caption className="sr-only">Objetivos del plan</caption>
          <thead>
            <tr className="text-meta text-muted">
              <th scope="col" className="px-5 pb-2 text-left font-normal">KPI</th>
              <th scope="col" className="pb-2 text-right font-normal">Hoy</th>
              <th scope="col" className="pb-2 text-right font-normal">Objetivo</th>
              <th scope="col" className="px-5 pb-2 text-right font-normal">Plazo</th>
            </tr>
          </thead>
          <tbody className="num">
            {plan.objetivos.map((o) => (
              <tr key={o.kpi} className="border-t border-rule">
                <th scope="row" className="px-5 py-2.5 text-left font-normal">{o.kpi}</th>
                <td className="py-2.5 text-right text-muted">{fmtNum(o.valor_actual, 1)}</td>
                <td className="py-2.5 text-right font-medium">{fmtNum(o.valor_objetivo, 1)}</td>
                <td className="px-5 py-2.5 text-right text-muted">{o.plazo_semanas} sem.</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Editor({ original }: { original: Plan }) {
  const { id, status } = useStudyContext();
  const navigate = useNavigate();
  const resume = useResume(id);
  const pendiente = status.revision_pendiente === "plan";
  const [plan, setPlan] = useState<Plan>(original);
  const findings = useMemo(() => new Map((status.findings ?? []).map((f) => [f.id, f])), [status.findings]);
  const originales = useMemo(() => new Map(original.fases.flatMap((f) => f.acciones).map((a) => [a.id, a])), [original]);
  const restricciones = status.brief?.restricciones ?? [];
  const acciones = plan.fases.flatMap((f) => f.acciones);
  const editadas = acciones.filter((a) => JSON.stringify(a) !== JSON.stringify(originales.get(a.id))).length;
  const semanas = plan.fases.reduce((s, f) => s + f.semanas, 0);
  const rango = status.brief?.presupuesto_anual_eur;

  function cambiar(fase: number, accion: Action) {
    setPlan((p) => ({
      ...p,
      fases: p.fases.map((f, i) =>
        i === fase ? { ...f, acciones: f.acciones.map((a) => (a.id === accion.id ? accion : a)) } : f,
      ),
    }));
  }

  function aprobar() {
    // mutateAsync: el editor se remonta al cambiar el estado y descartaría un onSuccess local.
    resume
      .mutateAsync({ revision: "plan", payload: plan })
      .then(() => navigate(`/studies/${id}/propuesta`))
      .catch(() => undefined);
  }

  return (
    <>
      <PageTitle
        title="Plan de acción"
        subtitle={
          <>
            {plan.fases.length} fases en {semanas} semanas · {acciones.length} acciones · presupuesto estimado{" "}
            <span className="num">{fmtEur(plan.presupuesto_estimado_eur, 0)}</span>
            {rango && (
              <>
                {" "}
                (brief: <span className="num">{fmtEur(rango[0], 0)} – {fmtEur(rango[1], 0)}</span>)
              </>
            )}
          </>
        }
        actions={
          pendiente ? (
            <>
              {editadas > 0 && (
                <span className="text-meta text-muted">
                  {editadas} {editadas === 1 ? "acción editada" : "acciones editadas"}
                </span>
              )}
              <button type="button" className="btn-primary" onClick={aprobar} disabled={resume.isPending}>
                {resume.isPending ? "Aprobando…" : "Aprobar plan"}
              </button>
            </>
          ) : (
            <Link to={`/studies/${id}/propuesta`} className="btn-secondary">
              Ver la propuesta
            </Link>
          )
        }
      >
        {status.study.modo === "kit" && <KitNotice />}
      </PageTitle>

      {resume.isError && (
        <p role="alert" className="mb-6 rounded-control bg-pill-neg-bg px-4 py-3 text-pill-neg-ink">
          {resume.error instanceof ApiError
            ? `La API no aceptó el plan: ${resume.error.message}`
            : "No se pudo enviar el plan a la API."}
        </p>
      )}

      {pendiente && status.errores.length > 0 && (
        <section
          role="alert"
          aria-labelledby="violaciones-titulo"
          className="mb-6 rounded-card border border-pill-warn-line bg-pill-warn-bg px-5 py-4 text-pill-warn-ink"
        >
          <h2 id="violaciones-titulo" className="font-semibold">
            {status.errores.length === 1
              ? "El plan incumple una restricción del brief"
              : `El plan incumple ${status.errores.length} restricciones del brief`}
          </h2>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5" data-testid="violaciones">
            {status.errores.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
          <p className="mt-2 text-meta">
            Corrige la acción o marca la restricción como revisada antes de aprobar. Puedes aprobar igualmente: el
            aviso quedará registrado.
          </p>
        </section>
      )}

      <div className="grid gap-6">
        <Objetivos plan={plan} />
        {status.simulacion && (
          <SimulationCard simulation={status.simulacion} quality={status.calidad_plan} />
        )}
        {status.calidad_plan && <PlanQualityCard quality={status.calidad_plan} />}
        {plan.fases.map((f, i) => (
          <Panel
            key={f.nombre}
            title={f.nombre}
            id={`fase-${i}`}
            meta={<span className="num">{f.semanas} semanas · {f.acciones.length} acciones</span>}
            flush
          >
            <p className="px-5 pb-1 text-muted">{f.objetivo}</p>
            {f.acciones.map((a) => (
              <ActionEditor
                key={a.id}
                action={a}
                original={originales.get(a.id) ?? a}
                findings={findings}
                restricciones={restricciones}
                readOnly={!pendiente}
                onChange={(next) => cambiar(i, next)}
              />
            ))}
          </Panel>
        ))}
      </div>
    </>
  );
}

export function PlanPage() {
  const { status } = useStudyContext();
  if (!status.plan) {
    return (
      <>
        <PageTitle title="Plan de acción" />
        <Waiting
          title="Preparando el plan"
          detail="El plan se redacta a partir de los hallazgos, con las cifras ya calculadas por el dominio. Cada acción enlaza los hallazgos que la justifican."
        />
      </>
    );
  }
  return <Editor key={status.revision_pendiente ?? "cerrado"} original={status.plan} />;
}
