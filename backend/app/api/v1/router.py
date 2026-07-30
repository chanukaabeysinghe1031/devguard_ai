"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analyses,
    auth,
    dashboard,
    evaluation,
    files,
    health,
    history,
    incidents,
    notes,
    notifications,
    organizations,
    pipeline_runs,
    projects,
    reports,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(projects.router)
api_router.include_router(pipeline_runs.router)
api_router.include_router(incidents.router)
api_router.include_router(notes.router)
api_router.include_router(files.router)
api_router.include_router(analyses.router)
api_router.include_router(dashboard.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(history.router)
api_router.include_router(evaluation.router)
