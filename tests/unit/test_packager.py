from __future__ import annotations

from uthere.packager import generate_debian, generate_fedora, generate_gentoo


def make_project_root(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "src" / "uthere").mkdir(parents=True)
    (project_root / "src" / "uthere" / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    (project_root / "pyproject.toml").write_text("[project]\nname='uthere'\n", encoding="utf-8")
    (project_root / "README.md").write_text("# uthere\n", encoding="utf-8")
    (project_root / "packaging").mkdir()
    (project_root / "packaging" / "uthere.service").write_text("[Service]\n", encoding="utf-8")
    return project_root


def test_generate_debian_files(tmp_path):
    project_root = make_project_root(tmp_path)
    files = generate_debian(project_root, tmp_path / "out", "0.1.0", "Tester <test@example.com>")
    names = {path.name for path in files}

    assert {"control", "changelog", "rules", "postinst", "copyright"}.issubset(names)
    assert (tmp_path / "out" / "debian" / "uthere-0.1.0" / "debian" / "control").read_text(encoding="utf-8").startswith("Source: uthere")


def test_generate_fedora_spec(tmp_path):
    project_root = make_project_root(tmp_path)
    files = generate_fedora(project_root, tmp_path / "out", "0.1.0", "Tester <test@example.com>")
    spec = tmp_path / "out" / "fedora" / "SPECS" / "uthere.spec"

    content = spec.read_text(encoding="utf-8")
    assert "Name:           uthere" in content
    assert "License:        GPL-3.0-only" in content
    assert "%systemd_post uthere.service" in content
    assert any(path.name == "uthere-0.1.0.tar.gz" for path in files)


def test_generate_gentoo_ebuild(tmp_path):
    files = generate_gentoo(tmp_path / "out", "0.1.0")

    assert any(path.name == "uthere-0.1.0.ebuild" for path in files)
    assert 'LICENSE="GPL-3"' in (tmp_path / "out" / "gentoo" / "uthere-0.1.0.ebuild").read_text(encoding="utf-8")
    assert (tmp_path / "out" / "gentoo" / "files" / "uthere.service").exists()
