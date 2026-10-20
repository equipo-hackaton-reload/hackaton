import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useStudies } from "../api/hooks";
import { KitNotice } from "../components/KitNotice";
import { PageTitle } from "../components/PageTitle";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { Waiting } from "../components/States";
import { TracesPanel } from "../components/TracesPanel";
import { fmtDate } from "../lib/format";
import type { FormatoExport } from "../types/api";
import { useStudyContext } from "./studyContext";

function Descargas({ id }: { id: string }) {
  const [enCurso, setEnCurso] = useState<FormatoExport | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function descargar(formato: FormatoExport) {
    setEnCurso(formato);
    setError(null);
    try {
      await api.exportProposal(id, formato);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo descargar el fichero.");
    } finally {
      setEnCurso(null);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button type="button" className="btn-secondary" disabled={enCurso !== null} onClick={() => descargar("pdf")}>
          {enCurso === "pdf" ? "Generando…" : "Descargar PDF"}
        </button>
        <button type="button" className="btn-primary" disabled={enCurso !== null} onClick={() => descargar("docx")}>
          {enCurso === "docx" ? "Generando…" : "Descargar Word"}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-meta text-negative">
          {error}
        </p>
      )}
    </div>
  );
}

function Mediciones({ brandId, actual }: { brandId: string; actual: string }) {
  const q = useStudies(brandId);
  const estudios = q.data ?? [];
  return (
    <Panel title="Mediciones de esta marca" id="mediciones" flush>
      {q.isError && <p className="px-5 pb-3 text-muted">La API no ha devuelto el histórico.</p>}
      {q.data && (
        <ul>
          {estudios.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 border-t border-rule px-5 py-2.5 first:border-t-0">
              <div className="min-w-0">
                {s.id === actual ? (
                  <span className="font-medium">Este estudio</span>
                ) : (
                  <Link to={`/studies/${s.id}`} className="font-medium hover:underline">
                    {fmtDate(s.creado_en)}
                  </Link>
                )}
                <p className="text-meta text-muted">
                  {s.id === actual ? fmtDate(s.creado_en) : s.id} · modo {s.modo}
                </p>
              </div>
              <StatusBadge estado={s.estado} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function ProposalPage() {
  const { id, status } = useStudyContext();
  const p = status.proposal;

  if (!p) {
    return (
      <>
        <PageTitle title="Propuesta" />
        <Waiting
          title="Redactando la propuesta"
          detail="Monta las diez secciones del entregable con el diagnóstico, los hallazgos y el plan aprobado."
        />
        <div className="mt-6">
          <TracesPanel studyId={id} estado={status.estado} />
        </div>
      </>
    );
  }

  const c = p.contexto;
  return (
    <>
      <PageTitle
        title="Propuesta"
        subtitle={`${c.marca} · ${c.sector} · ${fmtDate(c.fecha)}`}
        actions={<Descargas id={id} />}
      >
        {c.datos_sinteticos && <KitNotice />}
      </PageTitle>

      <div className="grid gap-6">
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,8fr)_minmax(0,4fr)]">
          <div className="grid gap-6">
            <Panel title="Resumen ejecutivo" id="resumen">
              <p className="max-w-[68ch] text-section leading-7" data-testid="resumen-ejecutivo">
                {p.resumen_ejecutivo}
              </p>
            </Panel>
            <Panel title="Limitaciones" id="limitaciones">
              <ul className="max-w-[68ch] list-disc space-y-1.5 pl-5">
                {c.limitaciones.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </Panel>
          </div>
          <div className="grid gap-6">
            <Panel title="Contexto" id="contexto">
              <dl className="divide-y divide-rule">
                {[
                  ["Motores", c.motores.join(", ")],
                  ["Datos", c.origen_datos === "kit" ? "Kit del reto" : "APIs de los motores"],
                  ["Hallazgos", String(p.hallazgos.length)],
                  ["Acciones", String(p.plan.fases.reduce((s, f) => s + f.acciones.length, 0))],
                  ["Riesgos", String(p.riesgos.length)],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-4 py-1.5">
                    <dt className="text-muted">{k}</dt>
                    <dd className="num text-right">{v}</dd>
                  </div>
                ))}
              </dl>
            </Panel>
            <Mediciones brandId={status.study.brand_id} actual={id} />
          </div>
        </div>
        <TracesPanel studyId={id} estado={status.estado} />
      </div>
    </>
  );
}
