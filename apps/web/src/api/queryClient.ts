import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./client";

/**
 * Un reintento para fallos de red o 5xx; un 4xx (404 de ruta, 401, 409…) no cambia al repetirlo, ni
 * tampoco el rechazo de la re-medición real sin estimación propia (`RemedicionRealNoDisponible`).
 */
function reintentar(fallos: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  if (error instanceof Error && error.name === "RemedicionRealNoDisponible") return false;
  return fallos < 1;
}

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: reintentar, refetchOnWindowFocus: false },
    },
  });
}
