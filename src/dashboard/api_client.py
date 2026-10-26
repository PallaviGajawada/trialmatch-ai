"""API client for communication between Streamlit dashboard and FastAPI backend."""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import ValidationError

from src.matching.schema import ScreeningReport

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://127.0.0.1:8000"


class ApiClientError(Exception):
    """Base exception for TrialMatch API client operations."""


class BackendConnectionError(ApiClientError):
    """Raised when the backend server cannot be reached."""


class BackendTimeoutError(ApiClientError):
    """Raised when an API request times out."""


class BackendHttpError(ApiClientError):
    """Raised when the backend returns a non-2xx HTTP status code."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class BackendResponseError(ApiClientError):
    """Raised when the backend returns a malformed or invalid response payload."""


class TrialMatchApiClient:
    """Client for interacting with the TrialMatch AI FastAPI backend."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        raw_url = base_url or os.environ.get("TRIALMATCH_API_URL", DEFAULT_API_URL)
        self.base_url = raw_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def check_health(self) -> Dict[str, Any]:
        """
        Query GET /health to verify backend connectivity and agent readiness.

        Returns:
            Dictionary containing health response data.

        Raises:
            BackendConnectionError: If server cannot be reached.
            BackendTimeoutError: If request times out.
            BackendHttpError: If server returns error code.
        """
        url = f"{self.base_url}/health"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url)
                if response.status_code != 200:
                    raise BackendHttpError(
                        status_code=response.status_code,
                        detail=response.text or "Health check failed.",
                    )
                return response.json()
        except httpx.ConnectError as err:
            raise BackendConnectionError(
                f"Unable to connect to backend at {self.base_url}. Ensure the FastAPI server is running."
            ) from err
        except httpx.TimeoutException as err:
            raise BackendTimeoutError(
                f"Connection to backend timed out after {self.timeout_seconds}s."
            ) from err
        except (BackendHttpError, BackendConnectionError, BackendTimeoutError):
            raise
        except Exception as exc:
            raise ApiClientError(f"Unexpected error querying /health: {exc}") from exc

    def evaluate(
        self,
        patient_id: str,
        trial_id: str,
        agent_results: Optional[List[Dict[str, Any]]] = None,
        required_agents: Optional[List[str]] = None,
        required_criteria: Optional[List[str]] = None,
    ) -> ScreeningReport:
        """
        Submit an eligibility evaluation request to POST /api/v1/evaluate.

        Args:
            patient_id: Identifier of the patient to evaluate.
            trial_id: Identifier of the target clinical trial.
            agent_results: Optional pre-collected agent findings.
            required_agents: Optional list of required agent IDs.
            required_criteria: Optional list of required criterion IDs.

        Returns:
            ScreeningReport instance validated from the backend response.

        Raises:
            BackendConnectionError: If server cannot be reached.
            BackendTimeoutError: If request times out.
            BackendHttpError: If server returns 4xx/500 error.
            BackendResponseError: If response is malformed.
        """
        url = f"{self.base_url}/api/v1/evaluate"
        payload: Dict[str, Any] = {
            "patient_id": patient_id,
            "trial_id": trial_id,
        }
        if agent_results is not None:
            payload["agent_results"] = agent_results
        if required_agents is not None:
            payload["required_agents"] = required_agents
        if required_criteria is not None:
            payload["required_criteria"] = required_criteria

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload)

                if response.status_code != 200:
                    try:
                        err_body = response.json()
                        detail = err_body.get("detail", response.text)
                    except Exception:
                        detail = response.text or "Evaluation failed."
                    raise BackendHttpError(
                        status_code=response.status_code,
                        detail=str(detail),
                    )

                data = response.json()
        except httpx.ConnectError as err:
            raise BackendConnectionError(
                f"Unable to connect to backend at {self.base_url}. Ensure the FastAPI server is running."
            ) from err
        except httpx.TimeoutException as err:
            raise BackendTimeoutError(
                f"Evaluation request timed out after {self.timeout_seconds}s."
            ) from err
        except (BackendHttpError, BackendConnectionError, BackendTimeoutError):
            raise
        except Exception as exc:
            raise ApiClientError(f"Network error during evaluation request: {exc}") from exc

        try:
            return ScreeningReport.model_validate(data)
        except ValidationError as val_err:
            raise BackendResponseError(
                f"Backend returned malformed ScreeningReport payload: {val_err}"
            ) from val_err
        except Exception as exc:
            raise BackendResponseError(
                f"Failed to parse backend evaluation response: {exc}"
            ) from exc
