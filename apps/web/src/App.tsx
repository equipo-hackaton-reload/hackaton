import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, MemoryRouter, Navigate, useLocation, useRoutes } from "react-router-dom";
import { makeQueryClient } from "./api/queryClient";
import { getSession } from "./lib/session";
import { routes } from "./routes";

/** Comportamiento de React Router v7, activado ya para evitar cambios al migrar. */
const FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };

function Rutas({ requireLogin }: { requireLogin: boolean }) {
  const element = useRoutes(routes);
  const { pathname, search } = useLocation();
  if (requireLogin && pathname !== "/login" && !getSession()) {
    return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />;
  }
  return element;
}

/**
 * La app. `initialPath` monta un router en memoria (tests); sin él, el del navegador.
 * `requireLogin` manda a /login a quien no tenga sesión; los tests lo dejan apagado.
 */
export function App({
  initialPath,
  client,
  requireLogin = false,
}: {
  initialPath?: string;
  client?: QueryClient;
  requireLogin?: boolean;
}) {
  const [qc] = useState(() => client ?? makeQueryClient());
  return (
    <QueryClientProvider client={qc}>
      {initialPath ? (
        <MemoryRouter initialEntries={[initialPath]} future={FUTURE}>
          <Rutas requireLogin={requireLogin} />
        </MemoryRouter>
      ) : (
        <BrowserRouter future={FUTURE}>
          <Rutas requireLogin={requireLogin} />
        </BrowserRouter>
      )}
    </QueryClientProvider>
  );
}
