import type { ReactNode } from "react";

interface Props {
  title: string;
  id?: string;
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}

/** Bloque de una pantalla: título que lo nombra, metadatos a la derecha y su contenido. */
export function Panel({ title, id, meta, actions, children, className = "", flush = false }: Props) {
  const headingId = id ? `${id}-titulo` : undefined;
  return (
    <section aria-labelledby={headingId} className={`panel min-w-0 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-5 pt-4">
        <h2 id={headingId} className="text-section font-semibold">
          {title}
        </h2>
        {(meta || actions) && (
          <div className="flex items-center gap-3 text-meta text-muted">
            {meta}
            {actions}
          </div>
        )}
      </div>
      <div className={flush ? "pb-2 pt-3" : "px-5 pb-5 pt-3"}>{children}</div>
    </section>
  );
}
