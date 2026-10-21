/** Una marca de registro de imprenta: círculo con cruz, como las esquinas de la presentación. */
function Marca({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`absolute size-5 ${className}`} fill="none" stroke="currentColor" strokeWidth="1">
      <circle cx="12" cy="12" r="6" />
      <path d="M12 2v20M2 12h20" />
    </svg>
  );
}

/** Las cuatro esquinas del pliego. Decoración pura: fijas, sin eventos y fuera del árbol accesible. */
export function RegistrationMarks({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden="true" className={`pointer-events-none fixed inset-3 z-0 hidden text-[var(--mark)] opacity-35 lg:block ${className}`}>
      <Marca className="left-0 top-0" />
      <Marca className="right-0 top-0" />
      <Marca className="bottom-0 left-0" />
      <Marca className="bottom-0 right-0" />
    </div>
  );
}
