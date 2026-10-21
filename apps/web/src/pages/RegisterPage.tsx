import { useId, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { AlertaFormulario, AuthLayout, CampoEmail, CampoPassword, Icono, Spinner } from "../components/AuthLayout";
import { EMAIL, ICONOS } from "../components/iconos";
import { destinoSeguro, rememberEmail } from "../lib/session";
import { MIN_PASSWORD } from "../types/auth";

/** Lo que la pantalla de verificación recibe al llegar desde el registro. */
export interface EstadoVerificacion {
  codigoDev?: string;
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next");
  const id = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);

  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tocado, setTocado] = useState({ email: false, password: false });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<{ mensaje: string; existe?: boolean } | null>(null);

  const limpio = email.trim().toLowerCase();
  const errorEmail = EMAIL.test(limpio) ? null : "Escribe un correo con la forma nombre@dominio.com.";
  const errorPassword = password.length >= MIN_PASSWORD ? null : `Usa al menos ${MIN_PASSWORD} caracteres.`;
  const conNext = next ? `&next=${encodeURIComponent(destinoSeguro(next))}` : "";

  async function registrar(e: FormEvent) {
    e.preventDefault();
    setTocado({ email: true, password: true });
    if (errorEmail || errorPassword) {
      (errorEmail ? emailRef : passRef).current?.focus();
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const r = await api.register({ email: limpio, password, ...(nombre.trim() ? { nombre: nombre.trim() } : {}) });
      rememberEmail(r.user.email);
      const estado: EstadoVerificacion = { codigoDev: r.verificacion.codigo_dev };
      navigate(`/verificar?email=${encodeURIComponent(r.user.email)}${conNext}`, { state: estado });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError({ mensaje: "Ya hay una cuenta con ese correo.", existe: true });
      } else if (err instanceof ApiError && err.status === 422) {
        setError({ mensaje: `La API no aceptó los datos: ${err.message}` });
      } else {
        setError({ mensaje: err instanceof ApiError ? `La API respondió ${err.status}: ${err.message}` : "No se pudo conectar con la API." });
      }
      setEnviando(false);
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-[28px] font-bold tracking-[-0.025em]">Crea tu cuenta</h1>
      <p className="mt-1.5 text-muted">Tus estudios y su seguimiento quedan guardados en tu cuenta; nadie más los ve.</p>

      <form noValidate onSubmit={registrar} className="mt-8 space-y-5">
        {error && (
          <AlertaFormulario>
            {error.mensaje}{" "}
            {error.existe && (
              <Link to={`/login?email=${encodeURIComponent(limpio)}${conNext}`} className="font-semibold underline">
                Inicia sesión
              </Link>
            )}
          </AlertaFormulario>
        )}

        <div>
          <label htmlFor={`${id}-nombre`} className="label">
            Nombre <span className="font-normal text-muted">(opcional)</span>
          </label>
          <div className="field-icon">
            <Icono d={ICONOS.user} className="text-faint" />
            <input id={`${id}-nombre`} autoComplete="name" value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus />
          </div>
        </div>
        <CampoEmail
          id={`${id}-email`}
          inputRef={emailRef}
          value={email}
          onChange={setEmail}
          onBlur={() => setTocado((t) => ({ ...t, email: true }))}
          error={tocado.email ? errorEmail : null}
          valido={tocado.email && !errorEmail}
        />
        <CampoPassword
          id={`${id}-password`}
          inputRef={passRef}
          value={password}
          onChange={setPassword}
          onBlur={() => setTocado((t) => ({ ...t, password: true }))}
          error={tocado.password ? errorPassword : null}
          autoComplete="new-password"
          ayuda={`Al menos ${MIN_PASSWORD} caracteres.`}
        />

        <button type="submit" className="btn-primary h-12 w-full text-[15px]" disabled={enviando} aria-busy={enviando}>
          {enviando ? (
            <>
              <Spinner /> Creando la cuenta…
            </>
          ) : (
            "Crear cuenta"
          )}
        </button>
        <p className="text-center text-meta text-muted">Te enviaremos un código de 6 cifras para verificar el correo.</p>
      </form>

      <p className="mt-6 text-center text-body text-muted">
        ¿Ya tienes cuenta?{" "}
        <Link to={`/login${next ? `?next=${encodeURIComponent(destinoSeguro(next))}` : ""}`} className="font-semibold text-ink underline hover:no-underline">
          Inicia sesión
        </Link>
      </p>
    </AuthLayout>
  );
}
