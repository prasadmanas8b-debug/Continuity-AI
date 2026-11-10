from fastapi import APIRouter

from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.claims import router as claims_router
from app.api.v1.cold_start import router as cold_start_router
from app.api.v1.conflicts import router as conflicts_router
from app.api.v1.extractions import router as extractions_router
from app.api.v1.handovers import router as handovers_router
from app.api.v1.projects import router as projects_router
from app.api.v1.sources import router as sources_router
from app.core.config import settings
from app.schemas.models import MetaResponse

api_v1_router = APIRouter(prefix="/api/v1")


@api_v1_router.get("/meta", response_model=MetaResponse, tags=["Meta"])
def get_meta():
    llm_mode = "live" if settings.LLM_PROVIDER != "fake" else "fake"
    return MetaResponse(
        contract_version=settings.CONTRACT_VERSION,
        app_version=settings.APP_VERSION,
        auth_mode="demo",
        llm_mode=llm_mode,
    )


api_v1_router.include_router(auth_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(sources_router)
api_v1_router.include_router(extractions_router)
api_v1_router.include_router(claims_router)
api_v1_router.include_router(conflicts_router)
api_v1_router.include_router(handovers_router)
api_v1_router.include_router(cold_start_router)
api_v1_router.include_router(audit_router)
