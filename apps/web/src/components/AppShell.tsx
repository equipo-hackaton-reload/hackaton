import { useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { clearSession, useSession } from "../lib/session";
import { ThemeToggle } from "./ThemeToggle";
import { Wordmark } from "./Wordmark";

/** Quién ha entrado y cómo salir, siempre a la vista en la cabecera. */
function UserMenu() {
  const navigate = useNavigate();
  const sesion = useSession();
  const [saliendo, setSaliendo] = useState(false);
  if (!sesion) return null;
  const { email, nombre } = sesion.user;
  const inicial = (nombre || email)[0]?.toUpperCase() ?? "?";

  async function salir() {
    if (!sesion) return;
    setSaliendo(true);
    // Se invalida el token en la API; si falla, la sesión local se borra igualmente.
    await api.logout(sesion.token).catch(() => undefined);
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <button
      type="button"
      onClick={salir}
      disabled={saliendo}
      title={`${email} · Cerrar sesión`}
      aria-label={`Cerrar sesión de ${email}`}
      className="group flex h-10 items-center gap-2 rounded-full pl-1 pr-1 text-meta text-muted transition-colors hover:bg-raised hover:text-ink sm:pr-3"
    >
      <span aria-hidden="true" className="grid size-8 place-items-center rounded-full bg-accent font-display text-[13px] font-bold text-on-accent">
        {inicial}
      </span>
      <span className="hidden sm:inline">{saliendo ? "Saliendo…" : "Salir"}</span>
    </button>
  );
}

/** Barra superior fija con el nombre del producto y, dentro de un estudio, su estado. */
export function AppShell({ bar, children }: { bar?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-control focus:bg-surface focus:px-3 focus:py-2"
      >
        Saltar al contenido
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-[var(--header)] backdrop-blur-md backdrop-saturate-150">
        <div className="mx-auto flex min-h-[56px] max-w-canvas flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2 sm:gap-x-6 sm:px-6">
          <Link to="/" aria-label="posiq., nuevo estudio" className="rounded-chip">
            <Wordmark />
          </Link>
          {bar}
          <div className={`flex items-center gap-1 ${bar ? "-ml-1 sm:-ml-3" : "ml-auto"}`}>
            <NavLink
              to="/marcas"
              className={({ isActive }) =>
                `flex h-8 items-center rounded-control px-2.5 text-meta transition-colors ${
                  isActive ? "bg-active font-medium text-ink" : "text-muted hover:bg-raised hover:text-ink"
                }`
              }
            >
              Seguimiento
            </NavLink>
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>
      </header>
      <main id="contenido" className="mx-auto max-w-canvas px-4 pb-24 pt-8 sm:px-6">
        {children}
      </main>
    </div>
  );
}
