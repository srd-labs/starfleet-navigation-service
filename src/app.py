from flask import Flask, jsonify
import logging
import json
import os
from datetime import datetime, timezone

COMMIT_ID = os.getenv("COMMIT_ID", "local")
RELEASE_VERSION = os.getenv("RELEASE_VERSION", "dev")

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


def log_event(message, level="INFO"):
    log_entry = {
        "service": "navigation",
        "level": level,
        "message": message,
    }

    logging.info(json.dumps(log_entry))


@app.route("/health_metadata")
def health_metadata():
    return jsonify(
        service="starfleet-navigation-service",
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        commit_id=COMMIT_ID,
        release_version=RELEASE_VERSION,
    )


@app.route("/")
def home():
    log_event("Navigation service homepage requested")

    return jsonify(
        service="starfleet-navigation-service",
        status="operational",
        quadrant="alpha",
    )


@app.route("/health")
def health():
    return jsonify(
        status="healthy"
    )


@app.route("/api/navigation")
def navigation():
    log_event("Navigation data requested")

    return jsonify(
        destination="Vulcan",
        warp_factor=5,
        status="course-plotted",
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )
