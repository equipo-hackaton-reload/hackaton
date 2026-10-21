import type { Plan } from "../types/schemas";

/**
 * Borrador del plan en revisión. Las ediciones viven fuera del componente para que no se pierdan al
 * cambiar de pestaña del estudio (o al recargar, con sessionStorage). Un borrador solo vale para el
 * plan del que salió: si la API trae otro plan, se descarta.
 */
interface Borrador {
  base: string;
  plan: Plan;
}

const memoria = new Map<string, Borrador>();
const clave = (studyId: string) => `posiq-plan-draft:${studyId}`;

export function leerBorrador(studyId: string, original: Plan): Plan | null {
  let b = memoria.get(studyId) ?? null;
  if (!b) {
    try {
      const raw = sessionStorage.getItem(clave(studyId));
      b = raw ? (JSON.parse(raw) as Borrador) : null;
    } catch {
      b = null;
    }
  }
  return b && b.base === JSON.stringify(original) ? b.plan : null;
}

export function guardarBorrador(studyId: string, original: Plan, plan: Plan): void {
  const base = JSON.stringify(original);
  if (JSON.stringify(plan) === base) return borrarBorrador(studyId);
  const b = { base, plan };
  memoria.set(studyId, b);
  try {
    sessionStorage.setItem(clave(studyId), JSON.stringify(b));
  } catch {
    // Sin almacenamiento el borrador dura lo que la pestaña.
  }
}

export function borrarBorrador(studyId: string): void {
  memoria.delete(studyId);
  try {
    sessionStorage.removeItem(clave(studyId));
  } catch {
    // Nada que borrar.
  }
}
