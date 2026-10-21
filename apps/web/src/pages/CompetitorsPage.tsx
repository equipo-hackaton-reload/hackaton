import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useResume } from "../api/hooks";
import { AvisoKit } from "../components/AvisoKit";
import { BrandEditor } from "../components/BrandEditor";
import { fromDrafts, toDrafts, validar, type BrandDraft } from "../lib/brands";
import { BriefCard } from "../components/BriefCard";
import { PageTitle } from "../components/PageTitle";
import { Waiting } from "../components/States";
import type { Market } from "../types/schemas";
import { useStudyContext } from "./studyContext";

function Editor({ market, marcaBriefId, pendiente }: { market: Market; marcaBriefId: string; pendiente: boolean }) {
  const { id } = useStudyContext();
  const navigate = useNavigate();
  const resume = useResume(id);
  const [drafts, setDrafts] = useState<BrandDraft[]>(() => toDrafts(market.marcas));
  const [intentado, setIntentado] = useState(false);
  const problemas = validar(drafts);

  function confirmar() {
    setIntentado(true);
    if (problemas.length) return;
    // mutateAsync: el editor se remonta al cambiar el estado y descartaría un onSuccess local.
    resume
      .mutateAsync({
        revision: "competidores",
        payload: { marcas: fromDrafts(drafts), confirmado_por_humano: true },
      })
      .then(() => navigate(`/studies/${id}/diagnostico`))
      .catch(() => undefined);
  }

  return (
    <section aria-labelledby="mercado-titulo" className="panel min-w-0 pb-4">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pb-1 pt-4">
        <h2 id="mercado-titulo" className="text-section font-semibold">
          {pendiente ? "Mercado propuesto" : "Mercado confirmado"}
        </h2>
        {pendiente ? (
          <button type="button" className="btn-primary" onClick={confirmar} disabled={resume.isPending}>
            {resume.isPending ? "Confirmando…" : "Confirmar y medir"}
          </button>
        ) : (
          <span className="pill bg-pill-pos-bg text-pill-pos-ink">Confirmado</span>
        )}
      </div>
      {intentado && problemas.length > 0 && (
        <ul role="alert" className="mx-5 mb-3 rounded-control bg-pill-neg-bg px-3 py-2 text-pill-neg-ink">
          {problemas.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      {resume.isError && (
        <p role="alert" className="mx-5 mb-3 rounded-control bg-pill-neg-bg px-3 py-2 text-pill-neg-ink">
          {resume.error instanceof ApiError
            ? `La API no aceptó el mercado: ${resume.error.message}`
            : "No se pudo enviar el mercado a la API."}
        </p>
      )}
      <BrandEditor drafts={drafts} onChange={setDrafts} marcaBriefId={marcaBriefId} readOnly={!pendiente} />
    </section>
  );
}

export function CompetitorsPage() {
  const { id, status } = useStudyContext();
  const pendiente = status.revision_pendiente === "competidores";

  if (!status.market) {
    return (
      <>
        <PageTitle title="Competidores" subtitle="posiq. está leyendo el brief para proponer el mercado." />
        <Waiting
          title="Leyendo el brief"
          detail="Extrae la ficha de la marca y propone sus competidores y el líder del mercado. Después podrás revisarlos antes de medir."
        />
      </>
    );
  }

  return (
    <>
      <PageTitle
        title="Competidores"
        subtitle={
          pendiente
            ? "Revisa con qué marcas se compara antes de medir: añade las que falten, quita las que sobren y marca el líder."
            : "Mercado confirmado. La medición usa estas marcas."
        }
        actions={
          !pendiente && (
            <Link to={`/studies/${id}/diagnostico`} className="btn-secondary">
              Ver el diagnóstico
            </Link>
          )
        }
      />
      <AvisoKit studyId={id} />
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Editor
          key={pendiente ? "editable" : "confirmado"}
          market={status.market}
          marcaBriefId={status.study.brand_id}
          pendiente={pendiente}
        />
        {status.brief && <BriefCard brief={status.brief} />}
      </div>
    </>
  );
}
