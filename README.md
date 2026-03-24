# Tools2Fast FastAPI

Shared tools, mixins, and base services for FastAPI applications. Designed for internal use by the Solautyc Team to standardize model definitions and common services across multiple packages.

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
- **Shared Services**: Reusable services logic for basic CRUD and related queries (coming soon).

## Documentation

See the `docs/` folder for more detailed instructions and usage guides:

- [Usage Guide](docs/guide.md)

## Examples

Check the `examples/` folder for sample implementation.

## License

This project is licensed under the MIT License.
