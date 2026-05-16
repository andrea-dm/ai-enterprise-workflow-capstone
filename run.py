"""Entry-point: start the Flask development server.

Notes:
    Calls :func:`~ai_enterprise_workflow.core.log_events.setup_logging` to
    configure the package logger and write JSONL events to the log directory
    before starting the server. The server port is read from the ``PORT``
    environment variable (default: ``80``).
"""

import os

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.core.log_events import setup_logging
from ai_enterprise_workflow.service import app

if __name__ == "__main__":
    setup_logging(log_dir=cfg.directory_logs)
    port = int(os.environ.get("PORT", "80"))
    app.run(host="0.0.0.0", port=port)
