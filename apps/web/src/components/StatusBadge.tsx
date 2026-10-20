import { ESTADO_LABEL } from "../lib/study";
import type { EstadoEstudio } from "../types/schemas";

const TONO: Record<EstadoEstudio, string> = {
  en_curso: "bg-raised text-ink",
  esperando_revision_competidores: "bg-pill-warn-bg text-pill-warn-ink",
  esperando_revision_plan: "bg-pill-warn-bg text-pill-warn-ink",
  completado: "bg-pill-pos-bg text-pill-pos-ink",
};

export function StatusBadge({ estado }: { estado: EstadoEstudio }) {
  return (
    <span className={`pill gap-1.5 ${TONO[estado]}`} data-testid="estado">
      {estado === "en_curso" && (
        <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
      )}
      {ESTADO_LABEL[estado]}
    </span>
  );
}
