import { Link } from "react-router-dom";
import { useBrands } from "../api/hooks";
import { AppShell } from "../components/AppShell";
import { PageTitle } from "../components/PageTitle";
import { ErrorState, Skeleton } from "../components/States";
import { fmtDay, fmtInt } from "../lib/format";

/** Entrada al seguimiento: las marcas de los estudios del usuario (`GET /brands`). */
export function BrandsPage() {
  const q = useBrands();
  return (
    <AppShell>
      <PageTitle
        title="Seguimiento"
        subtitle="Cada marca que has medido, con su serie de mediciones. Solo se destacan los cambios que salen del margen de error."
        actions={
          <Link to="/" className="btn-primary">
            Nuevo estudio
          </Link>
        }
      />
      {q.isPending ? (
        <div className="space-y-3" aria-busy="true" aria-label="Cargando marcas">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : q.isError ? (
        <ErrorState error={q.error} titulo="No se pudieron cargar tus marcas">
          <button type="button" className="btn-secondary" onClick={() => q.refetch()}>
            Reintentar
          </button>
        </ErrorState>
      ) : q.data.length === 0 ? (
        <div className="panel px-5 py-6">
          <p className="text-section font-semibold">Aún no has medido ninguna marca</p>
          <p className="mt-1 text-muted">Crea un estudio con el brief de tu marca: será la línea base de su seguimiento.</p>
          <Link to="/" className="btn-primary mt-4">
            Crear el primer estudio
          </Link>
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2" aria-label="Tus marcas">
          {q.data.map((b) => (
            <li key={b.brand_id}>
              <Link
                to={`/marcas/${encodeURIComponent(b.brand_id)}`}
                className="panel flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-raised"
                data-testid="marca-seguimiento"
              >
                <span className="min-w-0">
                  <span className="block truncate text-section font-semibold">{b.nombre}</span>
                  <span className="num mt-0.5 block text-meta text-muted">
                    {fmtInt(b.n_mediciones)} {b.n_mediciones === 1 ? "medición" : "mediciones"}
                    {b.ultima_medicion ? ` · última el ${fmtDay(b.ultima_medicion)}` : " · sin mediciones completadas"}
                  </span>
                </span>
                <span aria-hidden className="text-muted">→</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
