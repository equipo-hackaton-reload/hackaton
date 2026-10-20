import { useId, useRef } from "react";
import type { BrandDraft } from "../lib/brands";
import { ROL_LABEL } from "../lib/study";
import type { Rol } from "../types/schemas";

const ROLES: Rol[] = ["foco", "contexto", "lider"];

/** Columnas de la tabla: nombre, rol, alias, dominio y la acción de quitar. */
const COLS = "md:grid-cols-[minmax(0,1.7fr)_112px_minmax(0,1.3fr)_minmax(0,1.3fr)_64px]";

/** En escritorio el campo se lee como una celda y solo muestra su borde al pasar o al editar. */
const CELDA =
  "field md:h-8 md:border-transparent md:bg-transparent md:px-2 md:hover:border-line md:focus:border-control md:focus:bg-surface disabled:cursor-default disabled:appearance-none disabled:text-ink disabled:hover:border-transparent";

interface Props {
  drafts: BrandDraft[];
  onChange: (drafts: BrandDraft[]) => void;
  /** Marca del brief: no se puede quitar ni dejar de ser foco. */
  marcaBriefId: string;
  readOnly?: boolean;
}

let nuevas = 0;

export function BrandEditor({ drafts, onChange, marcaBriefId, readOnly = false }: Props) {
  const uid = useId();
  const lastAdded = useRef<string | null>(null);

  const update = (key: string, patch: Partial<BrandDraft>) =>
    onChange(drafts.map((d) => (d.key === key ? { ...d, ...patch } : d)));

  function add() {
    nuevas += 1;
    const key = `nueva-${nuevas}`;
    lastAdded.current = key;
    onChange([
      ...drafts,
      { key, id: "", nombre: "", rol: "contexto", aliases: "", dominio: "", rol_detalle: "Añadida en la revisión", nueva: true },
    ]);
  }

  const contar = (rol: Rol) => drafts.filter((d) => d.rol === rol).length;

  return (
    <div>
      <p className="mb-3 px-5 text-meta text-muted">
        {drafts.length} marcas · {contar("foco")} foco · {contar("contexto")} contexto · {contar("lider")} líder
      </p>
      <div role="table" aria-label="Marcas del mercado" className="text-body">
        <div role="row" className={`hidden gap-2 border-b border-line px-5 pb-2 text-meta text-muted md:grid ${COLS}`}>
          <span role="columnheader" className="pl-2">Marca</span>
          <span role="columnheader" className="pl-2">Rol</span>
          <span role="columnheader" className="pl-2">Alias, separados por comas</span>
          <span role="columnheader" className="pl-2">Dominio</span>
          <span role="columnheader" className="sr-only">Acciones</span>
        </div>
        {drafts.map((d, i) => {
          const esBrief = d.id === marcaBriefId;
          const n = `${uid}-${i}`;
          return (
            <div
              role="row"
              key={d.key}
              data-testid="marca"
              className={`grid grid-cols-2 gap-x-3 gap-y-2 border-b border-rule px-5 py-3 last:border-b-0 md:items-center md:gap-x-2 md:py-1.5 ${COLS} ${
                esBrief ? "bg-accent-soft" : ""
              }`}
            >
              <div role="cell" className="col-span-2 min-w-0 md:col-span-1">
                {esBrief ? (
                  <p className="truncate font-semibold text-accent-ink md:px-2" title={d.nombre}>
                    {d.nombre}
                  </p>
                ) : (
                  <>
                    <label htmlFor={`${n}-nombre`} className="mb-1 block text-meta text-muted md:sr-only">
                      Nombre de la marca
                    </label>
                    <input
                      id={`${n}-nombre`}
                      className={`${CELDA} font-medium`}
                      value={d.nombre}
                      disabled={readOnly}
                      autoFocus={lastAdded.current === d.key}
                      placeholder="Nombre de la marca"
                      aria-invalid={!d.nombre.trim()}
                      title={d.nombre}
                      onChange={(e) => update(d.key, { nombre: e.target.value })}
                    />
                  </>
                )}
              </div>
              <div role="cell">
                {esBrief ? (
                  <p className="leading-4 md:pl-[13px]">
                    {ROL_LABEL[d.rol]}
                    <span className="block text-meta text-accent-ink">marca del brief</span>
                  </p>
                ) : (
                  <>
                    <label htmlFor={`${n}-rol`} className="mb-1 block text-meta text-muted md:sr-only">
                      Rol
                    </label>
                    <select
                      id={`${n}-rol`}
                      className={`${CELDA} cursor-pointer pr-6`}
                      value={d.rol}
                      disabled={readOnly}
                      onChange={(e) => update(d.key, { rol: e.target.value as Rol })}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROL_LABEL[r]}
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>
              <div role="cell" className="min-w-0">
                <label htmlFor={`${n}-alias`} className="mb-1 block text-meta text-muted md:sr-only">
                  Alias
                </label>
                <input
                  id={`${n}-alias`}
                  className={CELDA}
                  value={d.aliases}
                  disabled={readOnly}
                  placeholder="Sin alias"
                  title={d.aliases}
                  onChange={(e) => update(d.key, { aliases: e.target.value })}
                />
              </div>
              <div role="cell" className="min-w-0">
                <label htmlFor={`${n}-dominio`} className="mb-1 block text-meta text-muted md:sr-only">
                  Dominio
                </label>
                <input
                  id={`${n}-dominio`}
                  className={`${CELDA} text-muted`}
                  value={d.dominio}
                  disabled={readOnly}
                  placeholder="ejemplo.com"
                  inputMode="url"
                  autoComplete="off"
                  spellCheck={false}
                  title={d.dominio}
                  onChange={(e) => update(d.key, { dominio: e.target.value })}
                />
              </div>
              <div role="cell" className="flex items-end justify-end md:items-center">
                {!readOnly && !esBrief && (
                  <button
                    type="button"
                    className="btn-ghost h-8 px-2 text-muted hover:text-negative"
                    aria-label={`Quitar ${d.nombre || "marca sin nombre"}`}
                    onClick={() => onChange(drafts.filter((x) => x.key !== d.key))}
                  >
                    Quitar
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {!readOnly && (
        <div className="px-5 pt-3">
          <button type="button" className="btn-secondary h-8" onClick={add}>
            <svg aria-hidden width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 3v10M3 8h10" strokeLinecap="round" />
            </svg>
            Añadir marca
          </button>
        </div>
      )}
    </div>
  );
}
