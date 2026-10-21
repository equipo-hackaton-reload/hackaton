import { useId, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useCreateStudy, useEstimate } from "../api/hooks";
import briefEjemplo from "../assets/brief-ejemplo.md?raw";
import { AppShell } from "../components/AppShell";
import { PageTitle } from "../components/PageTitle";
import { fmtEur, fmtInt } from "../lib/format";
import type { ModoEstudio } from "../types/schemas";

const MODOS: { value: ModoEstudio; label: string; detail: string }[] = [
  {
    value: "kit",
    label: "Kit",
    detail: "Usa las respuestas del kit del reto (624 ejecuciones). Los motores no cuestan nada.",
  },
  {
    value: "real",
    label: "Real",
    detail: "Pregunta de verdad a ChatGPT, Gemini, Perplexity y Claude. Tiene coste.",
  },
];

const PASOS = [
  ["Lee el brief", "y propone el mercado: tu marca, sus competidores y el líder."],
  ["Revisas los competidores", "antes de gastar nada en medir."],
  ["Mide la visibilidad", "en los cuatro asistentes y calcula el Score de Citación."],
  ["Revisas el plan", "de acción, enlazado a los hallazgos que lo justifican."],
  ["Redacta la propuesta", "para el comité, en Word o PDF."],
] as const;
/** Los aros del logotipo como viñetas; el número del paso dice el orden, el color solo acompaña. */
const DOTS = ["bg-brand-magenta", "bg-brand-cyan", "bg-brand-yellow", "bg-brand-coral"] as const;

function Estimacion() {
  const q = useEstimate(true);
  if (q.isPending) return <p className="text-muted">Calculando la estimación…</p>;
  if (q.isError || !q.data) {
    return <p className="text-muted">La API no ha devuelto una estimación de coste.</p>;
  }
  const { llamadas, coste_estimado_eur, presupuesto_max_eur } = q.data;
  const excede = coste_estimado_eur > presupuesto_max_eur;
  return (
    <dl className="grid grid-cols-3 gap-3" data-testid="estimacion">
      <div>
        <dt className="text-meta text-muted">Llamadas</dt>
        <dd className="num mt-0.5 text-section font-medium">{fmtInt(llamadas)}</dd>
      </div>
      <div>
        <dt className="text-meta text-muted">Coste estimado</dt>
        <dd className={`num mt-0.5 text-section font-medium ${excede ? "text-negative" : ""}`}>
          {fmtEur(coste_estimado_eur)}
        </dd>
      </div>
      <div>
        <dt className="text-meta text-muted">Tope</dt>
        <dd className="num mt-0.5 text-section text-muted">{fmtEur(presupuesto_max_eur)}</dd>
      </div>
    </dl>
  );
}

export function NewStudyPage() {
  const navigate = useNavigate();
  const create = useCreateStudy();
  const [brief, setBrief] = useState("");
  const [modo, setModo] = useState<ModoEstudio>("kit");
  const [origen, setOrigen] = useState<string | null>(null);
  const [errorFichero, setErrorFichero] = useState<string | null>(null);
  const briefId = useId();
  const ayudaId = useId();

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!/\.(md|txt)$/i.test(file.name)) {
      setErrorFichero("Sube el brief como .md o .txt. Si lo tienes en Word, copia y pega el texto.");
      return;
    }
    setErrorFichero(null);
    setOrigen(file.name);
    setBrief(await file.text());
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!brief.trim()) return;
    create.mutate(
      { brief_texto: brief, modo },
      { onSuccess: ({ study_id }) => navigate(`/studies/${study_id}/competidores`) },
    );
  }

  const palabras = brief.trim() ? brief.trim().split(/\s+/).length : 0;

  return (
    <AppShell>
      <PageTitle
        title="Nuevo estudio"
        subtitle="Pega el brief de la marca: posiq. medirá cuánto la recomiendan los asistentes de IA frente a su competencia."
      />
      <form onSubmit={onSubmit} className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="panel overflow-hidden p-5 pt-6">
          <div aria-hidden="true" className="brand-stripe -mx-5 -mt-6 mb-5 h-1" />
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <label htmlFor={briefId} className="text-body font-medium">
              Brief de la marca
            </label>
            <div className="-mr-2 flex items-center gap-1">
              <button
                type="button"
                className="btn-ghost h-8 px-2.5"
                onClick={() => {
                  setBrief(briefEjemplo);
                  setOrigen("brief de ejemplo del kit");
                  setErrorFichero(null);
                }}
              >
                Usar el brief de ejemplo
              </button>
              <label className="btn-ghost h-8 cursor-pointer px-2.5 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent">
                Subir .md o .txt
                <input
                  type="file"
                  accept=".md,.txt,text/markdown,text/plain"
                  className="sr-only"
                  onChange={onFile}
                />
              </label>
            </div>
          </div>
          <textarea
            id={briefId}
            name="brief"
            aria-describedby={ayudaId}
            value={brief}
            onChange={(e) => {
              setBrief(e.target.value);
              setOrigen(null);
            }}
            rows={18}
            spellCheck={false}
            placeholder="Marca, sector, servicios prioritarios, públicos, ciudades, competidores, presupuesto, restricciones y objetivos…"
            className="field h-auto min-h-[360px] resize-y py-2 leading-6"
          />
          <p id={ayudaId} className="mt-2 text-meta text-muted">
            {palabras
              ? `${origen ? `Cargado el ${origen}. ` : ""}${fmtInt(palabras)} palabras.`
              : "Sigue la plantilla de brief del kit para obtener mejores resultados."}
          </p>
          {errorFichero && (
            <p role="alert" className="mt-2 text-meta text-negative">
              {errorFichero}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-6">
          <fieldset className="panel p-5">
            <legend className="float-left mb-2 text-body font-medium">Modo</legend>
            <div className="clear-left grid grid-cols-2 gap-1 rounded-control bg-raised p-1">
              {MODOS.map((m) => (
                <label
                  key={m.value}
                  className={`flex h-8 cursor-pointer items-center justify-center rounded-[5px] transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent ${
                    modo === m.value ? "bg-primary font-semibold text-on-primary" : "text-muted hover:text-ink"
                  }`}
                >
                  {modo === m.value && (
                    <svg aria-hidden="true" viewBox="0 0 12 12" className="mr-1.5 size-3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2.5 6.3 5 8.7l4.5-5.2" />
                    </svg>
                  )}
                  <input
                    type="radio"
                    name="modo"
                    value={m.value}
                    checked={modo === m.value}
                    onChange={() => setModo(m.value)}
                    className="sr-only"
                  />
                  {m.label}
                </label>
              ))}
            </div>
            <p className="mt-3 text-muted">{MODOS.find((m) => m.value === modo)!.detail}</p>
            {modo === "real" && (
              <div className="mt-4 border-t border-rule pt-4">
                <Estimacion />
              </div>
            )}
          </fieldset>

          <div>
            <button
              type="submit"
              className="btn-primary h-12 w-full text-[15px]"
              disabled={!brief.trim() || create.isPending}
            >
              {create.isPending ? "Creando el estudio…" : "Analizar"}
            </button>
            {create.isError && (
              <p role="alert" className="mt-2 text-meta text-negative">
                {create.error instanceof ApiError
                  ? `La API rechazó el brief: ${create.error.message}`
                  : "No se pudo conectar con la API. Comprueba VITE_API_URL o activa los mocks."}
              </p>
            )}
          </div>

          <section aria-labelledby="que-hace" className="px-1">
            <h2 id="que-hace" className="text-body font-semibold">
              Qué pasa al analizar
            </h2>
            <ol className="mt-3 space-y-3 text-muted">
              {PASOS.map(([accion, resto], i) => (
                <li key={accion} className="flex gap-3">
                  <span aria-hidden="true" className={`dot mt-[5px] ${DOTS[i % DOTS.length]}`} />
                  <span>
                    <span className="font-semibold text-ink">
                      {i + 1}. {accion}
                    </span>{" "}
                    {resto}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </form>
    </AppShell>
  );
}
