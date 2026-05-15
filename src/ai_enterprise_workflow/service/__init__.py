"""HTTP service layer (Flask app exposing /predict and /logs)."""

from ai_enterprise_workflow.service.api import app

__all__ = ["app"]
