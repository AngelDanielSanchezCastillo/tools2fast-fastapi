# Tools2Fast FastAPI

Shared tools, mixins, and base services for FastAPI applications. Designed for internal use by the Solautyc Team to standardize model definitions and common services across multiple packages.

> 📖 **Conventions reference**: this package follows the [2fast-handbook](https://github.com/AngelDanielSanchezCastillo/2fast-handbook) for ecosystem conventions (structure, versioning, README, commits, release).

## Installation

You can install this package from PyPI (if published) or use it locally within your workspace:

```bash
pip install tools2fast-fastapi
```

Locally with UV:
```bash
uv pip install -e path/to/tools2fast-fastapi
```

## Features

- **SQLModel Mixins**: Standardized `IdMixin`, `TimestampMixin`, and `AuditMixin`.
- **Base Models**: Core models setup to be inherited across all entity definitions.
- **Unified API envelope**: Success and error helpers via `APIResponse`.
- **Auth error helper**: `APIResponse.auth_error(...)` returns a ready-to-return
  `JSONResponse` with the project envelope and, for HTTP 401, the RFC 6750
  `WWW-Authenticate` header.
- **Shared Services**: Reusable services logic for basic CRUD and related queries (coming soon).

## Auth error contract

`APIResponse.auth_error` produces a stable contract for authentication and
authorization failures. The discriminator is `error.type` (never the message),
which lets clients react without string matching:

```python
from tools2fast_fastapi import APIResponse

return APIResponse.auth_error(
    error_code="TokenExpired",
    message="Token expirado",
    status_code=401,
    www_authenticate='Bearer error="expired_token"',
)
```

When the failure happens inside a **FastAPI dependency**, return a `Response`
is not enough (FastAPI injects it as the dependency value instead of
short-circuiting). Raise `AuthError` and register the handler once at startup:

```python
from fastapi import FastAPI
from tools2fast_fastapi import AuthError, install_auth_error_handler

app = FastAPI()
install_auth_error_handler(app)

async def get_current_user(...):
    raise AuthError(
        error_code="TokenExpired",
        message="Token expirado",
        www_authenticate='Bearer error="expired_token"',
    )
```

Both paths produce the same envelope and the same RFC 6750 header.

| Situation | Status | `error.type` | `WWW-Authenticate` |
|---|---|---|---|
| Missing token | 401 | `TokenMissing` | `Bearer` |
| Malformed / bad signature | 401 | `TokenInvalid` | `Bearer error="invalid_token"` |
| Expired token | 401 | `TokenExpired` | `Bearer error="expired_token"` |
| Email not verified | 403 | `EmailNotVerified` | — |
| Missing permission | 403 | `PermissionDenied` | — |
| Missing role | 403 | `RoleMissing` | — |
| Valid token, no tenant | 403 | `TenantRequired` | — |
| Inactive tenant | 403 | `TenantInactive` | — |

When `status_code` is `401` and `www_authenticate` is omitted, the header
defaults to `Bearer`. For any other status the header is omitted unless passed
explicitly.

## Documentation

See the `docs/` folder for more detailed instructions and usage guides:

- [Usage Guide](docs/guide.md)

## Examples

Check the `examples/` folder for sample implementation.

## License

This project is licensed under the MIT License.
