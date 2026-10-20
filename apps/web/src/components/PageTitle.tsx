import type { ReactNode } from "react";

/** Fila de título: el h1 de la pantalla, una línea con el hallazgo o el alcance y sus acciones. */
export function PageTitle({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        <h1 className="text-title font-semibold tracking-[-0.01em]">{title}</h1>
        {subtitle && <p className="mt-1.5 text-section text-muted">{subtitle}</p>}
        {children && <div className="mt-3">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
