"""API de posiq.: `uvicorn posiq.interfaces.api.main:app`.

- `POST /studies` crea el estudio y lanza el grafo en segundo plano → `{study_id}`.
- `GET /studies/{id}` estado, revisión pendiente, coste, errores y lo producido hasta ahora.
- `POST /studies/{id}/resume` reanuda una revisión (`competidores` o `plan`) → 202.
- `GET /studies/{id}/export?formato=docx|pdf` Word o PDF (409 sin propuesta; PDF sin soffice, 503).
- `GET /studies/{id}/evaluations?ids=a,b` evidencias: evaluación con motor, prompt y respuesta.
- `GET /studies/{id}/traces` trazas del estudio (modelo, tokens, coste por llamada).
- `GET /estimate?modo=&n_prompts=&n_motores=&repeticiones=` coste estimado antes de ejecutar.
- `GET /studies?brand_id=` lista de estudios.
- `GET /health`.

`POST /studies` acepta JSON `{brief_texto, modo}`, un fichero subido como cuerpo (`text/markdown`,
`text/plain` o `.docx`, con `?modo=`) o un formulario multipart con `fichero` y `modo` (este último
requiere `python-multipart`).
"""

import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import ValidationError

from posiq.adapters.export import DocxExporter, PdfExporter, SofficeNotFoundError
from posiq.application.deps import db
from posiq.application.estimate import (
    KIT_MOTORES,
    KIT_PROMPTS,
    KIT_REPETICIONES,
    CostEstimate,
    estimate_study,
)
from posiq.application.runner import ResumeError, StudyRunner
from posiq.domain.schemas import ModoEstudio, Study, Trace
from posiq.interfaces.api.schemas import (
    Evidence,
    ResumeAccepted,
    ResumeBody,
    StudyCreate,
    StudyCreated,
    StudyView,
)
from posiq.interfaces.api.views import evidence
from posiq.interfaces.api.wiring import runner_from_settings
from posiq.settings import Settings

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT_TYPES = ("text/markdown", "text/plain", "text/x-markdown")
LOCALHOST = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


def docx_text(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(p for p in parts if p.strip())


def file_text(nombre: str, content_type: str, data: bytes) -> str:
    if content_type.startswith(DOCX) or nombre.lower().endswith(".docx"):
        return docx_text(data)
    if content_type.startswith(TEXT_TYPES) or nombre.lower().endswith((".md", ".txt")):
        return data.decode("utf-8-sig")
    raise HTTPException(
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"formato no admitido: {content_type or nombre}"
    )


async def read_brief(request: Request, modo: ModoEstudio | None) -> StudyCreate:
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("application/json"):
            return StudyCreate.model_validate(await request.json())
        if content_type.startswith("multipart/form-data"):
            try:
                form = await request.form()
            except AssertionError as exc:  # Starlette sin python-multipart
                raise HTTPException(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    "multipart no disponible en este servidor; envía JSON o el fichero como "
                    "cuerpo (Content-Type text/markdown o .docx) con ?modo=",
                ) from exc
            fichero = form.get("fichero")
            texto = form.get("brief_texto")
            if fichero is not None and not isinstance(fichero, str):
                texto = file_text(
                    fichero.filename or "", fichero.content_type or "", await fichero.read()
                )
            return StudyCreate.model_validate(
                {"brief_texto": texto, "modo": form.get("modo") or modo or "kit"}
            )
        nombre = request.query_params.get("nombre", "")
        texto = file_text(nombre, content_type, await request.body())
        return StudyCreate.model_validate({"brief_texto": texto, "modo": modo or "kit"})
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, exc.errors(include_url=False)
        ) from exc


def create_app(runner: StudyRunner | None = None, settings: Settings | None = None) -> FastAPI:
    """App con `runner` inyectado (tests) o construido desde `settings` al arrancar."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if runner is not None:
            yield
            return
        app.state.settings = settings or Settings()
        async with runner_from_settings(app.state.settings) as built:
            app.state.runner = built
            yield

    app = FastAPI(title="posiq.", lifespan=lifespan)
    app.state.runner = runner
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCALHOST,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_runner(request: Request) -> StudyRunner:
        current: StudyRunner | None = request.app.state.runner
        if current is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "la API aún no ha arrancado")
        return current

    def get_study(r: StudyRunner, study_id: str) -> Study:
        try:
            return r.repo.get_study(study_id)
        except KeyError:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"no existe el estudio {study_id}"
            ) from None

    def get_settings(request: Request) -> Settings:
        current: Settings | None = request.app.state.settings
        return current or Settings()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/studies", status_code=status.HTTP_201_CREATED)
    async def create_study(
        request: Request,
        background: BackgroundTasks,
        modo: Annotated[ModoEstudio | None, Query()] = None,
    ) -> StudyCreated:
        r = get_runner(request)
        body = await read_brief(request, modo)
        try:
            study = r.create(body.modo)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        background.add_task(r.start, study, body.brief_texto)
        return StudyCreated(study_id=study.id)

    @app.get("/studies")
    async def list_studies(request: Request, brand_id: str | None = None) -> list[Study]:
        return get_runner(request).repo.list_studies(brand_id)

    @app.get("/studies/{study_id}")
    async def read_study(request: Request, study_id: str) -> StudyView:
        r = get_runner(request)
        study = get_study(r, study_id)
        values, _ = await r.state(study_id)
        errores = list(values.get("errores", []))
        if study_id in r.fallos:
            errores.append(r.fallos[study_id])
        # El grafo guarda "none" en su estado; la web recibe null.
        pendiente = values.get("revision_pendiente", "none")
        return StudyView(
            study=study,
            estado=r.estado(study),  # type: ignore[arg-type]
            revision_pendiente=None if pendiente == "none" else pendiente,
            coste_acumulado_eur=values.get("coste_acumulado_eur", 0.0),
            errores=errores,
            brief=values.get("brief"),
            market=values.get("market"),
            metrics=values.get("metrics"),
            findings=values.get("findings"),
            plan=values.get("plan"),
            simulacion=values.get("simulacion"),
            calidad_plan=values.get("calidad_plan"),
            proposal=values.get("proposal"),
        )

    @app.post("/studies/{study_id}/resume", status_code=status.HTTP_202_ACCEPTED)
    async def resume_study(
        request: Request, study_id: str, body: ResumeBody, background: BackgroundTasks
    ) -> ResumeAccepted:
        r = get_runner(request)
        get_study(r, study_id)
        try:
            await r.check_resume(study_id, body.revision, body.payload)
        except ResumeError as exc:
            code = (
                status.HTTP_409_CONFLICT if exc.conflict else status.HTTP_422_UNPROCESSABLE_CONTENT
            )
            raise HTTPException(code, str(exc)) from exc
        r.en_marcha.add(study_id)  # evita un segundo resume antes de que arranque el primero
        background.add_task(r.resume, study_id, body.payload)
        return ResumeAccepted(study_id=study_id, revision=body.revision)

    @app.get("/studies/{study_id}/evaluations")
    async def read_evaluations(request: Request, study_id: str, ids: str = "") -> list[Evidence]:
        r = get_runner(request)
        get_study(r, study_id)
        values, _ = await r.state(study_id)
        return evidence(values, [i for i in ids.split(",") if i])

    @app.get("/studies/{study_id}/traces")
    async def read_traces(request: Request, study_id: str) -> list[Trace]:
        r = get_runner(request)
        get_study(r, study_id)
        values, _ = await r.state(study_id)
        return list(values.get("traces", []))

    @app.get("/estimate")
    async def estimate(
        request: Request,
        modo: ModoEstudio,
        n_prompts: Annotated[int, Query(ge=1)] = KIT_PROMPTS,
        n_motores: Annotated[int, Query(ge=1)] = KIT_MOTORES,
        repeticiones: Annotated[int, Query(ge=1)] = KIT_REPETICIONES,
    ) -> CostEstimate:
        return estimate_study(
            modo,
            get_settings(request),
            n_prompts=n_prompts,
            n_motores=n_motores,
            repeticiones=repeticiones,
        )

    @app.get("/studies/{study_id}/export")
    async def export_study(
        request: Request, study_id: str, formato: Literal["docx", "pdf"] = "docx"
    ) -> Any:
        r = get_runner(request)
        get_study(r, study_id)
        values, _ = await r.state(study_id)
        proposal = values.get("proposal")
        if proposal is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "la propuesta aún no está completada")
        from posiq.ports import Exporter

        exporter: Exporter = DocxExporter() if formato == "docx" else PdfExporter()
        try:
            data = await db(exporter.render, proposal, formato=formato)
        except SofficeNotFoundError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
        return Response(
            data,
            media_type=DOCX if formato == "docx" else "application/pdf",
            headers={"Content-Disposition": f'attachment; filename="posiq-{study_id}.{formato}"'},
        )

    return app


app = create_app()
