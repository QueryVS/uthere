from __future__ import annotations

import os
from pathlib import Path


ENV_FILES = (
    Path("/etc/default/uthere"),
    Path("/etc/sysconfig/uthere"),
    Path("/etc/conf.d/uthere"),
)


def get_setting(name: str, default: str, env_files: tuple[Path, ...] = ENV_FILES) -> str:
    value = os.environ.get(name)
    if value:
        return value

    for env_file in env_files:
        value = read_env_file_value(env_file, name)
        if value:
            return value

    return default


def read_env_file_value(path: Path, name: str) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    prefix = f"{name}="
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip()
        return value.strip('"').strip("'")
    return None
