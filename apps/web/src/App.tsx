import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, MemoryRouter, useRoutes } from "react-router-dom";
import { makeQueryClient } from "./api/queryClient";
import { routes } from "./routes";

/** Comportamiento de React Router v7, activado ya para evitar cambios al migrar. */
const FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };

function Rutas() {
  return useRoutes(routes);
}

/** La app. `initialPath` monta un router en memoria (tests); sin él, el del navegador. */
export function App({ initialPath, client }: { initialPath?: string; client?: QueryClient }) {
  const [qc] = useState(() => client ?? makeQueryClient());
  return (
    <QueryClientProvider client={qc}>
      {initialPath ? (
        <MemoryRouter initialEntries={[initialPath]} future={FUTURE}>
          <Rutas />
        </MemoryRouter>
      ) : (
        <BrowserRouter future={FUTURE}>
          <Rutas />
        </BrowserRouter>
      )}
    </QueryClientProvider>
  );
}
