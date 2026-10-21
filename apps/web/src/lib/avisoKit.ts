/**
 * Aviso de `POST /studies` en modo kit («Modo kit: datos sintéticos de Alborada; el brief no cambia
 * las mediciones»). La API lo devuelve al crear el estudio; se guarda por estudio en
 * sessionStorage para enseñarlo en la pantalla siguiente (competidores).
 */
const clave = (id: string) => `posiq-aviso-${id}`;

export function guardarAvisoKit(studyId: string, aviso: string | null | undefined): void {
  if (!aviso) return;
  try {
    sessionStorage.setItem(clave(studyId), aviso);
  } catch {
    // Sin almacenamiento no se ve el aviso; el resto de la pantalla sigue igual.
  }
}

export function leerAvisoKit(studyId: string): string | null {
  try {
    return sessionStorage.getItem(clave(studyId));
  } catch {
    return null;
  }
}
