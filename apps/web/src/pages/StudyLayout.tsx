import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { useStudy } from "../api/hooks";
import { AppShell } from "../components/AppShell";
import { FalloContext } from "../components/falloContext";
import { ErrorState, Skeleton } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";
import { fmtEur } from "../lib/format";
import { disponibles, type Pantalla } from "../lib/study";
import type { StudyStatus } from "../types/api";
import type { StudyContext } from "./studyContext";

const PANTALLAS: { to: Pantalla; label: string }[] = [
  { to: "competidores", label: "Competidores" },
  { to: "diagnostico", label: "Diagnóstico" },
  { to: "plan", label: "Plan" },
  { to: "propuesta", label: "Propuesta" },
];

function StudyBar({ status }: { status: StudyStatus }) {
  const listas = disponibles(status);
  return (
    <>
      <nav aria-label="Pantallas del estudio" className="order-3 -mx-4 w-[calc(100%+2rem)] overflow-x-auto px-4 sm:order-none sm:mx-0 sm:w-auto sm:px-0">
        <ul className="flex gap-1">
          {PANTALLAS.map((p) =>
            listas.has(p.to) ? (
              <li key={p.to}>
                <NavLink
                  to={p.to}
                  className={({ isActive }) =>
                    `flex h-8 items-center whitespace-nowrap rounded-control px-2.5 transition-colors ${
                      isActive ? "bg-active font-medium text-ink" : "text-muted hover:bg-raised hover:text-ink"
                    }`
                  }
                >
                  {p.label}
                </NavLink>
              </li>
            ) : (
              <li key={p.to}>
                <span
                  aria-disabled="true"
                  title="Aún no disponible"
                  className="flex h-8 cursor-default items-center whitespace-nowrap px-2.5 text-faint opacity-60"
                >
                  {p.label}
                </span>
              </li>
            ),
          )}
        </ul>
      </nav>
      <div className="ml-auto flex items-center gap-3 text-meta">
        <span className="hidden text-muted md:inline">{status.study.brief.marca}</span>
        <StatusBadge estado={status.estado} />
        <span className="num hidden text-muted sm:inline" title="Coste acumulado del estudio">
          {fmtEur(status.coste_acumulado_eur)}
        </span>
        {status.study.modo === "kit" && (
          <span className="pill bg-raised text-muted" title="Las respuestas salen del kit del reto">
            Kit
          </span>
        )}
      </div>
    </>
  );
}

/** El grafo se ha detenido: se dice por qué y se deja reintentar o salir, sin spinner infinito. */
function EstudioDetenido({ status, onRetry, retrying }: { status: StudyStatus; onRetry: () => void; retrying: boolean }) {
  return (
    <section role="alert" aria-labelledby="detenido-titulo" className="mb-6 rounded-card border border-pill-neg-bg bg-pill-neg-bg px-5 py-4 text-pill-neg-ink">
      <h2 id="detenido-titulo" className="font-semibold">El estudio se ha detenido por un error</h2>
      {status.errores.length > 0 ? (
        <ul className="mt-1.5 list-disc space-y-0.5 pl-5" data-testid="errores-estudio">
          {status.errores.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1.5">La API no ha dado más detalle.</p>
      )}
      <p className="mt-2 text-meta">Lo que ya se había calculado sigue disponible en las pestañas de arriba.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={onRetry} disabled={retrying}>
          {retrying ? "Comprobando…" : "Volver a comprobar"}
        </button>
        <Link to="/" className="btn-ghost">Empezar un estudio nuevo</Link>
        <Link to={`/marcas/${encodeURIComponent(status.study.brand_id)}`} className="btn-ghost">Ir al seguimiento</Link>
      </div>
    </section>
  );
}

export function StudyLayout() {
  const { id = "" } = useParams();
  const q = useStudy(id);

  if (q.isError && !q.data) {
    return (
      <AppShell>
        <ErrorState error={q.error}>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary" onClick={() => q.refetch()} disabled={q.isFetching}>
              {q.isFetching ? "Reintentando…" : "Reintentar"}
            </button>
            <Link to="/marcas" className="btn-ghost">Volver a mis marcas</Link>
          </div>
        </ErrorState>
      </AppShell>
    );
  }
  if (!q.data) {
    return (
      <AppShell>
        <div className="space-y-4" aria-busy="true" aria-label="Cargando estudio">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-40 w-full" />
        </div>
      </AppShell>
    );
  }
  return (
    <AppShell bar={<StudyBar status={q.data} />}>
      {q.isError && (
        // Fallo puntual de un sondeo: se avisa sin tapar la pantalla y se siguen mostrando los datos.
        <p role="status" className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-control bg-pill-warn-bg px-4 py-2 text-meta text-pill-warn-ink" data-testid="sondeo-fallido">
          No se pudo actualizar el estado del estudio; se muestran los últimos datos recibidos.
          <button type="button" className="font-semibold underline hover:no-underline" onClick={() => q.refetch()}>
            Reintentar ahora
          </button>
        </p>
      )}
      {q.data.estado === "error" && (
        <EstudioDetenido status={q.data} onRetry={() => q.refetch()} retrying={q.isFetching} />
      )}
      <FalloContext.Provider value={q.data.estado === "error"}>
        <Outlet context={{ id, status: q.data } satisfies StudyContext} />
      </FalloContext.Provider>
    </AppShell>
  );
}
