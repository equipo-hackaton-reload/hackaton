import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "./Wordmark";

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
      <header className="sticky top-0 z-30 border-b border-line bg-ground">
        <div className="mx-auto flex min-h-[52px] max-w-canvas flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6">
          <Link to="/" aria-label="posiq., nuevo estudio" className="rounded-chip">
            <Wordmark />
          </Link>
          {bar}
        </div>
      </header>
      <main id="contenido" className="mx-auto max-w-canvas px-4 pb-24 pt-8 sm:px-6">
        {children}
      </main>
    </div>
  );
}
