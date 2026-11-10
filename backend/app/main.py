import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import (
    ContinuityException,
    continuity_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.db.session import db
from app.schemas.models import HealthResponse

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    # Initialize DB schema and auto-seed if empty
    db.init_db()
    try:
        user_count = db.query_one("SELECT COUNT(*) as c FROM users")
        if user_count and user_count["c"] == 0:
            from app.seed import seed_database
            seed_database()
    except Exception:
        pass

    app = FastAPI(
        title="Continuity AI API",
        description="Evidence-first project knowledge handover platform API specification and backend",
        version=settings.CONTRACT_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS configuration supporting Bearer token auth and X-Request-ID exposure across origins
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    use_wildcard = not origins or "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[] if use_wildcard else origins,
        allow_origin_regex=".*" if use_wildcard else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Request ID middleware
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # Exception handlers
    app.add_exception_handler(ContinuityException, continuity_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Liveness route
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    def health_check():
        return HealthResponse(status="ok")

    # API v1 routes
    app.include_router(api_v1_router)

    # Serve pre-built React frontend at / if frontend/dist is present
    if (FRONTEND_DIST / "index.html").exists():
        if (FRONTEND_DIST / "assets").exists():
            app.mount(
                "/assets",
                StaticFiles(directory=str(FRONTEND_DIST / "assets")),
                name="frontend_assets",
            )

        @app.get("/", include_in_schema=False)
        def serve_frontend_root():
            return FileResponse(str(FRONTEND_DIST / "index.html"))

    return app


app = create_app()
