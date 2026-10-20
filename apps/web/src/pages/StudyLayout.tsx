import { NavLink, Outlet, useParams } from "react-router-dom";
import { useStudy } from "../api/hooks";
import { AppShell } from "../components/AppShell";
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
        <span className="num text-muted" title="Coste acumulado del estudio">
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

export function StudyLayout() {
  const { id = "" } = useParams();
  const q = useStudy(id);

  if (q.isError) {
    return (
      <AppShell>
        <ErrorState error={q.error} />
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
      <Outlet context={{ id, status: q.data } satisfies StudyContext} />
    </AppShell>
  );
}
