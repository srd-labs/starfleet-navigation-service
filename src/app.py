from flask import Flask, jsonify
import logging
import json
import os
from datetime import datetime, timezone
from google.cloud import storage

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


@app.route("/api/navigation/gcp-status")
def gcp_status():
    secret_path = "/mnt/secrets/navigation-service-secret"

    try:
        # Validate that the Secret Manager value is mounted into the pod.
        secret_loaded = os.path.isfile(secret_path) and os.path.getsize(secret_path) > 0

        # Use Application Default Credentials.
        # In GKE this resolves through Workload Identity.
        storage_client = storage.Client()

        bucket_name = "starfleet-gke-platform-lab-navigation-data"
        bucket = storage_client.bucket(bucket_name)

        # Make a real authenticated request to Cloud Storage.
        blobs = list(bucket.list_blobs(max_results=1))

        return {
            "service": "navigation",
            "secret_loaded": secret_loaded,
            "workload_identity": "authenticated",
            "gcp_service": "cloud-storage",
            "bucket": bucket_name,
            "bucket_access": "success"
        }, 200

    except Exception as e:
        return {
            "service": "navigation",
            "secret_loaded": os.path.isfile(secret_path),
            "gcp_service": "cloud-storage",
            "bucket_access": "failed",
            "error": str(e)
        }, 500


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
