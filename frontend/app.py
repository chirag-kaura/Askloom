
from flask import Flask, render_template
from urllib.request import urlopen
import json

app = Flask(__name__)

BACKEND_URL = "http://127.0.0.1:8000"


@app.route("/")
@app.route("/dashboard")
@app.route("/assessments")
@app.route("/profile")
def home():
    """Render the Askloom application for all tabs."""
    return render_template("index.html")


@app.route("/api/health")
def backend_health():
    """Check the FastAPI backend through Flask."""
    try:
        with urlopen(f"{BACKEND_URL}/health", timeout=3) as response:
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
    app.run(debug=True, port=5000)
