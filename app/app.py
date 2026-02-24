
import os
from pathlib import Path
import sys
from functools import wraps

from flask import Blueprint, Flask, flash, jsonify, request, redirect, session, url_for, send_from_directory
from flask_migrate import Migrate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from models import db, Asset, EntityVersion, Signal, OptimisticLockError

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent / "static"), static_url_path="/static")
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)

ENTITY_MODELS = {
    "signals": Signal,
    "assets": Asset,
}


def _active_user():
    return session.get("active_user", "system")


def _set_actor():
    db.session.info["actor"] = _active_user()


def _expected_lock_version_from_request():
    raw = request.form.get("lock_version") or (request.get_json(silent=True) or {}).get("lock_version")
    try:
        return int(raw) if raw is not None else 0
    except (ValueError, TypeError):
        return 0


def require_optimistic_lock(Model):
    """Set session.info so before_flush can check lock_version. Apply to edit/delete views."""
    id_param = Model.__tablename__.rstrip("s") + "_id"

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            entity_id = kwargs.get(id_param)
            if entity_id is None:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Missing entity id"}), 400
                return redirect(url_for("index"))
            db.session.info["expected_entity"] = (Model.__tablename__, entity_id)
            db.session.info["expected_lock_version"] = _expected_lock_version_from_request()
            return f(*args, **kwargs)
        return wrapped
    return decorator


@app.errorhandler(OptimisticLockError)
def handle_optimistic_lock_error(exc):
    if request.path.startswith("/api/"):
        return jsonify({"error": str(exc)}), 409
    flash(str(exc), "error")
    return redirect(url_for("index"))


def signal_to_dict(signal):
    return {
        "id": signal.id,
        "frequency": signal.frequency,
        "modulation": signal.modulation,
        "power": signal.power,
        "created_by": signal.created_by,
        "updated_by": signal.updated_by,
        "lock_version": signal.lock_version,
    }


def asset_to_dict(asset):
    return {
        "id": asset.id,
        "name": asset.name,
        "description": asset.description,
        "signal_ids": sorted(s.id for s in asset.signals),
        "created_by": asset.created_by,
        "updated_by": asset.updated_by,
        "lock_version": asset.lock_version,
    }


def version_to_dict(v):
    return {
        "id": v.id,
        "entity_type": v.entity_type,
        "entity_id": v.entity_id,
        "version": v.version,
        "operation": v.operation,
        "snapshot": v.snapshot,
        "diff": v.diff,
        "hash": v.hash,
        "changed_at": v.changed_at.isoformat() if v.changed_at else None,
        "changed_by": v.changed_by,
    }


api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/session", methods=["GET"])
def api_session_get():
    return jsonify({"active_user": _active_user()})


@api_bp.route("/session", methods=["POST"])
def api_session_post():
    data = request.get_json(silent=True) or {}
    session["active_user"] = (data.get("active_user") or "system").strip() or "system"
    return jsonify({"active_user": session["active_user"]})


@api_bp.route("/signals", methods=["GET"])
def api_signals_list():
    signals = Signal.query.filter_by(is_deleted=False).order_by(Signal.id.desc()).all()
    return jsonify([signal_to_dict(s) for s in signals])


@api_bp.route("/signals", methods=["POST"])
def api_signals_create():
    _set_actor()
    data = request.get_json(silent=True) or {}
    signal = Signal(
        frequency=float(data.get("frequency", 0)),
        modulation=str(data.get("modulation", "")),
        power=float(data.get("power", 0)),
    )
    db.session.add(signal)
    db.session.commit()
    return jsonify(signal_to_dict(signal)), 201


@api_bp.route("/signals/<int:signal_id>", methods=["PATCH"])
@require_optimistic_lock(Signal)
def api_signals_update(signal_id):
    _set_actor()
    signal = Signal.query.filter_by(id=signal_id, is_deleted=False).first()
    if not signal:
        return jsonify({"error": "Signal not found"}), 404
    data = request.get_json(silent=True) or {}
    signal.frequency = float(data.get("frequency", signal.frequency))
    signal.modulation = str(data.get("modulation", signal.modulation))
    signal.power = float(data.get("power", signal.power))
    db.session.commit()
    return jsonify(signal_to_dict(signal))


@api_bp.route("/signals/<int:signal_id>", methods=["DELETE"])
@require_optimistic_lock(Signal)
def api_signals_delete(signal_id):
    _set_actor()
    signal = Signal.query.filter_by(id=signal_id, is_deleted=False).first()
    if not signal:
        return jsonify({"error": "Signal not found"}), 404
    signal.soft_delete(_active_user())
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_bp.route("/assets", methods=["GET"])
def api_assets_list():
    assets = Asset.query.filter_by(is_deleted=False).order_by(Asset.id.desc()).all()
    return jsonify([asset_to_dict(a) for a in assets])


@api_bp.route("/assets", methods=["POST"])
def api_assets_create():
    _set_actor()
    data = request.get_json(silent=True) or {}
    signal_ids = data.get("signal_ids") or []
    signals = Signal.query.filter(Signal.id.in_(signal_ids), Signal.is_deleted.is_(False)).all() if signal_ids else []
    asset = Asset(
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        signals=signals,
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify(asset_to_dict(asset)), 201


@api_bp.route("/assets/<int:asset_id>", methods=["PATCH"])
@require_optimistic_lock(Asset)
def api_assets_update(asset_id):
    _set_actor()
    asset = Asset.query.filter_by(id=asset_id, is_deleted=False).first()
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    data = request.get_json(silent=True) or {}
    signal_ids = data.get("signal_ids") or []
    selected_signals = Signal.query.filter(Signal.id.in_(signal_ids), Signal.is_deleted.is_(False)).all() if signal_ids else []
    asset.name = str(data.get("name", asset.name))
    asset.description = str(data.get("description", asset.description))
    asset.signals = selected_signals
    db.session.commit()
    return jsonify(asset_to_dict(asset))


@api_bp.route("/assets/<int:asset_id>", methods=["DELETE"])
@require_optimistic_lock(Asset)
def api_assets_delete(asset_id):
    _set_actor()
    asset = Asset.query.filter_by(id=asset_id, is_deleted=False).first()
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
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
        return jsonify({"error": "Unknown entity type"}), 404
    versions = (
        EntityVersion.query
        .filter_by(entity_type=model.__tablename__, entity_id=entity_id)
        .order_by(EntityVersion.version.desc())
        .all()
    )
    return jsonify([version_to_dict(v) for v in versions])


app.register_blueprint(api_bp)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def spa_fallback(path):
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "8000"))
    app.run(host=host, port=port, debug=True)
