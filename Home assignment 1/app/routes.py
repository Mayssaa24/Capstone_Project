from flask import Blueprint, current_app, jsonify, render_template, request

from app.errors import InvalidImageError

bp = Blueprint("main", __name__)


def _services():
    return current_app.extensions["services"]


@bp.get("/")
def index():
    return render_template("index.html", region=_services().rules.region)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/api/dashboard")
def dashboard():
    return jsonify(_services().dashboard.build())


@bp.post("/api/scan")
def scan():
    services = _services()
    upload = request.files.get("image")
    if upload is None:
        raise InvalidImageError("No image was uploaded (field name: 'image').")

    results = services.classifier.classify(upload.read())
    if not results:
        return jsonify({"status": "uncertain",
                        "message": "I'm not sure what this is. Try a closer, brighter photo "
                                   "with a single item.",
                        "dashboard": services.dashboard.build()})

    decision = services.rules.decide(results[0])
    advice = services.coach.advise(decision)
    services.repository.add(decision)
    return jsonify({"status": "ok", "decision": decision.to_dict(),
                    "alternatives": [r.to_dict() for r in results[1:]],
                    "advice": advice.to_dict(), "dashboard": services.dashboard.build()})
