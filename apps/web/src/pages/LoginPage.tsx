import { useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { RegistrationMarks } from "../components/RegistrationMarks";
import { ThemeToggle } from "../components/ThemeToggle";
import { LogoMark, Wordmark } from "../components/Wordmark";
import { destinoSeguro, lastEmail, nombreDesde, saveSession } from "../lib/session";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const MIN_PASSWORD = 6;
const DEMO = { email: "demo@posiq.app", password: "demo1234" };

/** Tres pasos, no más: lo que el producto hace cabe de un vistazo (ley de Miller). */
const PASOS = [
  ["Lee tu brief", "y propone el mercado: tu marca, sus competidores y el líder."],
  ["Mide la visibilidad", "en ChatGPT, Gemini, Perplexity y Claude."],
  ["Propone un plan", "con cada acción enlazada a los hallazgos que la justifican."],
] as const;
/** Los aros del logotipo, de fuera adentro: magenta, cian, amarillo. */
const DOTS = ["bg-brand-magenta", "bg-brand-cyan", "bg-brand-yellow"] as const;

function Icono({ d, className = "" }: { d: string; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className={`size-[18px] flex-none ${className}`} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

const I = {
  mail: "M3 5.5h14v9H3zM3.5 6l6.5 5 6.5-5",
  lock: "M5.5 9h9v7.5h-9zM7 9V6.8a3 3 0 0 1 6 0V9",
  eye: "M2 10s3-5.5 8-5.5S18 10 18 10s-3 5.5-8 5.5S2 10 2 10ZM10 12.3a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6Z",
  eyeOff: "M3 3l14 14M8.3 8.4a2.3 2.3 0 0 0 3.3 3.2M6 5.7C3.6 7 2 10 2 10s3 5.5 8 5.5c1.4 0 2.6-.4 3.7-1M10.5 4.5C15.2 4.8 18 10 18 10s-.7 1.3-2 2.7",
  alert: "M10 6.5v4M10 13.5h.01M10 2.5l7.5 13h-15z",
  check: "M4.5 10.5l3.5 3.5 7.5-8",
};

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const destino = destinoSeguro(params.get("next"));
  const id = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);

  const [email, setEmail] = useState(lastEmail);
  const [password, setPassword] = useState("");
  const [verPassword, setVerPassword] = useState(false);
  const [recordar, setRecordar] = useState(true);
  const [tocado, setTocado] = useState({ email: false, password: false });
  const [mayusculas, setMayusculas] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const errorEmail = EMAIL.test(email.trim()) ? null : "Escribe un correo con la forma nombre@dominio.com.";
  const errorPassword = password.length >= MIN_PASSWORD ? null : `La contraseña necesita al menos ${MIN_PASSWORD} caracteres.`;
  const valido = !errorEmail && !errorPassword;
  const verErrorEmail = tocado.email && errorEmail;
  const verErrorPassword = tocado.password && errorPassword;

  function detectarMayusculas(e: KeyboardEvent<HTMLInputElement>) {
    setMayusculas(e.getModifierState("CapsLock"));
  }

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
    // Sin servicio de cuentas: una pausa breve deja ver que la acción se ha recibido.
    await new Promise((r) => setTimeout(r, 450));
    const limpio = email.trim().toLowerCase();
    saveSession({ email: limpio, nombre: nombreDesde(limpio) }, recordar);
    navigate(destino, { replace: true });
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      {/* Panel de marca: en móvil se reduce a una franja para que el formulario quede a mano. */}
      <aside className="login-hero relative flex flex-col justify-between overflow-hidden px-6 pb-8 pt-6 sm:px-10 lg:px-14 lg:py-12">
        {/* La diana del logotipo a gran tamaño, recortada en la esquina y atenuada: decorativa. */}
        <LogoMark className="pointer-events-none absolute -bottom-24 -right-24 hidden size-[420px] opacity-80 lg:block" />

        <span className="relative">
          <Wordmark className="text-[30px]" />
        </span>

        <div className="relative mt-8 max-w-[36rem] lg:mt-0">
          <h1 className="text-[56px] leading-[1.02] sm:text-[76px] lg:text-[96px]">¿Te recomienda la IA?</h1>
          <p className="tracked mt-6 text-white/85">Lo que hace posiq.</p>
          <p className="mt-2 max-w-[28rem] text-[15px] leading-relaxed text-white/80 sm:text-base">
            Mide cuánto aparece tu marca cuando alguien pregunta a ChatGPT, Gemini, Perplexity o Claude, la compara con
            tu competencia y te propone qué hacer.
          </p>

          <ol className="mt-8 hidden max-w-[22rem] gap-5 sm:grid">
            {PASOS.map(([titulo, texto], i) => (
              <li key={titulo} className="flex gap-3.5">
                <span aria-hidden="true" className={`dot mt-1.5 ${DOTS[i]}`} />
                <p className="text-[14px] leading-snug text-white/80">
                  <strong className="block text-[16px] font-bold text-white">
                    {i + 1}. {titulo}
                  </strong>
                  {texto}
                </p>
              </li>
            ))}
          </ol>
        </div>

        <p className="tracked relative mt-8 hidden text-white/60 lg:block">Hackatón EPS UFV · Zona D</p>
      </aside>

      <main id="contenido" className="relative flex items-center justify-center px-4 py-10 sm:px-8">
        <RegistrationMarks className="!absolute" />
        <div className="absolute right-4 top-4 sm:right-6">
          <ThemeToggle />
        </div>

        <div className="w-full max-w-[400px]">
          <h2 className="font-display text-[44px] font-light uppercase leading-none tracking-[0.01em]">Inicia sesión</h2>
          <p className="mt-1.5 text-muted">Entra para crear y revisar los estudios de tu marca.</p>

          <form noValidate onSubmit={entrar} className="mt-8 space-y-5" aria-describedby={`${id}-ayuda`}>
            <div>
              <label htmlFor={`${id}-email`} className="label">Correo</label>
              <div className={`field-icon ${verErrorEmail ? "is-invalid" : ""}`}>
                <Icono d={I.mail} className="text-faint" />
                <input
                  ref={emailRef}
                  id={`${id}-email`}
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  autoFocus={!email}
                  placeholder="nombre@empresa.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={() => setTocado((t) => ({ ...t, email: true }))}
                  aria-invalid={Boolean(verErrorEmail)}
                  aria-describedby={verErrorEmail ? `${id}-email-error` : undefined}
                />
                {tocado.email && !errorEmail && <Icono d={I.check} className="text-positive" />}
              </div>
              {verErrorEmail && (
                <p id={`${id}-email-error`} className="field-error">
                  <Icono d={I.alert} /> {errorEmail}
                </p>
              )}
            </div>

            <div>
              <label htmlFor={`${id}-password`} className="label">Contraseña</label>
              <div className={`field-icon ${verErrorPassword ? "is-invalid" : ""}`}>
                <Icono d={I.lock} className="text-faint" />
                <input
                  ref={passRef}
                  id={`${id}-password`}
                  type={verPassword ? "text" : "password"}
                  autoComplete="current-password"
                  autoFocus={Boolean(email)}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onBlur={() => setTocado((t) => ({ ...t, password: true }))}
                  onKeyDown={detectarMayusculas}
                  onKeyUp={detectarMayusculas}
                  aria-invalid={Boolean(verErrorPassword)}
                  aria-describedby={[verErrorPassword && `${id}-password-error`, mayusculas && `${id}-caps`].filter(Boolean).join(" ") || undefined}
                />
                <button
                  type="button"
                  onClick={() => setVerPassword((v) => !v)}
                  aria-label={verPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-pressed={verPassword}
                  className="-mr-1.5 grid size-9 flex-none place-items-center rounded-control text-muted hover:bg-raised hover:text-ink"
                >
                  <Icono d={verPassword ? I.eyeOff : I.eye} />
                </button>
              </div>
              {verErrorPassword && (
                <p id={`${id}-password-error`} className="field-error">
                  <Icono d={I.alert} /> {errorPassword}
                </p>
              )}
              {mayusculas && (
                <p id={`${id}-caps`} role="status" className="mt-1.5 flex items-center gap-1.5 text-meta text-pill-warn-ink">
                  <Icono d={I.alert} /> Tienes activadas las mayúsculas.
                </p>
              )}
            </div>

            <label className="flex w-fit cursor-pointer items-center gap-2.5 text-body">
              <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} className="size-[18px] accent-[var(--accent)]" />
              Recordarme en este navegador
            </label>

            <div>
              <button type="submit" className="btn-ink h-12 w-full text-[15px]" disabled={!valido || enviando} aria-busy={enviando}>
                {enviando ? (
                  <>
                    <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent" />
                    Entrando…
                  </>
                ) : (
                  "Entrar"
                )}
              </button>
              <p id={`${id}-ayuda`} aria-live="polite" className="mt-2 min-h-4 text-center text-meta text-muted">
                {!valido && !enviando ? "Completa el correo y la contraseña para entrar." : ""}
              </p>
            </div>
          </form>

          <div className="my-6 flex items-center gap-3 text-meta text-faint" aria-hidden="true">
            <span className="h-px flex-1 bg-line" /> o <span className="h-px flex-1 bg-line" />
          </div>

          <button type="button" onClick={usarDemo} className="btn-secondary h-11 w-full">
            Usar la cuenta de demostración
          </button>
          <p className="mt-6 text-center text-meta text-muted">
            Demo sin servidor de cuentas: la sesión solo se guarda en este navegador.
          </p>
        </div>
      </main>
    </div>
  );
}
