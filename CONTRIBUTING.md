# Contributing

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

If your distribution disables `ensurepip`, install the matching Python venv
package first, for example `python3-venv` or `python3.13-venv`.
Do not use `pip install` directly against the system Python on Debian/Ubuntu
systems that enforce PEP 668.

## Running Tests

```bash
PYTHONPATH=src pytest -q
```

Run this before opening a pull request. The suite contains unit tests and
integration tests. Some socket behavior may be skipped in restricted sandbox
environments.

## Code Style

- Keep changes small and focused.
- Prefer the existing standard-library-only approach unless a dependency is
  clearly justified.
- Keep CLI behavior stable and document new options.
- Add or update tests when changing scheduling, persistence, alerts, packaging,
  or CLI behavior.
- Do not commit generated caches such as `__pycache__`, `.pytest_cache`, or
  local SQLite databases.

## Packaging Changes

When changing package metadata, run:

```bash
PYTHONPATH=src python3 -m uthere.packager all
PYTHONPATH=src pytest -q
```

## Release Changes

Releases are tag-driven. The tag `vX.Y.Z` must match `uthere.__version__` value
`X.Y.Z`.
