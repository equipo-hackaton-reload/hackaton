/**
 * Verificación de correo por código de 6 cifras.
 *
 * La página solo habla con `EmailVerifier`. Hoy lo cumple `demoVerifier`, que no envía nada:
 * genera el código en el navegador y la pantalla lo enseña. Cuando exista el servicio de
 * cuentas, basta con escribir un verificador que llame a la API y devolverlo en `verifier`.
 */
export interface EnvioCodigo {
  /** Cuándo caduca el código (ms desde epoch). */
  caducaEn: number;
  /** Solo en demo: el código, para poder probar sin buzón. */
  codigoDemo?: string;
}

export type ResultadoVerificacion = "ok" | "incorrecto" | "caducado" | "sin_codigo" | "bloqueado";

export interface EmailVerifier {
  sendCode(email: string): Promise<EnvioCodigo>;
  confirm(email: string, code: string): Promise<ResultadoVerificacion>;
}

export const CODIGO_LONGITUD = 6;
export const VIGENCIA_MS = 10 * 60 * 1000;
export const ESPERA_REENVIO_S = 30;
export const MAX_INTENTOS = 5;

interface Pendiente {
  email: string;
  codigo: string;
  caducaEn: number;
  intentos: number;
}

const CLAVE = "posiq-email-verification";

function leer(): Pendiente | null {
  try {
    const raw = sessionStorage.getItem(CLAVE);
    return raw ? (JSON.parse(raw) as Pendiente) : null;
  } catch {
    return null;
  }
}

function guardar(p: Pendiente | null): void {
  try {
    if (p) sessionStorage.setItem(CLAVE, JSON.stringify(p));
    else sessionStorage.removeItem(CLAVE);
  } catch {
    // Sin almacenamiento el código solo vive mientras no se recargue.
  }
}

function codigoAleatorio(): string {
  const n = new Uint32Array(1);
  crypto.getRandomValues(n);
  return String(n[0] % 10 ** CODIGO_LONGITUD).padStart(CODIGO_LONGITUD, "0");
}

export const demoVerifier: EmailVerifier = {
  async sendCode(email) {
    const pendiente = { email, codigo: codigoAleatorio(), caducaEn: Date.now() + VIGENCIA_MS, intentos: 0 };
    guardar(pendiente);
    return { caducaEn: pendiente.caducaEn, codigoDemo: pendiente.codigo };
  },
  async confirm(email, code) {
    const p = leer();
    if (!p || p.email !== email) return "sin_codigo";
    if (Date.now() > p.caducaEn) return "caducado";
    if (p.intentos >= MAX_INTENTOS) return "bloqueado";
    if (code !== p.codigo) {
      guardar({ ...p, intentos: p.intentos + 1 });
      return p.intentos + 1 >= MAX_INTENTOS ? "bloqueado" : "incorrecto";
    }
    guardar(null);
    return "ok";
  },
};

/** El verificador que usa la app. Sustitúyelo aquí por el que llame a la API. */
export const verifier: EmailVerifier = demoVerifier;

/** Deja solo cifras y corta a la longitud del código: así pegar «123 456» funciona. */
export function limpiarCodigo(valor: string): string {
  return valor.replace(/\D/g, "").slice(0, CODIGO_LONGITUD);
}

export const MENSAJE: Record<Exclude<ResultadoVerificacion, "ok">, string> = {
  incorrecto: "El código no coincide. Revísalo e inténtalo otra vez.",
  caducado: "El código ha caducado. Pide uno nuevo.",
  sin_codigo: "Aún no has pedido un código. Pulsa «Enviar código».",
  bloqueado: `Demasiados intentos. Pide un código nuevo para seguir.`,
};
