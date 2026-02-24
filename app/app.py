
from datetime import datetime
import os
from pathlib import Path
import sys

from flask import Flask, flash, render_template, request, redirect, session, url_for
from flask_migrate import Migrate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from models import db, Asset, EntityVersion, Signal

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)

ENTITY_MODELS = {
    "signals": Signal,
    "assets": Asset,
}


def _active_user():
    return session.get("active_user", "system")


def _expected_version():
    try:
        return int(request.form.get("lock_version", "0"))
    except ValueError:
        return 0


def _check_optimistic_lock(entity, expected_version, label):
    if expected_version != entity.lock_version:
        flash(
            f"Conflict: {label} #{entity.id} was changed by another user. Reload and try again.",
            "error",
        )
        return False
    return True


def _set_actor():
    db.session.info["actor"] = _active_user()


@app.route("/active-user", methods=["POST"])
def set_active_user():
    session["active_user"] = request.form.get("active_user", "system").strip() or "system"
    return redirect(url_for("index"))


@app.route("/")
def index():
    signals = Signal.query.filter_by(is_deleted=False).order_by(Signal.id.desc()).all()
    assets = Asset.query.filter_by(is_deleted=False).order_by(Asset.id.desc()).all()
    return render_template(
        "index.html",
        active_user=_active_user(),
        signals=signals,
        assets=assets,
        all_signals=signals,
    )


@app.route("/trash")
def trash():
    deleted_items = []
    for signal in Signal.query.filter_by(is_deleted=True).all():
        deleted_items.append(
            {
                "entity_type": "signals",
                "id": signal.id,
                "name": signal.trash_name,
                "deleted_at": signal.deleted_at,
                "deleted_by": signal.deleted_by,
            }
        )
    for asset in Asset.query.filter_by(is_deleted=True).all():
        deleted_items.append(
            {
                "entity_type": "assets",
                "id": asset.id,
                "name": asset.trash_name,
                "deleted_at": asset.deleted_at,
                "deleted_by": asset.deleted_by,
            }
        )
    deleted_items.sort(key=lambda x: x["deleted_at"] or datetime.min, reverse=True)
    return render_template("trash.html", deleted_items=deleted_items)


@app.route("/signals/create", methods=["POST"])
def create_signal():
    _set_actor()
    signal = Signal(
        frequency=float(request.form["frequency"]),
        modulation=request.form["modulation"],
        power=float(request.form["power"]),
    )
    db.session.add(signal)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/signals/<int:signal_id>/edit", methods=["POST"])
def edit_signal(signal_id):
    _set_actor()
    signal = Signal.query.filter_by(id=signal_id, is_deleted=False).first_or_404()
    expected_version = _expected_version()
    if not _check_optimistic_lock(signal, expected_version, "signal"):
        return redirect(url_for("index"))

    previous_lock_version = signal.lock_version
    signal.frequency = float(request.form["frequency"])
    signal.modulation = request.form["modulation"]
    signal.power = float(request.form["power"])

    db.session.commit()
    if signal.lock_version == previous_lock_version:
        flash(f"No changes for signal #{signal.id}.", "error")
    else:
        flash(f"Signal #{signal.id} updated.", "success")
    return redirect(url_for("index"))


@app.route("/signals/<int:signal_id>/delete", methods=["POST"])
def delete_signal(signal_id):
    _set_actor()
    user = _active_user()
    signal = Signal.query.filter_by(id=signal_id, is_deleted=False).first_or_404()
    expected_version = _expected_version()
    if not _check_optimistic_lock(signal, expected_version, "signal"):
        return redirect(url_for("index"))

    signal.soft_delete(user)
    db.session.commit()
    flash(f"Signal #{signal.id} deleted (soft).", "success")
    return redirect(url_for("index"))


@app.route("/assets/create", methods=["POST"])
def create_asset():
    _set_actor()
    signal_ids = request.form.getlist("signal_ids")
    signals = Signal.query.filter(Signal.id.in_(signal_ids), Signal.is_deleted.is_(False)).all() if signal_ids else []

    asset = Asset(
        name=request.form["name"],
        description=request.form["description"],
        signals=signals,
    )
    db.session.add(asset)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/assets/<int:asset_id>/edit", methods=["POST"])
def edit_asset(asset_id):
    _set_actor()
    asset = Asset.query.filter_by(id=asset_id, is_deleted=False).first_or_404()
    expected_version = _expected_version()
    if not _check_optimistic_lock(asset, expected_version, "asset"):
        return redirect(url_for("index"))

    signal_ids = request.form.getlist("signal_ids")
    selected_signals = Signal.query.filter(Signal.id.in_(signal_ids), Signal.is_deleted.is_(False)).all() if signal_ids else []

    previous_lock_version = asset.lock_version
    asset.name = request.form["name"]
    asset.description = request.form["description"]
    asset.signals = selected_signals

    db.session.commit()
    if asset.lock_version == previous_lock_version:
        flash(f"No changes for asset #{asset.id}.", "error")
    else:
        flash(f"Asset #{asset.id} updated.", "success")
    return redirect(url_for("index"))


@app.route("/assets/<int:asset_id>/delete", methods=["POST"])
def delete_asset(asset_id):
    _set_actor()
    user = _active_user()
    asset = Asset.query.filter_by(id=asset_id, is_deleted=False).first_or_404()
    expected_version = _expected_version()
    if not _check_optimistic_lock(asset, expected_version, "asset"):
        return redirect(url_for("index"))

    asset.soft_delete(user)
    db.session.commit()
    flash(f"Asset #{asset.id} deleted (soft).", "success")
    return redirect(url_for("index"))


@app.route("/versions/<entity_type>/<int:entity_id>")
def versions(entity_type, entity_id):
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return "Unknown entity type", 404

    versions = (
        EntityVersion.query
        .filter_by(entity_type=model.__tablename__, entity_id=entity_id)
        .order_by(EntityVersion.version.desc())
        .all()
    )
    return render_template(
        "versions.html",
        versions=versions,
        entity_type=entity_type,
        entity_id=entity_id,
    )

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "8000"))
    app.run(host=host, port=port, debug=True)
