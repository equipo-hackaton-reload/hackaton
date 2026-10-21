/**
 * Sesión de la demo. La API todavía no tiene cuentas: el login solo guarda en el navegador quién
 * entra, para dar la bienvenida y recordar el correo. «Recordarme» usa localStorage; si no,
 * sessionStorage, que se borra al cerrar la pestaña.
 */
export interface Sesion {
  email: string;
  nombre: string;
  /** El correo se ha confirmado con un código (ver emailVerification.ts). */
  verificado?: boolean;
}

const CLAVE = "posiq-session";
const ULTIMO_EMAIL = "posiq-last-email";

function leer(store: () => Storage): Sesion | null {
  try {
    const raw = store().getItem(CLAVE);
    return raw ? (JSON.parse(raw) as Sesion) : null;
  } catch {
    return null;
  }
}

export function getSession(): Sesion | null {
  return leer(() => localStorage) ?? leer(() => sessionStorage);
}

export function saveSession(sesion: Sesion, recordar: boolean): void {
  try {
    (recordar ? localStorage : sessionStorage).setItem(CLAVE, JSON.stringify(sesion));
    localStorage.setItem(ULTIMO_EMAIL, sesion.email);
  } catch {
    // Sin almacenamiento la sesión no persiste, pero la navegación sigue funcionando.
  }
}

/** Marca el correo de la sesión como verificado, en el mismo almacén donde ya estaba. */
export function markVerified(): void {
  for (const store of [() => localStorage, () => sessionStorage]) {
    const sesion = leer(store);
    if (!sesion) continue;
    try {
      store().setItem(CLAVE, JSON.stringify({ ...sesion, verificado: true }));
    } catch {
      // Sin almacenamiento la marca dura lo que la página.
    }
    return;
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(CLAVE);
    sessionStorage.removeItem(CLAVE);
  } catch {
    // Nada que borrar.
  }
}

/** Último correo usado: el formulario lo propone para que se reconozca en vez de recordarlo. */
export function lastEmail(): string {
  try {
    return localStorage.getItem(ULTIMO_EMAIL) ?? "";
  } catch {
    return "";
  }
}

/** «ana.lopez@clinica.es» → «Ana». */
export function nombreDesde(email: string): string {
  const base = email.split("@")[0]?.split(/[._-]/)[0] ?? "";
  return base ? base[0].toUpperCase() + base.slice(1) : "";
}

/** Solo rutas internas: evita que `?next=` mande fuera de la app. */
export function destinoSeguro(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/login")) return "/";
  return next;
}
