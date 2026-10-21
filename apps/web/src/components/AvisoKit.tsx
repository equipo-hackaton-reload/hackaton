import { leerAvisoKit } from "../lib/avisoKit";

/** Aviso que dio la API al crear el estudio en modo kit (ver `lib/avisoKit.ts`). */
export function AvisoKit({ studyId }: { studyId: string }) {
  const aviso = leerAvisoKit(studyId);
  if (!aviso) return null;
  return (
    <p role="note" className="mb-4 rounded-control bg-pill-warn-bg px-3 py-2 text-meta font-medium text-pill-warn-ink">
      {aviso}
    </p>
  );
}
