
from flask import Flask, render_template, request, redirect, url_for
from config import Config
from models import db, Object, ObjectVersion
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

@app.before_request
def create_tables():
    db.create_all()

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
        ObjectVersion.query
        .filter_by(object_id=object_id)
        .order_by(ObjectVersion.version.desc())
        .all()
    )
    return render_template("versions.html", versions=versions, object_id=object_id)

if __name__ == "__main__":
    app.run(debug=True)
