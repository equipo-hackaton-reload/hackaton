import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { saveSession } from "../lib/session";
import { sesionDePrueba } from "../mocks/auth";

const ESPACIOS_DUROS = new RegExp(`[${String.fromCharCode(0xa0, 0x202f)}]`, "g");

/** Intl separa número y unidad con espacios duros; se normalizan para comparar texto. */
export const nb = (s: string | null | undefined) => (s ?? "").replace(ESPACIOS_DUROS, " ");

export function testClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

/** Renderiza un componente suelto con TanStack Query y router en memoria. */
export function renderUI(ui: ReactElement) {
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Abre sesión con una cuenta verificada del mock y devuelve su usuario y token. */
export function iniciarSesion(email = "ana@clinica.es") {
  const s = sesionDePrueba(email);
  saveSession({ token: s.token, expiraEn: s.expira, user: s.user }, false);
  return s;
}
