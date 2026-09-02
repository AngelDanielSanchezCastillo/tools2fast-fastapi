---
name: tools2fast-fastapi
description: "Trigger: working on or with tools2fast-fastapi. Shared base layer of the 2fast stack: model/schema mixins, APIResponse envelope, SafeRouter, revision and number services. Prevails over the 2fast-handbook base skill for this package."
license: MIT
metadata:
  author: AngelDanielSanchezCastillo
  version: "1.0"
---

## Purpose

Shared foundation consumed by nearly every 2fast package (oauth2fast,
permissions2fast, tenants2fast, cashing2fast, Metal-ERP): model mixins,
schema mixins, the response envelope (`APIResponse`), `SafeRouter`, audit
automation, and revision/document services. No settings module by design.

## Import quirk — TWO mixin namespaces, same names

- Top-level `from tools2fast_fastapi import IdMixin, TimestampMixin, ...` exports the **MODEL** versions (`models/mixins.py`): DB columns — nullable BigInteger PK `id`, tz-aware `created_at`/`updated_at` with `onupdate`, `revision` defaults to 1, `NumberUniqueMixin` has NO `tenant_id`.
- `tools2fast_fastapi.schemas.*` are the validation-only versions: REQUIRED `id`, REQUIRED `revision`, `NumberUniqueMixin` REQUIRES `tenant_id`. A schema built on `NumberUniqueMixin` cannot round-trip the model.
- Never mix the two families in one class; downstream imports top-level (model) mixins — that re-export is a hard cross-package contract.

## Envelope — `APIResponse`

- Success factories `ok/saved/created/deleted` return **bare Pydantic models** (HTTP 200 implied; a 201 must come from the route decorator).
- Error factories `fail(message, status_code=400)` / `payment_required` / `from_exception` return **`(model, http_status)` tuples** the caller must wrap in a `JSONResponse`.
- `error_type` Literal allows ONLY `controlled` / `unexpected` / `payment_required`. Unexpected errors **hide `error.detail`** (security) with fixed Spanish message "Ha ocurrido un error".
- `ERROR_RESPONSES` maps {400/402/404/500} → response classes (reuse for OpenAPI docs).
- `from_exception` treats `ValueError` subclasses as controlled 400; anything else → 500. Legacy `schemas.BaseResponse/DataResponse/ErrorResponse` still exported until all routers migrate.

## SafeRouter / handle_exceptions (traps)

- Endpoints under `SafeRouter`/`handle_exceptions` MUST be `async def` — the wrapper awaits unconditionally, sync endpoints crash with TypeError.
- **`HTTPException` is NOT a controlled error** → it becomes a 500 with hidden detail (loses the intended 404). Only `ValueError` subclasses survive as 400s. Prefer `TransactionService` + explicit `APIResponse.fail`/`from_exception`; never rely on SafeRouter to emit 404s.

## AuditTimestampMixin

- Only auto-audits **when tenants2fast is installed** (lazy import of `get_user_context` inside SQLAlchemy events; silently skipped otherwise). `created_by` filled only if absent; `updated_by` always set; `updated_at` force-set on every flush (even no-op updates).
- Revision clones copy `created_by`/`updated_by` verbatim (`_EXCLUDED_ON_CLONE = {"id", "created_at", "updated_at"}`) — new revisions carry stale audit attribution.

## Revision / number services

- `RevisionMixin` invariant: the consumer table MUST declare `UniqueConstraint("number", "revision", ...)` — **services never enforce it**; "current revision = max revision" depends on that constraint.
- Item/document services key items by the numeric `number` column (AttributeError otherwise); deleted items are implicit (absent from the payload → not cloned); `create_document_with_items` **mutates the caller's dict** (injects the header FK).
- `get_next_number(session, model_class)` = `max(number) + 1` over the WHOLE table — not tenant-filtered, **not atomic** (race-prone under concurrency), safe only in per-tenant DBs, and untested.

## Conventions

- Spanish response messages ("Éxito", "Guardado con éxito", "Ha ocurrido un error", "Pago requerido").
- All `error_type` values are Literals — only the three above exist.

## Stale docs

- README claims services are "(coming soon)" — 5 service modules exist; its `docs/guide.md` and `examples/` only cover the 3 basic mixins. Docstrings reference a nonexistent `tenant.*` module (copied from the original project).
- `pyproject.toml` pins deps with `>=` ranges and leaves `pydantic`/`sqlalchemy`/`tenant2fast` undeclared (tenant2fast is imported lazily at runtime).

## Golden rule (inherited)

Follow the 2fast-handbook base skill for layout/versioning/naming/README/commits/release.
Local edits are fine; NEVER bump/publish on your own — prepare the exact command and hand it to the developer.