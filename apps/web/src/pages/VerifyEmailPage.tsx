import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { AlertaFormulario, AuthLayout } from "../components/AuthLayout";
import { CODIGO_LONGITUD, ESPERA_REENVIO_S, limpiarCodigo, mensajeVerificacion, VIGENCIA_MIN } from "../lib/emailVerification";
import { destinoSeguro } from "../lib/session";
import type { EstadoVerificacion } from "./RegisterPage";

/** Verificación del correo con el código que envía la API (`POST /auth/verify`). */
export function VerifyEmailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const email = (params.get("email") ?? "").trim().toLowerCase();
  const next = params.get("next");
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const [codigoDev, setCodigoDev] = useState<string | undefined>(
    () => (location.state as EstadoVerificacion | null)?.codigoDev,
  );
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [bloqueado, setBloqueado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [comprobando, setComprobando] = useState(false);
  const [reenviando, setReenviando] = useState(false);
  const [espera, setEspera] = useState(0);
  const [hecho, setHecho] = useState(false);

  // Cuenta atrás del reenvío: se ve cuánto falta en lugar de un botón que no responde.
  useEffect(() => {
    if (espera <= 0) return;
    const t = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [espera]);

  if (!email) return <Navigate to="/registro" replace />;
  const loginTras = `/login?verificado=1&email=${encodeURIComponent(email)}${next ? `&next=${encodeURIComponent(destinoSeguro(next))}` : ""}`;

  async function reenviar() {
    setReenviando(true);
    setError(null);
    setAviso(null);
    setCodigo("");
    try {
      const r = await api.resendCode(email);
      setCodigoDev(r?.verificacion?.codigo_dev ?? r?.codigo_dev);
      setBloqueado(false);
      setAviso(`Te hemos enviado un código nuevo. Vale ${VIGENCIA_MIN} minutos.`);
      setEspera(ESPERA_REENVIO_S);
      requestAnimationFrame(() => inputRef.current?.focus());
    } catch (e) {
      setError(e instanceof ApiError ? `No se pudo reenviar el código: ${e.message}` : "No se pudo conectar con la API.");
    } finally {
      setReenviando(false);
    }
  }

  async function confirmar(e: FormEvent) {
    e.preventDefault();
    if (codigo.length !== CODIGO_LONGITUD) return;
    setComprobando(true);
    setAviso(null);
    try {
      await api.verify({ email, codigo });
      setHecho(true);
      setTimeout(() => navigate(loginTras, { replace: true }), 900);
    } catch (err) {
      setError(mensajeVerificacion(err));
      if (err instanceof ApiError && err.status === 429) {
        setBloqueado(true);
        setCodigoDev(undefined);
      }
      inputRef.current?.select();
    } finally {
      setComprobando(false);
    }
  }

  return (
    <AuthLayout>
      <span aria-hidden="true" className="grid size-12 place-items-center rounded-full bg-accent-soft text-accent-ink">
        <svg viewBox="0 0 20 20" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          {hecho ? <path d="M4.5 10.5l3.5 3.5 7.5-8" /> : <path d="M3 5.5h14v9H3zM3.5 6l6.5 5 6.5-5" />}
        </svg>
      </span>

      {hecho ? (
        <div role="status">
          <h1 className="mt-5 font-display text-[26px] font-bold tracking-[-0.025em]">Correo verificado</h1>
          <p className="mt-2 text-muted">Gracias. Ahora inicia sesión…</p>
        </div>
      ) : (
        <>
          <h1 className="mt-5 font-display text-[26px] font-bold tracking-[-0.025em]">Verifica tu correo</h1>
          <p className="mt-2 text-muted">
            Escribe el código de {CODIGO_LONGITUD} cifras que hemos enviado a <strong className="text-ink">{email}</strong>.
            Caduca a los {VIGENCIA_MIN} minutos.
          </p>

          {codigoDev && (
            <p className="mt-4 rounded-control bg-pill-warn-bg px-3 py-2 text-meta text-pill-warn-ink" data-testid="codigo-dev">
              Modo demo: la API no envía correos. Tu código es <strong className="num">{codigoDev}</strong>.
            </p>
          )}

          <form onSubmit={confirmar} noValidate className="mt-6">
            <label htmlFor={`${id}-codigo`} className="label">Código de verificación</label>
            <input
              ref={inputRef}
              id={`${id}-codigo`}
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              pattern="[0-9]*"
              maxLength={CODIGO_LONGITUD + 2}
              value={codigo}
              disabled={bloqueado}
              onChange={(e) => {
                setCodigo(limpiarCodigo(e.target.value));
                setError(null);
              }}
              placeholder={"0".repeat(CODIGO_LONGITUD)}
              aria-invalid={Boolean(error)}
              aria-describedby={`${id}-ayuda${error ? ` ${id}-error` : ""}`}
              className={`field num h-14 text-center font-display text-[26px] font-semibold tracking-[0.5em] placeholder:tracking-[0.5em] ${error ? "border-negative" : ""}`}
            />
            <p id={`${id}-ayuda`} className="mt-1.5 text-meta text-muted">Puedes pegarlo tal cual.</p>

            {error && (
              <div className="mt-3" id={`${id}-error`}>
                <AlertaFormulario>{error}</AlertaFormulario>
              </div>
            )}
            {aviso && (
              <p role="status" className="mt-3 text-meta text-muted">{aviso}</p>
            )}

            <button
              type="submit"
              disabled={codigo.length !== CODIGO_LONGITUD || comprobando || bloqueado}
              aria-busy={comprobando}
              className="btn-primary mt-5 h-12 w-full text-[15px]"
            >
              {comprobando ? "Comprobando…" : "Verificar"}
            </button>
            <button type="button" onClick={reenviar} disabled={espera > 0 || reenviando} className="btn-ghost mt-2 w-full">
              {reenviando ? "Enviando…" : espera > 0 ? `Reenviar código en ${espera} s` : "Pedir un código nuevo"}
            </button>
          </form>

          <Link to="/login" className="mt-6 block text-center text-meta text-muted underline hover:text-ink">
            Volver a iniciar sesión
          </Link>
        </>
      )}
    </AuthLayout>
  );
}
