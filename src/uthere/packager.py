from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from pathlib import Path


PROJECT_NAME = "uthere"
SUMMARY = "Small CLI and service for ping/http health checks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uthere-packager", description="Generate Linux packaging files for uthere.")
    parser.add_argument("--project-root", default=".", help="Project root path")
    parser.add_argument("--output-dir", default="dist/packages", help="Generated packaging output directory")
    parser.add_argument("--version", default=read_version(Path(".")), help="Package version")
    parser.add_argument("--maintainer", default="uthere maintainers <root@localhost>", help="Package maintainer")
    parser.add_argument("--build", action="store_true", help="Call native package build tool if available")
    parser.add_argument("targets", nargs="*", choices=("debian", "fedora", "gentoo", "all"), default=["all"])
    return parser


def read_version(project_root: Path) -> str:
    init_file = project_root / "src" / "uthere" / "__init__.py"
    try:
        for line in init_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return "0.1.0"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    targets = {"debian", "fedora", "gentoo"} if "all" in args.targets else set(args.targets)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    if "debian" in targets:
        generated.extend(generate_debian(project_root, output_dir, args.version, args.maintainer))
        if args.build:
            run_optional(["dpkg-buildpackage", "-us", "-uc"], output_dir / "debian" / f"{PROJECT_NAME}-{args.version}")
    if "fedora" in targets:
        generated.extend(generate_fedora(project_root, output_dir, args.version, args.maintainer))
        if args.build:
            run_optional(["rpmbuild", "--define", f"_topdir {output_dir / 'fedora'}", "-ba", str(output_dir / "fedora" / "SPECS" / f"{PROJECT_NAME}.spec")], project_root)
    if "gentoo" in targets:
        generated.extend(generate_gentoo(output_dir, args.version))
        if args.build:
            run_optional(["ebuild", str(output_dir / "gentoo" / f"{PROJECT_NAME}-{args.version}.ebuild"), "manifest"], project_root)

    for path in generated:
        print(path)
    return 0


def generate_debian(project_root: Path, output_dir: Path, version: str, maintainer: str) -> list[Path]:
    package_root = output_dir / "debian" / f"{PROJECT_NAME}-{version}"
    copy_source_tree(project_root, package_root)
    debian_dir = package_root / "debian"
    debian_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "control": f"""Source: {PROJECT_NAME}
Section: utils
Priority: optional
Maintainer: {maintainer}
Build-Depends: debhelper-compat (= 13), dh-python, pybuild-plugin-pyproject, python3-all, python3-setuptools
Standards-Version: 4.6.2
Rules-Requires-Root: no

Package: {PROJECT_NAME}
Architecture: all
Depends: ${{misc:Depends}}, ${{python3:Depends}}, iputils-ping
Description: {SUMMARY}
 uthere stores ping/http health checks in SQLite and runs them from a
 systemd-friendly CLI service.
""",
        "changelog": f"""{PROJECT_NAME} ({version}-1) unstable; urgency=medium

  * Initial package.

 -- {maintainer}  Sat, 02 May 2026 00:00:00 +0000
""",
        "rules": """#!/usr/bin/make -f

%:
\tdh $@ --buildsystem=pybuild
""",
        "uthere.service": service_file(),
        "uthere.default": default_env_file(),
        "install": "debian/uthere.service lib/systemd/system/uthere.service\n",
        "dirs": "var/lib/uthere\n",
        "copyright": f"""Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: {PROJECT_NAME}
Source: https://example.invalid/uthere

Files: *
Copyright: 2026 uthere contributors
License: GPL-3.0-only

License: GPL-3.0-only
 This package is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, version 3.
 .
 This package is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in /usr/share/common-licenses/GPL-3.
""",
        "postinst": """#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
fi
#DEBHELPER#
""",
    }
    written = write_files(debian_dir, files)
    (debian_dir / "rules").chmod(0o755)
    (debian_dir / "postinst").chmod(0o755)
    return written


def generate_fedora(project_root: Path, output_dir: Path, version: str, maintainer: str) -> list[Path]:
    fedora_dir = output_dir / "fedora"
    specs_dir = fedora_dir / "SPECS"
    sources_dir = fedora_dir / "SOURCES"
    specs_dir.mkdir(parents=True, exist_ok=True)
    sources_dir.mkdir(parents=True, exist_ok=True)
    archive = sources_dir / f"{PROJECT_NAME}-{version}.tar.gz"
    make_source_archive(project_root, archive, version)
    spec = specs_dir / f"{PROJECT_NAME}.spec"
    spec.write_text(
        f"""Name:           {PROJECT_NAME}
Version:        {version}
Release:        1%{{?dist}}
Summary:        {SUMMARY}

License:        GPL-3.0-only
URL:            https://example.invalid/uthere
Source0:        %{{name}}-%{{version}}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  pyproject-rpm-macros
Requires:       python3
Requires:       iputils

%description
uthere stores ping/http health checks in SQLite and runs them from a
systemd-friendly CLI service.

%prep
%autosetup

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files uthere
install -D -m 0644 packaging/uthere.service %{{buildroot}}%{{_unitdir}}/uthere.service
install -D -m 0644 /dev/null %{{buildroot}}%{{_sysconfdir}}/sysconfig/uthere
install -d -m 0755 %{{buildroot}}%{{_sharedstatedir}}/uthere

%post
%systemd_post uthere.service

%preun
%systemd_preun uthere.service

%postun
%systemd_postun_with_restart uthere.service

%files -f %{{pyproject_files}}
%license LICENSE
%{{_bindir}}/uthere
%{{_unitdir}}/uthere.service
%config(noreplace) %{{_sysconfdir}}/sysconfig/uthere
%dir %{{_sharedstatedir}}/uthere

%changelog
* Sat May 02 2026 {maintainer} - {version}-1
- Initial package
""",
        encoding="utf-8",
    )
    return [spec, archive]


def generate_gentoo(output_dir: Path, version: str) -> list[Path]:
    gentoo_dir = output_dir / "gentoo"
    files_dir = gentoo_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    ebuild = gentoo_dir / f"{PROJECT_NAME}-{version}.ebuild"
    service = files_dir / "uthere.service"
    env = files_dir / "uthere.confd"
    ebuild.write_text(
        f"""EAPI=8

PYTHON_COMPAT=( python3_10 python3_11 python3_12 python3_13 )
DISTUTILS_USE_PEP517=setuptools
inherit distutils-r1 systemd

DESCRIPTION="{SUMMARY}"
HOMEPAGE="https://example.invalid/uthere"
SRC_URI=""
LICENSE="GPL-3"
SLOT="0"
KEYWORDS="~amd64"
RDEPEND="net-misc/iputils"

src_install() {{
    distutils-r1_src_install
    systemd_dounit "${{FILESDIR}}/uthere.service"
    insinto /etc/conf.d
    newins "${{FILESDIR}}/uthere.confd" uthere
    keepdir /var/lib/uthere
}}
""",
        encoding="utf-8",
    )
    service.write_text(service_file(), encoding="utf-8")
    env.write_text(default_env_file(), encoding="utf-8")
    return [ebuild, service, env]


def service_file() -> str:
    return """[Unit]
Description=uthere health check service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-/etc/default/uthere
EnvironmentFile=-/etc/sysconfig/uthere
EnvironmentFile=-/etc/conf.d/uthere
ExecStart=/usr/bin/uthere serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def default_env_file() -> str:
    return """UTHERE_DB=/var/lib/uthere/uthere.db
UTHERE_SOCKET=/tmp/uthere.sock
# UTHERE_ALERT_CHANNELS=
# UTHERE_ALERT_MODE=on_change
"""


def write_files(directory: Path, files: dict[str, str]) -> list[Path]:
    written: list[Path] = []
    for relative_path, content in files.items():
        path = directory / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def copy_source_tree(project_root: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    ignore = shutil.ignore_patterns(".git", ".agents", ".codex", ".venv", "__pycache__", "*.pyc", "dist", ".pytest_cache")
    shutil.copytree(project_root, destination, ignore=ignore)


def make_source_archive(project_root: Path, archive: Path, version: str) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        for path in project_root.rglob("*"):
            if should_skip(path, project_root):
                continue
            tar.add(path, arcname=Path(f"{PROJECT_NAME}-{version}") / path.relative_to(project_root))


def should_skip(path: Path, project_root: Path) -> bool:
    parts = path.relative_to(project_root).parts
    ignored = {".git", ".agents", ".codex", ".venv", "__pycache__", "dist", ".pytest_cache"}
    return any(part in ignored for part in parts) or path.suffix == ".pyc"


def run_optional(cmd: list[str], cwd: Path) -> None:
    if shutil.which(cmd[0]) is None:
        raise SystemExit(f"{cmd[0]} was not found; packaging files were generated but the build could not run")
    subprocess.run(cmd, cwd=cwd, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
