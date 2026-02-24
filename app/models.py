
from datetime import datetime
import hashlib
import json

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, func, inspect

db = SQLAlchemy()


class VersionedMixin:
    __versioned__ = True
    __version_exclude__ = {"updated_at"}

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_by = db.Column(db.String(64))


class Object(db.Model, VersionedMixin):
    __tablename__ = "objects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False)


class EntityVersion(db.Model):
    __tablename__ = "entity_versions"
    __table_args__ = (
        db.Index("ix_entity_versions_lookup", "entity_type", "entity_id", "version"),
    )

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(128), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    version = db.Column(db.Integer, nullable=False)
    operation = db.Column(db.String(16), nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    diff = db.Column(db.JSON, nullable=False, default=dict)
    hash = db.Column(db.String(64), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    changed_by = db.Column(db.String(64))


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_entity(entity):
    exclude = set(getattr(entity, "__version_exclude__", set()))
    data = {}
    for column in entity.__table__.columns:
        if column.name in exclude:
            continue
        data[column.name] = _json_value(getattr(entity, column.name))
    return data


def _calculate_hash(data):
    payload = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_diff(entity):
    mapper_state = inspect(entity)
    diff = {}
    exclude = set(getattr(entity, "__version_exclude__", set()))
    for column in entity.__table__.columns:
        if column.name in exclude:
            continue
        attr = mapper_state.attrs[column.name]
        history = attr.history
        if history.has_changes():
            old_value = _json_value(history.deleted[0]) if history.deleted else None
            new_value = _json_value(history.added[0]) if history.added else _json_value(getattr(entity, column.name))
            diff[column.name] = {"old": old_value, "new": new_value}
    return diff


def _is_versioned_entity(entity):
    return (
        hasattr(entity, "__table__")
        and getattr(entity, "__versioned__", False)
        and not isinstance(entity, EntityVersion)
    )


@event.listens_for(db.session.__class__, "before_flush")
def collect_version_events(session, flush_context, instances):
    events = session.info.setdefault("version_events", [])

    for entity in session.new:
        if _is_versioned_entity(entity):
            events.append((entity, "create", {}))

    for entity in session.dirty:
        if _is_versioned_entity(entity) and session.is_modified(entity, include_collections=False):
            events.append((entity, "update", _compute_diff(entity)))

    for entity in session.deleted:
        if _is_versioned_entity(entity):
            events.append((entity, "delete", {}))


@event.listens_for(db.session.__class__, "after_flush_postexec")
def create_entity_versions(session, flush_context):
    events = session.info.pop("version_events", [])
    for entity, operation, diff in events:
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            continue

        entity_type = entity.__tablename__
        current_version = (
            session.query(func.max(EntityVersion.version))
            .filter_by(entity_type=entity_type, entity_id=entity_id)
            .scalar()
        ) or 0

        snapshot = _serialize_entity(entity)
        version_row = EntityVersion(
            entity_type=entity_type,
            entity_id=entity_id,
            version=current_version + 1,
            operation=operation,
            snapshot=snapshot,
            diff=diff,
            hash=_calculate_hash(snapshot),
            changed_by=getattr(entity, "updated_by", None),
        )
        session.add(version_row)
