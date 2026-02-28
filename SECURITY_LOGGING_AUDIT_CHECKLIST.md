# Чеклист: безопасность, логирование, аудит

Документ для переноса практик из versioning-sample в другой проект.

---

## 1. Безопасность

### 1.1 Реализовать

| Фича | Описание |
|------|----------|
| **JWT для API** | Все эндпоинты кроме логина и OpenAPI требуют `verify_jwt_in_request()`. Исключения: `/auth/login`, `/openapi`, `/apidoc`. |
| **Секреты из env** | `SECRET_KEY`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRES` (сек), `JWT_ALGORITHM` (HS256). Дефолты только для dev. |
| **Валидация логина** | Pydantic-схема для username/password (min_length=1). При ошибке — 401 без уточнения «логин или пароль». |
| **Оптимистическая блокировка** | Поле `lock_version` у сущностей. При edit/delete проверять версию из запроса; при расхождении — 409 Conflict. |
| **Валидация тел запросов** | Pydantic для всех create/update. Ошибки валидации — 422 с единым форматом ErrorResponse. |
| **Хеш снапшота** | SHA-256 от JSON-снапшота версии для целостности (хранить в таблице аудита). |

### 1.2 Усилить в продакшене

- Заменить демо-логин на реальную аутентификацию (OAuth2, LDAP, и т.д.).
- Хранить пароли только в виде хеша (bcrypt/argon2).
- Добавить RBAC (роли и проверки на эндпоинтах).
- Rate limiting на логин и общий API.
- CORS и CSP по необходимости.

---

## 2. Логирование

### 2.1 Сейчас в sample

- Логи только в миграциях (Alembic), через `logging.config.fileConfig(alembic.ini)`.

### 2.2 Что добавить в приложение

- Логгер приложения (не только alembic).
- Логирование: входящий запрос (method, path, user), ответ (status), исключения.
- Опционально: request id, структурированный лог (JSON).
- Отдельный логгер/канал для событий безопасности (логин успех/неудача, смена пароля).

---

## 3. Аудит

### 3.1 Таблица истории версий (EntityVersion)

Колонки:

- `id` (PK)
- `entity_type` (str, например `signals`, `assets`)
- `entity_id` (int)
- `version` (int, монотонно растёт по entity)
- `operation`: `create` | `update` | `delete`
- `snapshot` (JSON) — полное состояние сущности на момент операции
- `diff` (JSON) — для update: `{ "field": { "old": ..., "new": ... } }`
- `hash` (str) — SHA-256 от snapshot
- `changed_at` (datetime UTC)
- `changed_by` (str, идентификатор пользователя из JWT)

Индекс: `(entity_type, entity_id, version)`.

### 3.2 Привязка к пользователю

- В `before_request` или при начале обработки: из JWT взять identity, положить в `db.session.info["actor"]` (или аналог).
- При создании/обновлении сущностей проставлять `created_by` / `updated_by` из этого actor.
- При записи версии в таблицу аудита заполнять `changed_by` из того же actor.

### 3.3 Мягкое удаление (опционально)

- Поля: `is_deleted`, `deleted_at`, `deleted_by`.
- При «удалении» выставлять флаг и писать в EntityVersion операцию `delete`.

### 3.4 Механика версионирования

- Миксин/база для сущностей: `__versioned__ = True`, список полей `__version_exclude__` (created_at, updated_at, created_by, updated_by, lock_version).
- События SQLAlchemy: `before_flush` — собрать события create/update/delete по изменённым сущностям; `after_flush_postexec` — записать строки в EntityVersion (snapshot, diff, hash, changed_by).
- Для update: diff либо через history атрибутов, либо сравнением предыдущего snapshot с текущим.

### 3.5 API аудита

- `GET /api/versions/<entity_type>/<entity_id>` — список версий сущности (по убыванию version), ответ: id, entity_type, entity_id, version, operation, snapshot, diff, hash, changed_at, changed_by.

---

## 4. Зависимости (Python)

- Flask, Flask-JWT-Extended, Flask-SQLAlchemy
- Pydantic (или Flask-Pydantic-Spec для OpenAPI)
- PyMySQL (если БД MySQL)

---

## 5. Порядок внедрения в новом проекте

1. Конфиг: секреты, JWT (secret, expires, algorithm).
2. Аутентификация: логин (с реальным хранилищем и хешем паролей в проде), выдача JWT, `before_request` с проверкой JWT и исключениями для login/openapi.
3. Валидация: Pydantic-схемы для всех входных тел, единый ErrorResponse и 422.
4. Модели: VersionedMixin (created_by, updated_by, lock_version), при необходимости SoftDeleteMixin.
5. Таблица EntityVersion и логика before_flush/after_flush_postexec для записи версий.
6. Установка actor из JWT в session.info и проставление created_by/updated_by/changed_by.
7. Оптимистическая блокировка на edit/delete (expected lock_version, 409 при конфликте).
8. Эндпоинт GET /versions/<entity_type>/<entity_id>.
9. Логирование приложения и при необходимости — отдельный аудит-лог безопасности.
