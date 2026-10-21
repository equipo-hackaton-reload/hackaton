/**
 * La diana de posiq.: cuatro aros (magenta, cian, amarillo y coral, de fuera adentro) con la cruz
 * de mira sobre el aro exterior. Los colores salen de los tokens de marca, que se suavizan en el
 * tema claro para no deslumbrar sobre fondo blanco.
 */
export function LogoMark({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 100 100" className={className} fill="none" strokeLinecap="round">
      <circle cx="50" cy="50" r="44.5" stroke="var(--brand-magenta)" strokeWidth="2.4" />
      <path d="M50 1.5v10M50 88.5v10M1.5 50h10M88.5 50h10" stroke="var(--brand-magenta)" strokeWidth="2.4" />
      <circle cx="50" cy="50" r="33" stroke="var(--brand-cyan)" strokeWidth="5" />
      <circle cx="50" cy="50" r="20.5" stroke="var(--brand-yellow)" strokeWidth="5" />
      <circle cx="50" cy="50" r="9" stroke="var(--brand-coral)" strokeWidth="4.8" />
    </svg>
  );
}

/** El nombre del producto: «posiq» en estrecha y el punto magenta redondo, como en el logotipo. */
export function Wordmark({ className = "", mark = true }: { className?: string; mark?: boolean }) {
  return (
    <span role="img" aria-label="posiq." className={`inline-flex select-none items-center gap-[0.35em] text-[24px] leading-none ${className}`}>
      {mark && <LogoMark className="size-[1.3em] flex-none" />}
      <span className="inline-flex items-baseline font-display font-bold tracking-[0.005em]">
        posiq
        <span className="ml-[0.06em] inline-block size-[0.22em] rounded-full bg-[var(--brand-magenta)]" />
      </span>
    </span>
  );
}
