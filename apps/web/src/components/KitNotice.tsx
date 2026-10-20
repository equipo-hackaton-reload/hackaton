/** Aviso permanente cuando las cifras salen del kit del reto y no de motores reales. */
export function KitNotice() {
  return (
    <p
      role="note"
      className="inline-flex items-center gap-2 rounded-chip border border-pill-warn-line bg-pill-warn-bg px-2.5 py-1 text-meta font-medium text-pill-warn-ink"
    >
      <svg aria-hidden width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="8" cy="8" r="6.25" />
        <path d="M8 4.75v3.75M8 10.75v.5" strokeLinecap="round" />
      </svg>
      Datos sintéticos del kit: no son respuestas reales de los motores
    </p>
  );
}
