"""Failure category reference data endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_failure_category_repository
from app.infrastructure.repositories.failure_category_repository import FailureCategoryRepository
from app.schemas import FailureCategoryResponse

router = APIRouter(prefix="/failure-categories", tags=["Failure Categories"])


@router.get("", response_model=list[FailureCategoryResponse], summary="List active failure categories")
async def list_failure_categories(
    repo: FailureCategoryRepository = Depends(get_failure_category_repository),
) -> list[FailureCategoryResponse]:
    categories = await repo.list_active()
    return [FailureCategoryResponse.model_validate(c) for c in categories]
