/** Una marca de registro de imprenta: círculo con cruz, como las esquinas de la presentación. */
function Marca({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`absolute size-5 ${className}`} fill="none" stroke="currentColor" strokeWidth="1">
      <circle cx="12" cy="12" r="6" />
      <path d="M12 2v20M2 12h20" />
    </svg>
  );
}

interface RegistrationMarksProps {
  /** Posicionamiento y visibilidad del pliego (por defecto, fijo y solo con margen lateral real). */
  className?: string;
  /** Solo las dos de abajo: en la app las de arriba quedarían tapadas por la cabecera fija. */
  soloInferiores?: boolean;
}

/**
 * Las esquinas del pliego. Decoración pura: sin eventos, fuera del árbol accesible y por DEBAJO del
 * contenido (-z-10; el contenedor debe crear su contexto de apilamiento con `isolate`). Solo se
 * muestran desde 1300px, cuando hay un margen lateral real y no pisan los paneles.
 */
export function RegistrationMarks({ className = "fixed hidden min-[1300px]:block", soloInferiores = false }: RegistrationMarksProps) {
  return (
    <div aria-hidden="true" className={`pointer-events-none inset-3 -z-10 text-[var(--mark)] opacity-35 ${className}`}>
      {!soloInferiores && <Marca className="left-0 top-0" />}
      {!soloInferiores && <Marca className="right-0 top-0" />}
      <Marca className="bottom-0 left-0" />
      <Marca className="bottom-0 right-0" />
    </div>
  );
}
