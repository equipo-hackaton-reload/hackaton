import { useId, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { AlertaFormulario, AuthLayout, CampoEmail, CampoPassword, Spinner } from "../components/AuthLayout";
import { EMAIL } from "../components/iconos";
import { caducidad, destinoSeguro, lastEmail, saveSession } from "../lib/session";
import { MIN_PASSWORD } from "../types/auth";

/** La cuenta de demostración solo existe en el mock; contra la API real no se ofrece. */
const DEMO = { email: "demo@posiq.app", password: "demo1234" };
const HAY_DEMO = import.meta.env.VITE_USE_MOCKS === "true" || import.meta.env.MODE === "test";

type Fallo = { tipo: "credenciales" } | { tipo: "no_verificado" } | { tipo: "otro"; mensaje: string };

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next");
  const destino = destinoSeguro(next);
  const id = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);

  const [email, setEmail] = useState(() => params.get("email") ?? lastEmail());
  const [password, setPassword] = useState("");
  const [recordar, setRecordar] = useState(false);
  const [tocado, setTocado] = useState({ email: false, password: false });
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const recienVerificado = params.get("verificado") === "1";

  const limpio = email.trim().toLowerCase();
  const errorEmail = EMAIL.test(limpio) ? null : "Escribe un correo con la forma nombre@dominio.com.";
  const errorPassword = password.length >= MIN_PASSWORD ? null : `La contraseña tiene al menos ${MIN_PASSWORD} caracteres.`;
  const valido = !errorEmail && !errorPassword;
  const conNext = next ? `&next=${encodeURIComponent(destino)}` : "";

  function usarDemo() {
    setEmail(DEMO.email);
    setPassword(DEMO.password);
    setTocado({ email: true, password: true });
  }

  async function entrar(e: FormEvent) {
    e.preventDefault();
    setTocado({ email: true, password: true });
    if (!valido) {
      (errorEmail ? emailRef : passRef).current?.focus();
      return;
    }
    setEnviando(true);
    setFallo(null);
    try {
      const r = await api.login({ email: limpio, password });
      saveSession({ token: r.token, expiraEn: caducidad(r.expira_en), user: r.user }, recordar);
      navigate(destino, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setFallo({ tipo: "credenciales" });
      else if (err instanceof ApiError && err.status === 403 && err.message === "correo_no_verificado") {
        setFallo({ tipo: "no_verificado" });
      } else {
        setFallo({
          tipo: "otro",
          mensaje: err instanceof ApiError ? `La API respondió ${err.status}: ${err.message}` : "No se pudo conectar con la API.",
        });
      }
      setEnviando(false);
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-[28px] font-bold tracking-[-0.025em]">Inicia sesión</h1>
      <p className="mt-1.5 text-muted">Entra para crear y seguir los estudios de tu marca.</p>

      {recienVerificado && !fallo && (
        <p role="status" className="mt-6 rounded-control bg-pill-pos-bg px-3 py-2.5 text-pill-pos-ink">
          Correo verificado. Ya puedes entrar.
        </p>
      )}

      <form noValidate onSubmit={entrar} className="mt-8 space-y-5">
        {fallo && (
          <AlertaFormulario id={`${id}-fallo`}>
            {fallo.tipo === "credenciales" && "Correo o contraseña incorrectos."}
            {fallo.tipo === "no_verificado" && (
              <>
                Aún no has verificado {limpio}.{" "}
                <Link to={`/verificar?email=${encodeURIComponent(limpio)}${conNext}`} className="font-semibold underline">
                  Verificar el correo
                </Link>
              </>
            )}
            {fallo.tipo === "otro" && fallo.mensaje}
          </AlertaFormulario>
        )}

        <CampoEmail
          id={`${id}-email`}
          inputRef={emailRef}
          value={email}
          onChange={setEmail}
          onBlur={() => setTocado((t) => ({ ...t, email: true }))}
          error={tocado.email ? errorEmail : null}
          valido={tocado.email && !errorEmail}
          autoFocus={!email}
        />
        <CampoPassword
          id={`${id}-password`}
          inputRef={passRef}
          value={password}
          onChange={setPassword}
          onBlur={() => setTocado((t) => ({ ...t, password: true }))}
          error={tocado.password ? errorPassword : null}
          autoComplete="current-password"
          autoFocus={Boolean(email)}
        />

        <label className="flex w-fit cursor-pointer items-center gap-2.5 text-body">
          <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} className="size-[18px] accent-[var(--accent)]" />
          Recordarme en este navegador
        </label>

        <button type="submit" className="btn-primary h-12 w-full text-[15px]" disabled={enviando} aria-busy={enviando}>
          {enviando ? (
            <>
              <Spinner /> Entrando…
            </>
          ) : (
            "Entrar"
          )}
        </button>
      </form>

      <p className="mt-6 text-center text-body text-muted">
        ¿No tienes cuenta?{" "}
        <Link to={`/registro${next ? `?next=${encodeURIComponent(destino)}` : ""}`} className="font-semibold text-ink underline hover:no-underline">
          Crear una cuenta
        </Link>
      </p>

      {HAY_DEMO && (
        <>
          <div className="my-6 flex items-center gap-3 text-meta text-faint" aria-hidden="true">
            <span className="h-px flex-1 bg-line" /> o <span className="h-px flex-1 bg-line" />
          </div>
          <button type="button" onClick={usarDemo} className="btn-secondary h-11 w-full">
            Usar la cuenta de demostración
          </button>
          <p className="mt-3 text-center text-meta text-muted">Solo con los mocks activados (VITE_USE_MOCKS).</p>
        </>
      )}
    </AuthLayout>
  );
}
