"""FastAPI application entrypoint for TrialMatch AI backend."""

from __future__ import annotations

import logging
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.dependencies import get_coordinator
from src.api.schemas import EvaluationRequest, HealthResponse
from src.matching.coordinator import EligibilityCoordinator
from src.matching.schema import (
    EvaluationCounts,
    OverallStatus,
    ScreeningReport,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="TrialMatch AI API",
        description="Multi-Agent Patient Eligibility Matching Backend for Clinical Trials",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request validation error on %s: %s", request.url.path, exc.errors()
        )
        formatted_errors = []
        for err in exc.errors():
            loc = " -> ".join(str(loc_item) for loc_item in err.get("loc", []))
            formatted_errors.append(f"{loc}: {err.get('msg')}")
        return JSONResponse(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            content={
                "detail": "Request validation failed.",
                "errors": formatted_errors,
            },
        )

    @application.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled server exception on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred during eligibility evaluation. Please contact system support.",
            },
        )

    @application.get("/health", response_model=HealthResponse, tags=["Health"])
    def health_check(
        coordinator: EligibilityCoordinator = Depends(get_coordinator),
    ) -> HealthResponse:
        """
        Check health status and readiness of the backend.

        Does not claim operational eligibility pipeline if agents are unconfigured.
        """
        agents_count = len(coordinator.registered_agents)
        agents_configured = agents_count > 0
        pipeline_status = (
            "operational"
            if agents_configured
            else "agents_unconfigured_pipeline_incomplete"
        )
        return HealthResponse(
            status="ok",
            service="trialmatch-ai-backend",
            version="1.0.0",
            agents_configured=agents_configured,
            pipeline_status=pipeline_status,
            registered_agents=list(coordinator.registered_agents.keys()),
        )

    @application.post(
        "/api/v1/evaluate",
        response_model=ScreeningReport,
        tags=["Evaluation"],
        summary="Evaluate Patient Eligibility for a Clinical Trial",
    )
    def evaluate_patient(
        request: EvaluationRequest,
        coordinator: EligibilityCoordinator = Depends(get_coordinator),
    ) -> ScreeningReport:
        """
        Evaluate a patient's eligibility against clinical trial criteria.

        Uses the deterministic decision engine and preserved evidence provenance.
        """
        try:
            # If agent results were pre-collected or supplied directly
            if request.agent_results is not None:
                return coordinator.evaluate(
                    patient_id=request.patient_id,
                    trial_id=request.trial_id,
                    agent_results=request.agent_results,
                    required_agents=request.required_agents,
                    required_criteria=request.required_criteria,
                )

            # If coordinator has registered agent runners configured
            if coordinator.registered_agents:
                return coordinator.evaluate_with_agents(
                    patient_id=request.patient_id,
                    trial_id=request.trial_id,
                    required_agents=request.required_agents,
                    required_criteria=request.required_criteria,
                )

            # If no agent results provided and no agents configured on server:
            # Report that evaluation is incomplete. Do NOT fabricate successful eligibility.
            return ScreeningReport(
                patient_id=request.patient_id,
                trial_id=request.trial_id,
                overall_status=OverallStatus.REQUIRES_REVIEW,
                requires_human_review=True,
                reasons=[
                    "Evaluation is incomplete: no eligibility agents are currently registered or configured on this backend.",
                    "Person 1 eligibility agents must be implemented and registered before automated multi-agent evaluation can execute.",
                ],
                counts=EvaluationCounts(),
                criterion_results=[],
                missing_agents=list(request.required_agents or []),
                missing_criteria=list(request.required_criteria or []),
                errors=[
                    "No eligibility agents configured; unable to execute agent runners."
                ],
            )

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error during evaluation: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal error occurred during eligibility evaluation.",
            )

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.app:app", host="127.0.0.1", port=8000, reload=True)

