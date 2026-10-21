import { ESTADO_LABEL } from "../lib/study";
import type { EstadoApi } from "../types/api";

const TONO: Record<EstadoApi, string> = {
  en_curso: "bg-raised text-ink",
  esperando_revision_competidores: "bg-pill-warn-bg text-pill-warn-ink",
  esperando_revision_plan: "bg-pill-warn-bg text-pill-warn-ink",
  completado: "bg-pill-pos-bg text-pill-pos-ink",
  error: "bg-pill-neg-bg text-pill-neg-ink",
};

/** Forma además de color: cada estado se distingue también sin ver el tono (daltonismo). */
function Forma({ estado }: { estado: EstadoApi }) {
  if (estado === "en_curso") {
    return <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />;
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 12 12" className="size-3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      {estado === "completado" ? (
        <path d="M2.5 6.3 5 8.7l4.5-5.2" />
      ) : estado === "error" ? (
        <path d="M3 3l6 6M9 3 3 9" />
      ) : (
        <path d="M6 3.2v3.3M6 8.8h.01M6 1l5 9H1z" />
      )}
    </svg>
  );
}

export function StatusBadge({ estado }: { estado: EstadoApi }) {
  return (
    <span className={`pill gap-1.5 ${TONO[estado]}`} data-testid="estado">
      <Forma estado={estado} />
      {ESTADO_LABEL[estado]}
    </span>
  );
}
