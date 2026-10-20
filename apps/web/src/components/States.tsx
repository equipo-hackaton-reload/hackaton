import type { ReactNode } from "react";
import { ApiError } from "../api/client";

/** Espera mientras el grafo trabaja: dice qué está haciendo y que la pantalla se actualiza sola. */
export function Waiting({ title, detail }: { title: string; detail: string }) {
  return (
    <div role="status" aria-live="polite" className="panel flex items-start gap-4 px-5 py-6">
      <span aria-hidden className="mt-1.5 h-2 w-2 flex-none animate-pulse rounded-full bg-accent" />
      <div>
        <p className="text-section font-semibold">{title}</p>
        <p className="mt-1 max-w-prose text-muted">{detail}</p>
        <p className="mt-3 text-meta text-faint">Se actualiza sola cada 3 segundos.</p>
      </div>
    </div>
  );
}

export function ErrorState({ error, children }: { error: unknown; children?: ReactNode }) {
  const msg =
    error instanceof ApiError
      ? error.status === 404
        ? "No existe ningún estudio con ese identificador."
        : `La API respondió ${error.status}: ${error.message}`
      : "No se pudo conectar con la API. Comprueba que está arrancada o activa los mocks.";
  return (
    <div role="alert" className="panel border-pill-neg-bg px-5 py-5">
      <p className="font-semibold text-pill-neg-ink">No se pudo cargar el estudio</p>
      <p className="mt-1 text-muted">{msg}</p>
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-control bg-raised ${className}`} />;
}
