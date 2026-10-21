import { QueryClientProvider, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { BrowserRouter, MemoryRouter, Navigate, useLocation, useNavigate, useRoutes } from "react-router-dom";
import { EVENTO_401 } from "./api/client";
import { makeQueryClient } from "./api/queryClient";
import { esPublica, rutaLogin, useSession } from "./lib/session";
import { routes } from "./routes";

/** Comportamiento de React Router v7, activado ya para evitar cambios al migrar. */
const FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };

function Rutas({ requireLogin }: { requireLogin: boolean }) {
  const element = useRoutes(routes);
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const sesion = useSession();
  const usuario = sesion?.user.id ?? null;
  const anterior = useRef(usuario);
  const ruta = useRef(pathname + search);
  ruta.current = pathname + search;

  // Los datos de un usuario no se quedan en la caché al salir o al entrar otro.
  useEffect(() => {
    if (anterior.current !== usuario) qc.clear();
    anterior.current = usuario;
  }, [usuario, qc]);

  // 401 de la API: la sesión ya se ha limpiado; se vuelve al login conservando la ruta.
  useEffect(() => {
    function alLogin() {
      if (!esPublica(ruta.current.split("?")[0])) navigate(rutaLogin(ruta.current), { replace: true });
    }
    window.addEventListener(EVENTO_401, alLogin);
    return () => window.removeEventListener(EVENTO_401, alLogin);
  }, [navigate]);

  if (requireLogin && !esPublica(pathname) && !sesion) {
    return <Navigate to={rutaLogin(pathname + search)} replace />;
  }
  return element;
}

/**
 * La app. `initialPath` monta un router en memoria (tests); sin él, el del navegador.
 * `requireLogin` manda a /login a quien no tenga sesión antes de llamar a la API; sin él, es el
 * primer 401 de la API el que lleva al login.
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
