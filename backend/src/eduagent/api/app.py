"""FastAPI adapter around the tested learning service.

Each synchronous endpoint opens, uses and closes its SQLite connection in
the same worker thread. A shared connection is deliberately not handed
between FastAPI's dependency worker and its route worker.
"""

from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict
import logging
import sqlite3
from typing import Annotated, Iterator

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from eduagent import __version__
from eduagent.api.schemas import (
    AnswerSubmission, DecisionResponse, HealthResponse, Identifier,
    KnowledgePointResponse, MasteryItem, MasteryResponse, StartLearning,
    CitationResponse, RetrievalQuery, TutorQuestion, TutorResponse, HistoryResponse,
)
from eduagent.api.settings import APISettings
from eduagent.api.notes import notes_router
from eduagent.api.body_limit import NotesBodyLimit
from eduagent.api.knowledge import knowledge_router
from eduagent.api.workbench import workbench_router
from eduagent.api.notebooks import notebooks_router
from eduagent.api.self_assessments import self_assessments_router
from eduagent.api.study_guides import study_guides_router
from eduagent.api.documents import documents_router
from eduagent.api.architectures import architectures_router
from eduagent.api.personal_bank import personal_bank_router
from eduagent.api.course_workspaces import course_workspace_router
from eduagent.services.course_releases import CourseReleases
from eduagent.domain.architecture import ArchitectureError
from eduagent.api.upload_limit import DocumentBodyLimit
from eduagent.documents.models import DocumentError
from eduagent.documents.coordinator import DocumentCoordinator
from eduagent.services.documents import DocumentsService
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.question_extraction import QuestionExtractionService
from eduagent.documents.extraction_coordinator import ExtractionCoordinator
from eduagent.services.guidance import LearningContextChanged
from eduagent.services.knowledge import CourseSources, SourceChanged, IndexUnavailable
from eduagent.services.note_index import NoteIndexer
from eduagent.domain.notes import NoteNotFound, NoteConflict, NoteTooLarge
from eduagent.domain.catalog import Catalog
from eduagent.domain.models import SubmissionResult
from eduagent.services.learning import GoalConflict, LearningService, StudentNotFound, SubmissionConflict
from eduagent.storage.sqlite import SQLiteRepository

logger = logging.getLogger(__name__)


def create_app(settings: APISettings | None = None, *, document_runner=None, document_vision_factory=None, extraction_client_factory=None, teaching_client_factory=None) -> FastAPI:
    settings = settings or APISettings.from_environment()
    catalog: Catalog | None = None
    course_index = None
    course_sources = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal catalog, course_index, course_sources
        catalog = Catalog.load(settings.data_dir)
        # Fail at startup for corrupt data or a mismatched historical configuration.
        with SQLiteRepository(settings.db_path, allow_upgrade=False) as repository:
            learning=LearningService(catalog, repository)
            CourseReleases(learning,settings.data_dir).ensure_demo()
            if settings.retrieval_enabled:
                NoteIndexer(repository).recover()
        if settings.retrieval_enabled:
            try:
                from eduagent.retrieval.index import CourseIndex
            except ImportError:
                logger.warning('Course retrieval dependencies unavailable; install the retrieval extra')
            else:
                course_index = CourseIndex(settings.data_dir / "materials", set(catalog.knowledge))
                course_sources = CourseSources(course_index, settings.data_dir / 'materials')
        settings.document_dir.mkdir(parents=True, exist_ok=True)
        coordinator = DocumentCoordinator(document_service, settings.document_dir, document_runner, document_vision_factory)
        extraction_coordinator = ExtractionCoordinator(extraction_factory)
        try:
            yield
        finally:
            extraction_coordinator.close()
            coordinator.close()
            catalog = None
            course_index = None
            course_sources = None

    app = FastAPI(
        title="智学郑大 EduAgent", version=__version__, lifespan=lifespan,
        description="本地课程助教：规则学情闭环，可选 DeepSeek / LangGraph / FAISS 检索。",
        redoc_url=None,
    )

    def loaded_catalog() -> Catalog:
        if catalog is None:
            raise RuntimeError("应用 lifespan 尚未启动")
        return catalog

    @contextmanager
    def learning_service() -> Iterator[LearningService]:
        with SQLiteRepository(settings.db_path, allow_upgrade=False) as repository:
            repository.document_root=settings.document_dir
            yield LearningService(loaded_catalog(), repository)

    @contextmanager
    def document_service():
        with SQLiteRepository(settings.db_path, allow_upgrade=False) as repository:
            yield DocumentsService(repository, settings.document_dir, vision_enabled=settings.document_vision_enabled, agent_settings=settings.agent)

    def extraction_service(learning):
        docs=DocumentsService(learning.repository,settings.document_dir,vision_enabled=settings.document_vision_enabled,agent_settings=settings.agent)
        return QuestionExtractionService(PersonalBankService(learning,settings.data_dir/'materials'),settings.agent,docs,extraction_client_factory)

    @contextmanager
    def extraction_factory():
        with learning_service() as learning:yield extraction_service(learning)

    def mastery_view(service: LearningService, student_id: str) -> MasteryResponse:
        snapshot = service.snapshot(student_id)
        return MasteryResponse(
            student_id=snapshot.student_id, goals=list(snapshot.goals), revision=snapshot.revision,
            threshold=service.policy.threshold, parameter_version=service.parameters.version,
            mastery=[MasteryItem(
                **asdict(state), name=service.catalog.knowledge[state.knowledge_id].name,
                has_evidence=state.attempts > 0,
            ) for state in snapshot.mastery],
        )

    def error(status: int, code: str, message: str, **extra) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, **extra}})

    app.add_middleware(NotesBodyLimit)
    app.add_middleware(DocumentBodyLimit)
    app.include_router(notes_router(learning_service))
    app.include_router(knowledge_router(learning_service, lambda: course_sources, settings.retrieval_enabled))
    app.include_router(workbench_router(learning_service, lambda: course_sources, settings.retrieval_enabled, settings.agent))
    app.include_router(notebooks_router(learning_service, settings, lambda: course_sources, teaching_client_factory))
    app.include_router(self_assessments_router(learning_service))
    app.include_router(study_guides_router(learning_service, lambda: course_sources, settings.retrieval_enabled, settings.agent))
    app.include_router(documents_router(document_service, settings))
    app.include_router(architectures_router(learning_service))
    app.include_router(personal_bank_router(learning_service,settings.data_dir/'materials',extraction_service))
    app.include_router(course_workspace_router(learning_service,settings,lambda:course_sources,teaching_client_factory))
    from eduagent.api.teaching_materials import teaching_materials_router
    app.include_router(teaching_materials_router(learning_service))

    @app.exception_handler(ArchitectureError)
    async def architecture_error(request: Request, exc: ArchitectureError):
        return error(exc.status, exc.code, str(exc))

    @app.exception_handler(DocumentError)
    async def document_error(request: Request, exc: DocumentError):
        return error(exc.status, exc.code, str(exc))

    @app.exception_handler(LearningContextChanged)
    async def learning_context_changed(request: Request, exc: LearningContextChanged):
        return error(409, 'learning_context_changed', str(exc))

    @app.exception_handler(SourceChanged)
    async def source_changed(request: Request, exc: SourceChanged):
        return error(409, 'source_changed', str(exc))

    @app.exception_handler(IndexUnavailable)
    async def index_unavailable(request: Request, exc: IndexUnavailable):
        return error(503, 'index_unavailable', str(exc))

    @app.exception_handler(NoteNotFound)
    async def missing_note(request: Request, exc: NoteNotFound):
        return error(404, "note_not_found", str(exc))

    @app.exception_handler(NoteConflict)
    async def note_conflict(request: Request, exc: NoteConflict):
        return error(409, "revision_conflict", str(exc))

    @app.exception_handler(NoteTooLarge)
    async def note_too_large(request: Request, exc: NoteTooLarge):
        return error(413, "content_too_large", str(exc))

    @app.exception_handler(StudentNotFound)
    async def missing_student(request: Request, exc: StudentNotFound):
        return error(404, "student_not_found", str(exc))

    @app.exception_handler(GoalConflict)
    async def goal_conflict(request: Request, exc: GoalConflict):
        return error(409, "goal_conflict", str(exc))

    @app.exception_handler(SubmissionConflict)
    async def submission_conflict(request: Request, exc: SubmissionConflict):
        return error(409, "submission_conflict", str(exc))

    @app.exception_handler(ValueError)
    async def invalid_value(request: Request, exc: ValueError):
        return error(422, "invalid_input", str(exc))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        details = [{"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
                   for item in exc.errors()]
        return error(422, "validation_error", "请求字段不符合接口约束", details=details)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error):
        logger.error("SQLite request failed: %s", exc)
        return error(503, "storage_unavailable", "学习数据暂时不可用，请稍后重试")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        response = error(exc.status_code, "http_error", str(exc.detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.get("/health", response_model=HealthResponse, response_model_exclude_none=True, tags=["服务"])
    def health():
        with learning_service() as service:
            data = service.catalog
            return HealthResponse(
                version=__version__, question_count=len(data.questions),
                pending_review_count=sum(q.review_status == "pending" for q in data.questions.values()),
                ai_checked_count=sum(q.review_status == "ai_checked" for q in data.questions.values()) or None,
                agent_enabled=settings.agent.enabled, retrieval_available=course_index is not None,
            )

    @app.get("/api/v1/knowledge-points", response_model=list[KnowledgePointResponse], tags=["课程"])
    def knowledge_points():
        return [asdict(point) for point in loaded_catalog().knowledge.values()]

    @app.post("/api/v1/students", response_model=MasteryResponse, tags=["学习"])
    def start_learning(body: StartLearning):
        with learning_service() as service:
            service.register(body.student_id, tuple(body.goals) if body.goals is not None else None)
            return mastery_view(service, body.student_id)

    @app.get("/api/v1/students/{student_id}/mastery", response_model=MasteryResponse, tags=["学习"])
    def mastery(student_id: Identifier):
        with learning_service() as service:
            return mastery_view(service, student_id)

    @app.post("/api/v1/students/{student_id}/next", response_model=DecisionResponse, tags=["学习"])
    def next_action(student_id: Identifier):
        with learning_service() as service:
            return asdict(service.next_action(student_id))

    @app.post("/api/v1/students/{student_id}/answers", response_model=SubmissionResult, tags=["学习"])
    def submit_answer(student_id: Identifier, body: AnswerSubmission):
        with learning_service() as service:
            return service.submit(student_id, body.decision_id, body.answer, body.event_id)

    @app.post("/api/v1/materials/search", response_model=list[CitationResponse], tags=["课程"])
    def retrieve_materials(body: RetrievalQuery):
        if course_index is None:
            return error(503, "retrieval_unavailable", "请启用本地检索并安装 retrieval 依赖，不需要模型密钥")
        return course_index.search(body.query, body.knowledge_id)

    @app.post("/api/v1/students/{student_id}/tutor", response_model=TutorResponse, tags=["助教"])
    def ask_tutor(student_id: Identifier, body: TutorQuestion):
        if not settings.agent.enabled:
            return error(503, 'agent_disabled', 'Agent 未启用，本地检索仍可独立使用')
        if course_index is None:
            return error(503, "agent_disabled", "请先在本机配置并启用 Agent")
        from eduagent.agent.deepseek import DeepSeekClient
        from eduagent.agent.tutor import Tutor
        with learning_service() as service:
            return Tutor(service, course_index, DeepSeekClient(settings.agent), settings.agent).run(
                student_id, body.question,
            )

    @app.get("/api/v1/students/{student_id}/tutor-runs/{run_id}", response_model=TutorResponse, tags=["助教"])
    def tutor_run(student_id: Identifier, run_id: Identifier):
        with learning_service() as service:
            service.snapshot(student_id)
            result = service.repository.tutor_run(student_id, run_id)
            if result is None:
                return error(404, "tutor_run_not_found", "当前学生没有该助教记录")
            return result

    @app.get("/api/v1/students/{student_id}/history", response_model=HistoryResponse, tags=["学习"])
    def history(student_id: Identifier, limit: Annotated[int, Query(ge=1, le=50)] = 50):
        with learning_service() as service:
            return service.history(student_id, limit)

    @app.get("/api/v1/students/{student_id}/tutor-runs", response_model=list[TutorResponse], tags=["助教"])
    def tutor_history(student_id: Identifier, limit: Annotated[int, Query(ge=1, le=10)] = 5):
        # Reading saved runs never calls the model, including after a page reload.
        with learning_service() as service:
            service.snapshot(student_id)
            return service.repository.recent_tutor_runs(student_id, limit)

    @app.get("/", include_in_schema=False)
    def learning_page():
        index_path = settings.frontend_dir / "index.html"
        if not index_path.is_file():
            return error(503, "frontend_not_built", "请先在 frontend 目录安装依赖并运行 npm run build，然后重启后端")
        return FileResponse(index_path, headers={"Cache-Control": "no-store"})

    assets = settings.frontend_dir / "assets"
    if assets.is_dir():
        # Only compiled assets are public. Never mount the repository/data root.
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    return app
