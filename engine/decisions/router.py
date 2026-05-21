"""Router for unified decisioning."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from engine.auth.models import Tenant
from engine.decisions.schemas import (
    UnifiedDecisionEvaluateRequest,
    UnifiedDecisionEvaluateResponse,
)
from engine.decisions.service import UnifiedDecisionService
from engine.dependencies import (
    get_db,
    get_detection_engine,
    get_registry,
    verify_api_key,
)
from engine.detection.engine import DetectionEngine
from engine.rulesets.registry import RulesetRegistry

router = APIRouter(prefix="/v1/decisions", tags=["decisions"])


@router.post("/evaluate", response_model=UnifiedDecisionEvaluateResponse)
async def evaluate_unified_decision(
    body: UnifiedDecisionEvaluateRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    registry: RulesetRegistry = Depends(get_registry),
    detection_engine: DetectionEngine = Depends(get_detection_engine),
):
    service = UnifiedDecisionService(db)
    return await service.evaluate_decision(
        tenant=tenant,
        request=body,
        registry=registry,
        detection_engine=detection_engine,
    )

