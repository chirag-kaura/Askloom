

import json
import os
from urllib.request import urlopen

from flask import Flask, render_template

app = Flask(__name__)

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000",
).rstrip("/")


@app.route("/")
@app.route("/dashboard")
@app.route("/assessments")
@app.route("/profile")
def home():
    """Render the Askloom application for all tabs."""
    return render_template(
        "index.html",
        backend_url=BACKEND_URL,
    )


@app.route("/api/health")
def backend_health():
    """Check whether the FastAPI backend is running."""
    try:
        with urlopen(f"{BACKEND_URL}/health", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        return {
            "frontend": "healthy",
            "backend": data,
        }, 200

    except Exception:
        return {
            "frontend": "healthy",
            "backend": "unavailable",
        }, 503


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

