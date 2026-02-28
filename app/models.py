
from datetime import datetime
import hashlib
import json

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, func, inspect

db = SQLAlchemy()

asset_signals = db.Table(
    "asset_signals",
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id"), primary_key=True),
    db.Column("signal_id", db.Integer, db.ForeignKey("signals.id"), primary_key=True),
)


class VersionedMixin:
    __versioned__ = True
    __version_exclude__ = {"created_at", "updated_at", "created_by", "updated_by", "lock_version"}

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.String(64), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_by = db.Column(db.String(64), nullable=False)
    lock_version = db.Column(db.Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": lock_version}


class SoftDeleteMixin:
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.String(64), nullable=True)

    def soft_delete(self, user):
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = user

    @property
    def trash_name(self):
        return getattr(self, "name", None)


class Signal(db.Model, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "signals"

    frequency_from = db.Column(db.Float, nullable=False)
    frequency_to = db.Column(db.Float, nullable=False)
    modulation = db.Column(db.String(50), nullable=False)
    power = db.Column(db.Float, nullable=False)

    assets = db.relationship(
        "Asset",
        secondary=asset_signals,
        back_populates="signals",
        lazy="select",
    )

    @property
    def trash_name(self):
        if self.frequency_from == self.frequency_to:
            return f"f={self.frequency_from}, {self.modulation}"
        return f"f={self.frequency_from}-{self.frequency_to}, {self.modulation}"


class Asset(db.Model, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "assets"

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)

    signals = db.relationship(
        "Signal",
        secondary=asset_signals,
        back_populates="assets",
        lazy="select",
    )

    def __version_snapshot__(self):
        data = _serialize_columns(self)
        data["signal_ids"] = sorted(signal.id for signal in self.signals)
        return data


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


def _serialize_columns(entity):
    exclude = set(getattr(entity, "__version_exclude__", set()))
    data = {}
    for column in entity.__table__.columns:
        if column.name in exclude:
            continue
        data[column.name] = _json_value(getattr(entity, column.name))
    return data


def _serialize_entity(entity):
    custom_serializer = getattr(entity, "__version_snapshot__", None)
    if callable(custom_serializer):
        return custom_serializer()
    return _serialize_columns(entity)


def _calculate_hash(data):
    payload = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _diff_snapshots(old_snapshot, new_snapshot):
    diff = {}
    keys = set(old_snapshot.keys()) | set(new_snapshot.keys())
    for key in keys:
        old_value = old_snapshot.get(key)
        new_value = new_snapshot.get(key)
        if old_value != new_value:
            diff[key] = {"old": old_value, "new": new_value}
    return diff


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


def _get_last_snapshot(session, entity_type, entity_id):
    previous_version = (
        session.query(EntityVersion)
        .filter_by(entity_type=entity_type, entity_id=entity_id)
        .order_by(EntityVersion.version.desc())
        .first()
    )
    if previous_version:
        return previous_version.snapshot or {}
    return None


def _is_versioned_entity(entity):
    return (
        hasattr(entity, "__table__")
        and getattr(entity, "__versioned__", False)
        and not isinstance(entity, EntityVersion)
    )


class OptimisticLockError(Exception):
    """Raised when entity lock_version does not match the version sent by the client."""


@event.listens_for(db.session.__class__, "before_flush")
def collect_version_events(session, flush_context, instances):
    events = session.info.setdefault("version_events", [])
    actor = session.info.get("actor")

    for entity in session.new:
        if _is_versioned_entity(entity):
            if actor:
                if not getattr(entity, "created_by", None):
                    entity.created_by = actor
                if not getattr(entity, "updated_by", None):
                    entity.updated_by = actor
            events.append((entity, "create", {}))

    for entity in session.dirty:
        if _is_versioned_entity(entity) and session.is_modified(entity, include_collections=True):
            if getattr(entity, "id", None) is None:
                continue

            current_snapshot = _serialize_entity(entity)
            previous_snapshot = _get_last_snapshot(session, entity.__tablename__, entity.id)

            if previous_snapshot is not None:
                snapshot_diff = _diff_snapshots(previous_snapshot, current_snapshot)
                if not snapshot_diff:
                    continue
                entity.updated_at = datetime.utcnow()
                if actor:
                    entity.updated_by = actor
                events.append((entity, "update", snapshot_diff))
            else:
                column_diff = _compute_diff(entity)
                if not column_diff:
                    continue
                entity.updated_at = datetime.utcnow()
                if actor:
                    entity.updated_by = actor
                events.append((entity, "update", column_diff))

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
