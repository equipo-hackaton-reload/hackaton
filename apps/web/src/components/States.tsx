import { useContext, type ReactNode } from "react";
import { ApiError, rutaNoDisponible } from "../api/client";
import { FalloContext } from "./falloContext";

/** Espera mientras el grafo trabaja: dice qué está haciendo y que la pantalla se actualiza sola. */
export function Waiting({ title, detail }: { title: string; detail: string }) {
  const fallo = useContext(FalloContext);
  if (fallo) {
    return (
      <div className="panel flex items-start gap-4 px-5 py-6" data-testid="paso-detenido">
        <span aria-hidden className="mt-1.5 h-2 w-2 flex-none rounded-full bg-negative" />
        <div>
          <p className="text-section font-semibold">{title}: no se completó</p>
          <p className="mt-1 max-w-prose text-muted">El estudio se detuvo por un error antes de llegar aquí. Mira el aviso de arriba.</p>
        </div>
      </div>
    );
  }
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

export function ErrorState({
  error,
  children,
  titulo = "No se pudo cargar el estudio",
  noEncontrado = "No existe ningún estudio con ese identificador en tu cuenta.",
  noDisponible = "La API conectada todavía no ofrece esta función.",
}: {
  error: unknown;
  children?: ReactNode;
  titulo?: string;
  noEncontrado?: string;
  /** Mensaje cuando la ruta no existe en la API (404 «Not Found» de FastAPI). */
  noDisponible?: string;
}) {
  const msg = rutaNoDisponible(error)
    ? noDisponible
    : error instanceof ApiError
      ? error.status === 404
        ? noEncontrado
        : `La API respondió ${error.status}: ${error.message}`
      : "No se pudo conectar con la API. Comprueba que está arrancada o activa los mocks.";
  return (
    <div role="alert" className="panel border-pill-neg-bg px-5 py-5">
      <p className="font-semibold text-pill-neg-ink">{titulo}</p>
      <p className="mt-1 text-muted">{msg}</p>
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-control bg-raised ${className}`} />;
}
