import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearSession, getSession } from "../lib/session";
import { ThemeToggle } from "./ThemeToggle";
import { Wordmark } from "./Wordmark";

/** Quién ha entrado y cómo salir, siempre a la vista en la cabecera. */
function UserMenu() {
  const navigate = useNavigate();
  const sesion = getSession();
  if (!sesion) return null;
  const inicial = (sesion.nombre || sesion.email)[0]?.toUpperCase() ?? "?";

  function salir() {
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <button
      type="button"
      onClick={salir}
      title={`${sesion.email} · Cerrar sesión`}
      aria-label={`Cerrar sesión de ${sesion.email}`}
      className="group flex h-10 items-center gap-2 rounded-full pl-1 pr-1 text-meta text-muted transition-colors hover:bg-raised hover:text-ink sm:pr-3"
    >
      <span aria-hidden="true" className="grid size-8 place-items-center rounded-full bg-accent font-display text-[13px] font-bold text-on-accent">
        {inicial}
      </span>
      <span className="hidden sm:inline">Salir</span>
    </button>
  );
}

/** Barra superior fija con el nombre del producto y, dentro de un estudio, su estado. */
/** Recordatorio discreto mientras el correo no esté verificado; no bloquea el trabajo. */
function VerifyBanner() {
  const { pathname, search } = useLocation();
  const sesion = getSession();
  if (!sesion || sesion.verificado || pathname === "/verificar") return null;
  return (
    <div className="border-b border-pill-warn-line bg-pill-warn-bg text-pill-warn-ink">
      <p className="mx-auto flex max-w-canvas flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-meta sm:px-6">
        <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 flex-none" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 5.5h14v9H3zM3.5 6l6.5 5 6.5-5" />
        </svg>
        <span>
          Aún no has verificado <strong>{sesion.email}</strong>.
        </span>
        <Link
          to={`/verificar?next=${encodeURIComponent(pathname + search)}`}
          className="font-semibold underline hover:no-underline"
        >
          Verificar ahora
        </Link>
      </p>
    </div>
  );
}

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
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>
      </header>
      <VerifyBanner />
      <main id="contenido" className="mx-auto max-w-canvas px-4 pb-24 pt-8 sm:px-6">
        {children}
      </main>
    </div>
  );
}
