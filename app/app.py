import os
from pathlib import Path
import sys
from flask import Blueprint, Flask, flash, jsonify, request, redirect, session, url_for, send_from_directory
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    verify_jwt_in_request,
)
from flask_pydantic_spec import FlaskPydanticSpec
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.orm.exc import StaleDataError

from config import Config
from models import db, Asset, EntityVersion, Signal, OptimisticLockError
from schemas import (
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    SessionResponse,
    SignalCreateRequest,
    SignalUpdateRequest,
    AssetCreateRequest,
    AssetUpdateRequest,
    signal_to_response,
    asset_to_response,
    version_to_response,
)

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent / "static"), static_url_path="/static")
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
api_spec = FlaskPydanticSpec("flask", title="Versioning API", version="1.0", path="apidoc")

ENTITY_MODELS = {
    "signals": Signal,
    "assets": Asset,
}


def _active_user():
    try:
        identity = get_jwt_identity()
        return identity or "system"
    except RuntimeError:
        return "system"


def _set_actor():
    db.session.info["actor"] = _active_user()


CONFLICT_MSG = "Conflict: entity was changed by another user. Reload and try again."


def _expected_lock_version_from_request():
    raw = request.form.get("lock_version")
    if raw is None and request.is_json:
        try:
            raw = (request.get_json(silent=True) or {}).get("lock_version")
        except Exception:
            pass
    try:
        return int(raw) if raw is not None else 0
    except (ValueError, TypeError):
        return 0


def _check_lock_version(entity, expected_version):
    """Return 409 response if entity.lock_version != expected_version; else None."""
    if entity is None:
        return None
    try:
        current = int(entity.lock_version)
    except (TypeError, ValueError):
        current = 0
    if current != expected_version:
        if request.path.startswith("/api/"):
            return jsonify(ErrorResponse(error=CONFLICT_MSG).model_dump()), 409
        flash(CONFLICT_MSG, "error")
        return redirect(url_for("index"))
    return None


@app.errorhandler(OptimisticLockError)
def handle_optimistic_lock_error(exc):
    if request.path.startswith("/api/"):
        return jsonify(ErrorResponse(error=str(exc)).model_dump()), 409
    flash(str(exc), "error")
    return redirect(url_for("index"))


@app.errorhandler(StaleDataError)
def handle_stale_data_error(exc):
    if request.path.startswith("/api/"):
        return jsonify(ErrorResponse(error=CONFLICT_MSG).model_dump()), 409
    flash(CONFLICT_MSG, "error")
    return redirect(url_for("index"))


@app.errorhandler(ValidationError)
def handle_validation_error(exc):
    if request.path.startswith("/api/"):
        msg = exc.errors()[0].get("msg", "Validation error") if exc.errors() else "Validation error"
        return jsonify(ErrorResponse(error=msg).model_dump()), 422
    return jsonify(ErrorResponse(error="Invalid request").model_dump()), 422


api_bp = Blueprint("api", __name__, url_prefix="/api")


def _api_path_no_jwt():
    """Paths that do not require JWT (login, openapi, apidoc)."""
    path = request.path or ""
    return (
        path.endswith("/auth/login")
        or "/openapi" in path
        or "/apidoc" in path
    )


@api_bp.before_request
def require_jwt_for_api():
    if _api_path_no_jwt():
        return None
    try:
        verify_jwt_in_request(optional=False)
    except Exception:
        return jsonify(ErrorResponse(error="Authorization required").model_dump()), 401
    return None


@api_bp.route("/auth/login", methods=["POST"])
def api_auth_login():
    """Login with username/password. Demo: test_user / test_pass."""
    try:
        body = request.get_json(force=True, silent=True) or {}
        req = LoginRequest.model_validate(body)
    except ValidationError as e:
        return jsonify(ErrorResponse(error=e.errors()[0].get("msg", "Validation error")).model_dump()), 422
    if req.username != app.config["DEMO_USERNAME"] or req.password != app.config["DEMO_PASSWORD"]:
        return jsonify(ErrorResponse(error="Invalid username or password").model_dump()), 401
    token = create_access_token(identity=req.username)
    return jsonify(LoginResponse(access_token=token, user=req.username).model_dump()), 200


@api_bp.route("/session", methods=["GET"])
def api_session_get():
    return jsonify(SessionResponse(active_user=_active_user()).model_dump())


@api_bp.route("/signals", methods=["GET"])
def api_signals_list():
    signals = Signal.query.filter_by(is_deleted=False).order_by(Signal.id.desc()).all()
    return jsonify([signal_to_response(s) for s in signals])


@api_bp.route("/signals", methods=["POST"])
def api_signals_create():
    _set_actor()
    body = request.get_json(silent=True) or {}
    req = SignalCreateRequest.model_validate(body)
    signal = Signal(
        frequency=req.frequency,
        modulation=req.modulation,
        power=req.power,
    )
    db.session.add(signal)
    db.session.commit()
    return jsonify(signal_to_response(signal)), 201


@api_bp.route("/signals/<int:signal_id>", methods=["PATCH"])
def api_signals_update(signal_id):
    _set_actor()
    signal = Signal.query.filter_by(id=signal_id, is_deleted=False).first()
    if not signal:
        return jsonify(ErrorResponse(error="Signal not found").model_dump()), 404
    conflict = _check_lock_version(signal, _expected_lock_version_from_request())
    if conflict is not None:
        return conflict
    body = request.get_json(silent=True) or {}
    req = SignalUpdateRequest.model_validate(body)
    previous_lock = signal.lock_version
    if req.frequency is not None:
        signal.frequency = req.frequency
    if req.modulation is not None:
        signal.modulation = req.modulation
    if req.power is not None:
        signal.power = req.power
    db.session.commit()
    updated = signal.lock_version != previous_lock
    return jsonify(signal_to_response(signal, updated=updated))


@api_bp.route("/signals/<int:signal_id>", methods=["DELETE"])
def api_signals_delete(signal_id):
    _set_actor()
    signal = Signal.query.filter_by(id=signal_id, is_deleted=False).first()
    if not signal:
        return jsonify(ErrorResponse(error="Signal not found").model_dump()), 404
    conflict = _check_lock_version(signal, _expected_lock_version_from_request())
    if conflict is not None:
        return conflict
    signal.soft_delete(_active_user())
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_bp.route("/assets", methods=["GET"])
def api_assets_list():
    assets = Asset.query.filter_by(is_deleted=False).order_by(Asset.id.desc()).all()
    return jsonify([asset_to_response(a) for a in assets])


@api_bp.route("/assets", methods=["POST"])
def api_assets_create():
    _set_actor()
    body = request.get_json(silent=True) or {}
    req = AssetCreateRequest.model_validate(body)
    signals = (
        Signal.query.filter(Signal.id.in_(req.signal_ids), Signal.is_deleted.is_(False)).all()
        if req.signal_ids
        else []
    )
    asset = Asset(name=req.name, description=req.description, signals=signals)
    db.session.add(asset)
    db.session.commit()
    return jsonify(asset_to_response(asset)), 201


@api_bp.route("/assets/<int:asset_id>", methods=["PATCH"])
def api_assets_update(asset_id):
    _set_actor()
    asset = Asset.query.filter_by(id=asset_id, is_deleted=False).first()
    if not asset:
        return jsonify(ErrorResponse(error="Asset not found").model_dump()), 404
    conflict = _check_lock_version(asset, _expected_lock_version_from_request())
    if conflict is not None:
        return conflict
    body = request.get_json(silent=True) or {}
    req = AssetUpdateRequest.model_validate(body)
    previous_lock = asset.lock_version
    if req.name is not None:
        asset.name = req.name
    if req.description is not None:
        asset.description = req.description
    if req.signal_ids is not None:
        selected = (
            Signal.query.filter(Signal.id.in_(req.signal_ids), Signal.is_deleted.is_(False)).all()
            if req.signal_ids
            else []
        )
        asset.signals = selected
    db.session.commit()
    updated = asset.lock_version != previous_lock
    return jsonify(asset_to_response(asset, updated=updated))


@api_bp.route("/assets/<int:asset_id>", methods=["DELETE"])
def api_assets_delete(asset_id):
    _set_actor()
    asset = Asset.query.filter_by(id=asset_id, is_deleted=False).first()
    if not asset:
        return jsonify(ErrorResponse(error="Asset not found").model_dump()), 404
    conflict = _check_lock_version(asset, _expected_lock_version_from_request())
    if conflict is not None:
        return conflict
    asset.soft_delete(_active_user())
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_bp.route("/trash", methods=["GET"])
def api_trash_list():
    deleted_items = []
    for signal in Signal.query.filter_by(is_deleted=True).all():
        deleted_items.append({
            "entity_type": "signals",
            "id": signal.id,
            "name": signal.trash_name,
            "deleted_at": signal.deleted_at.isoformat() if signal.deleted_at else None,
            "deleted_by": signal.deleted_by,
        })
    for asset in Asset.query.filter_by(is_deleted=True).all():
        deleted_items.append({
            "entity_type": "assets",
            "id": asset.id,
            "name": asset.trash_name,
            "deleted_at": asset.deleted_at.isoformat() if asset.deleted_at else None,
            "deleted_by": asset.deleted_by,
        })
    deleted_items.sort(key=lambda x: x["deleted_at"] or "", reverse=True)
    return jsonify(deleted_items)


@api_bp.route("/versions/<entity_type>/<int:entity_id>", methods=["GET"])
def api_versions_list(entity_type, entity_id):
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return jsonify(ErrorResponse(error="Unknown entity type").model_dump()), 404
    versions = (
        EntityVersion.query
        .filter_by(entity_type=model.__tablename__, entity_id=entity_id)
        .order_by(EntityVersion.version.desc())
        .all()
    )
    return jsonify([version_to_response(v) for v in versions])


app.register_blueprint(api_bp)
api_spec.register(app)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def spa_fallback(path):
    if path.startswith("api/"):
        return jsonify(ErrorResponse(error="Not found").model_dump()), 404
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "8000"))
    app.run(host=host, port=port, debug=True)
