
from datetime import datetime
import hashlib
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event

db = SQLAlchemy()

class VersionedMixin:
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.String(64))

class Object(db.Model, VersionedMixin):
    __tablename__ = "objects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False)

    versions = db.relationship("ObjectVersion", backref="object", lazy=True)

class ObjectVersion(db.Model):
    __tablename__ = "object_versions"

    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(db.Integer, db.ForeignKey("objects.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    hash = db.Column(db.String(64), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    changed_by = db.Column(db.String(64))

def calculate_hash(data):
    payload = json.dumps(data, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

@event.listens_for(db.session.__class__, "before_flush")
def create_version(session, flush_context, instances):
    for obj in session.dirty:
        if isinstance(obj, Object):
            last_version = (
                ObjectVersion.query
                .filter_by(object_id=obj.id)
                .order_by(ObjectVersion.version.desc())
                .first()
            )

            new_version_number = 1
            if last_version:
                new_version_number = last_version.version + 1

            snapshot = {
                "name": obj.name,
                "status": obj.status,
            }

            version = ObjectVersion(
                object_id=obj.id,
                version=new_version_number,
                snapshot=snapshot,
                hash=calculate_hash(snapshot),
                changed_by=obj.updated_by,
            )

            session.add(version)
