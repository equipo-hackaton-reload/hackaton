import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { RemedicionRealNoDisponible, useRemeasure, useRemeasureEstimate } from "../api/hooks";
import { fmtEur } from "../lib/format";
import { CostEstimateView } from "./CostEstimateView";

/** Margen con el que la API da por buena la estimación confirmada (± 0,01 €). */
const TOLERANCIA_EUR = 0.01;

interface Props {
  studyId: string;
  className?: string;
  label?: string;
}

/**
 * «Volver a medir» con confirmación del coste: primero pide la estimación a la API, la enseña y
 * solo al confirmar envía `POST /remeasure {confirmado, coste_estimado_eur}`.
 */
export function RemeasureButton({ studyId, className = "btn-secondary", label = "Volver a medir" }: Props) {
  const [abierto, setAbierto] = useState(false);
  return (
    <>
      <button type="button" className={className} onClick={() => setAbierto(true)} aria-haspopup="dialog">
        {label}
      </button>
      {abierto && <RemeasureDialog studyId={studyId} onClose={() => setAbierto(false)} />}
    </>
  );
}

function RemeasureDialog({ studyId, onClose }: { studyId: string; onClose: () => void }) {
  const navigate = useNavigate();
  const titulo = useId();
  const cancelarRef = useRef<HTMLButtonElement>(null);
  const estimate = useRemeasureEstimate(studyId, true);
  const remeasure = useRemeasure(studyId);
  const [aviso, setAviso] = useState<string | null>(null);
  const [aceptaTope, setAceptaTope] = useState(false);

  useEffect(() => {
    cancelarRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const est = estimate.data;
  const excede = est != null && est.coste_estimado_eur > est.presupuesto_max_eur;
  const puede = est != null && !estimate.isFetching && !remeasure.isPending && (!excede || aceptaTope);

  async function confirmar() {
    if (!est) return;
    const enviado = est.coste_estimado_eur;
    setAviso(null);
    try {
      const r = await remeasure.mutateAsync({ confirmado: true, coste_estimado_eur: enviado });
      onClose();
      navigate(`/studies/${encodeURIComponent(r.study_id)}/diagnostico`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // Dos 409 posibles: el coste ha cambiado o ya hay una re-medición en curso. Se distingue
        // comparando con la estimación actual, sin depender del texto del error.
        const nueva = (await estimate.refetch()).data;
        if (nueva && Math.abs(nueva.coste_estimado_eur - enviado) > TOLERANCIA_EUR) {
          setAceptaTope(false);
          setAviso(
            `El coste estimado ha cambiado: era ${fmtEur(enviado)} y ahora es ${fmtEur(nueva.coste_estimado_eur)}. Revísalo y confirma de nuevo.`,
          );
        } else {
          setAviso(`Ya hay una re-medición en curso de este estudio. Espera a que termine. (${e.message})`);
        }
        return;
      }
      setAviso(e instanceof ApiError ? `La API no inició la re-medición: ${e.message}` : "No se pudo conectar con la API.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 px-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby={titulo} className="panel w-full max-w-[460px] px-6 py-5">
        <h2 id={titulo} className="text-section font-semibold">Volver a medir</h2>
        <p className="mt-1.5 text-muted">
          Se repite la medición con el mismo banco de prompts, el mismo mercado confirmado y el mismo modo que el
          estudio original. Solo se informará de cambios que salgan del margen de error.
        </p>

        <div className="mt-4 rounded-control bg-raised px-4 py-3">
          {estimate.isPending ? (
            <p className="text-muted">Calculando el coste…</p>
          ) : est ? (
            <>
              <CostEstimateView estimate={est} />
              {est.aproximada && (
                <p className="mt-2 text-meta text-muted" data-testid="estimacion-aproximada">
                  Esta API todavía no calcula el coste propio de la re-medición: se muestra su estimación para un
                  estudio nuevo en modo kit, que no tiene coste de motores.
                </p>
              )}
            </>
          ) : estimate.error instanceof RemedicionRealNoDisponible ? (
            <p className="text-negative" data-testid="remedicion-no-disponible">
              {estimate.error.message}
            </p>
          ) : (
            <p className="text-negative">
              No se pudo obtener la estimación del coste
              {estimate.error instanceof ApiError ? `: ${estimate.error.message}` : ""}. Sin estimación no se puede confirmar.
            </p>
          )}
        </div>

        {excede && (
          <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-meta">
            <input type="checkbox" checked={aceptaTope} onChange={(e) => setAceptaTope(e.target.checked)} className="mt-0.5 size-4 flex-none accent-[var(--accent)]" />
            Entiendo que la estimación supera el tope y quiero medir igualmente.
          </label>
        )}

        {aviso && (
          <p role="alert" className="mt-3 rounded-control bg-pill-warn-bg px-3 py-2 text-meta text-pill-warn-ink">
            {aviso}
          </p>
        )}

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button ref={cancelarRef} type="button" className="btn-ghost" onClick={onClose}>
            Cancelar
          </button>
          <button type="button" className="btn-primary" onClick={confirmar} disabled={!puede} aria-busy={remeasure.isPending}>
            {remeasure.isPending ? "Iniciando…" : est ? `Confirmar y medir (${fmtEur(est.coste_estimado_eur)})` : "Confirmar y medir"}
          </button>
        </div>
      </div>
    </div>
  );
}
