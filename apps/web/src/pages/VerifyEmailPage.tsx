import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import {
  CODIGO_LONGITUD,
  ESPERA_REENVIO_S,
  MENSAJE,
  limpiarCodigo,
  verifier,
  type EnvioCodigo,
} from "../lib/emailVerification";
import { destinoSeguro, getSession, markVerified } from "../lib/session";

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const destino = destinoSeguro(params.get("next"));
  const sesion = getSession();
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const [envio, setEnvio] = useState<EnvioCodigo | null>(null);
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [comprobando, setComprobando] = useState(false);
  const [espera, setEspera] = useState(0);
  const [hecho, setHecho] = useState(false);

  // Cuenta atrás del reenvío: se ve cuánto falta en lugar de un botón que no responde.
  useEffect(() => {
    if (espera <= 0) return;
    const t = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [espera]);

  if (!sesion) return <Navigate to="/login" replace />;
  if (sesion.verificado && !hecho) return <Navigate to={destino} replace />;
  const email = sesion.email;

  async function enviar() {
    setEnviando(true);
    setError(null);
    setCodigo("");
    try {
      setEnvio(await verifier.sendCode(email));
      setEspera(ESPERA_REENVIO_S);
      requestAnimationFrame(() => inputRef.current?.focus());
    } catch {
      setError("No se pudo enviar el código. Inténtalo de nuevo en unos segundos.");
    } finally {
      setEnviando(false);
    }
  }

  async function confirmar(e: FormEvent) {
    e.preventDefault();
    if (codigo.length !== CODIGO_LONGITUD) return;
    setComprobando(true);
    try {
      const r = await verifier.confirm(email, codigo);
      if (r === "ok") {
        markVerified();
        setHecho(true);
        setTimeout(() => navigate(destino, { replace: true }), 900);
        return;
      }
      setError(MENSAJE[r]);
      if (r === "caducado" || r === "bloqueado") setEnvio(null);
      inputRef.current?.select();
    } finally {
      setComprobando(false);
    }
  }

  const caducaA = envio
    ? new Date(envio.caducaEn).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <AppShell>
      <div className="mx-auto max-w-[440px] pt-4 sm:pt-10">
        <div className="panel px-6 py-7 sm:px-8">
          <span aria-hidden="true" className="grid size-12 place-items-center rounded-full bg-accent-soft text-accent-ink">
            <svg viewBox="0 0 20 20" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              {hecho ? <path d="M4.5 10.5l3.5 3.5 7.5-8" /> : <path d="M3 5.5h14v9H3zM3.5 6l6.5 5 6.5-5" />}
            </svg>
          </span>

          {hecho ? (
            <div role="status">
              <h1 className="mt-5 font-display text-[26px] font-bold tracking-[-0.025em]">Correo verificado</h1>
              <p className="mt-2 text-muted">Gracias. Te llevamos de vuelta…</p>
            </div>
          ) : (
            <>
              <h1 className="mt-5 font-display text-[26px] font-bold tracking-[-0.025em]">Verifica tu correo</h1>
              <p className="mt-2 text-muted">
                Te enviaremos un código de {CODIGO_LONGITUD} cifras a <strong className="text-ink">{email}</strong>.
                Sirve para que las propuestas lleguen a la persona correcta.
              </p>

              {!envio ? (
                <button type="button" onClick={enviar} disabled={enviando} aria-busy={enviando} className="btn-primary mt-6 h-12 w-full text-[15px]">
                  {enviando ? "Enviando…" : "Enviar código"}
                </button>
              ) : (
                <form onSubmit={confirmar} noValidate className="mt-6">
                  <label htmlFor={`${id}-codigo`} className="label">Código de verificación</label>
                  <input
                    ref={inputRef}
                    id={`${id}-codigo`}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]*"
                    maxLength={CODIGO_LONGITUD + 2}
                    value={codigo}
                    onChange={(e) => {
                      setCodigo(limpiarCodigo(e.target.value));
                      setError(null);
                    }}
                    placeholder={"0".repeat(CODIGO_LONGITUD)}
                    aria-invalid={Boolean(error)}
                    aria-describedby={`${id}-ayuda${error ? ` ${id}-error` : ""}`}
                    className={`field num h-14 text-center font-display text-[26px] font-semibold tracking-[0.5em] placeholder:tracking-[0.5em] ${error ? "border-negative" : ""}`}
                  />
                  <p id={`${id}-ayuda`} className="mt-1.5 text-meta text-muted">
                    Válido hasta las {caducaA}. Puedes pegarlo tal cual.
                  </p>
                  {envio.codigoDemo && (
                    <p className="mt-3 rounded-control bg-pill-warn-bg px-3 py-2 text-meta text-pill-warn-ink">
                      Modo demo: no se envían correos. Tu código es <strong className="num">{envio.codigoDemo}</strong>.
                    </p>
                  )}

                  <button
                    type="submit"
                    disabled={codigo.length !== CODIGO_LONGITUD || comprobando}
                    aria-busy={comprobando}
                    className="btn-primary mt-5 h-12 w-full text-[15px]"
                  >
                    {comprobando ? "Comprobando…" : "Verificar"}
                  </button>
                  <button type="button" onClick={enviar} disabled={espera > 0 || enviando} className="btn-ghost mt-2 w-full">
                    {espera > 0 ? `Reenviar código en ${espera} s` : "Reenviar código"}
                  </button>
                </form>
              )}

              {error && (
                <p id={`${id}-error`} role="alert" className="field-error mt-3">
                  <svg aria-hidden="true" viewBox="0 0 20 20" className="size-[18px] flex-none" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10 6.5v4M10 13.5h.01M10 2.5l7.5 13h-15z" />
                  </svg>
                  {error}
                </p>
              )}

              <Link to={destino} className="mt-6 block text-center text-meta text-muted underline hover:text-ink">
                Ahora no, verificar más tarde
              </Link>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
