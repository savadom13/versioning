
from datetime import datetime
import os
from pathlib import Path
import sys

from flask import Flask, render_template, request, redirect, url_for
from flask_migrate import Migrate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from models import db, Object, EntityVersion

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)

@app.route("/")
def index():
    objects = Object.query.all()
    return render_template("index.html", objects=objects)

@app.route("/create", methods=["POST"])
def create_object():
    name = request.form["name"]
    status = request.form["status"]
    user = request.form.get("user", "system")

    obj = Object(name=name, status=status, updated_by=user)
    db.session.add(obj)
    db.session.commit()

    return redirect(url_for("index"))

@app.route("/edit/<int:object_id>", methods=["POST"])
def edit_object(object_id):
    obj = Object.query.get_or_404(object_id)
    obj.name = request.form["name"]
    obj.status = request.form["status"]
    obj.updated_by = request.form.get("user", "system")
    obj.updated_at = datetime.utcnow()

    db.session.commit()

    return redirect(url_for("index"))

@app.route("/versions/<int:object_id>")
def versions(object_id):
    versions = (
        EntityVersion.query
        .filter_by(entity_type=Object.__tablename__, entity_id=object_id)
        .order_by(EntityVersion.version.desc())
        .all()
    )
    return render_template("versions.html", versions=versions, object_id=object_id)

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "8000"))
    app.run(host=host, port=port, debug=True)
