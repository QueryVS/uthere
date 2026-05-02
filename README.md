# uthere

<p align="center">
  <img src="assert/uthere.png" alt="uthere logo" width="180">
</p>

uthere is a Linux-focused CLI and systemd service for monitoring IP, domain,
and URL health with ping or HTTP checks. It stores monitors in SQLite, wakes the
service when records change, and can send alerts through mail, Telegram, and
WhatsApp when a monitor becomes unhealthy.

## Documentation

- [English documentation](docs/en.md)
- [Turkish documentation](docs/tr.md)
- [Contributing guide](CONTRIBUTING.md)
- [License](LICENSE): GPL-3.0-only

## Quick Start

### Debian/Ubuntu prerequisites:

```bash
# Install Python venv support, pip, pytest, and ping.
sudo apt install python3-full python3-venv python3-pip python3-pytest iputils-ping

# If `python3 -m venv .venv` still reports that ensurepip is unavailable,
# install the venv package for your exact Python version. Example for Python 3.13:
sudo apt install python3.13-venv
```

### Project setup for Debian/Ubuntu systems that enforce PEP 668:

```bash
# Install uthere and its test extras.
python3 -m pip install -e '.[test]' --break-system-packages

# Use the CLI.
uthere add example.com --type ping --interval 60 --timeout 3 --name dns
uthere add https://example.com --type http --interval 120 --timeout 5
uthere des add 1 "this description server"
uthere des show 1
uthere list
uthere check
uthere check all
uthere check 1 2 3
```

New records are checked immediately after `uthere add`, so `uthere list` should
show `healthy` or `unhealthy` instead of `unknown` unless the database cannot be
updated.

### Alternative isolated virtual environment setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'

uthere add example.com --type ping --interval 60 --timeout 3 --name dns
uthere add https://example.com --type http --interval 120 --timeout 5
uthere des add 1 "this description server"
uthere des show 1
uthere list
uthere check
uthere check all
uthere check 1 2 3
```

`--break-system-packages` bypasses Debian/Ubuntu's
`externally-managed-environment` protection. Use it only when you intentionally
want to install into the system Python environment.

Install as a Linux systemd service:

```bash
sudo scripts/install-systemd.sh
systemctl status uthere
journalctl -u uthere -f
```

Systemd installation is system mode:

- The service runs as `root` by default.
- The database is `/var/lib/uthere/uthere.db` by default.
- Configuration is read from `/etc/default/uthere`.
- Use `sudo uthere ...` when reading or writing the service database.

Examples:

```bash
sudo uthere add example.com --type ping --interval 60
sudo uthere list
sudo uthere check all
```

To run the service as another user, pass `UTHERE_SERVICE_USER` during install:

```bash
sudo UTHERE_SERVICE_USER=anc scripts/install-systemd.sh
```

User-mode installation:

```bash
scripts/install-systemd.sh
```

When the installer is run without root privileges, it installs only the CLI:

- Binary: `~/.local/bin/uthere`
- Config: `~/.config/uthere/uthere.env`
- Database: `~/.local/state/uthere/uthere.db`

User mode is not a background service. It only runs when you call commands like
`uthere add`, `uthere check`, or `uthere list`. For continuous interval checks,
install system mode with `sudo scripts/install-systemd.sh`.

If records stay `unknown`, they have not been checked yet. Check these first:

```bash
# Run one check manually.
uthere check

# Confirm the CLI and service use the same database.
uthere --help
cat /etc/default/uthere

# If the service database is /var/lib/uthere/uthere.db, use the same DB manually:
sudo uthere --db /var/lib/uthere/uthere.db list
sudo uthere --db /var/lib/uthere/uthere.db check
```

The CLI reads `UTHERE_DB` from the environment and, if available, from
`/etc/default/uthere`, `/etc/sysconfig/uthere`, or `/etc/conf.d/uthere`.
If `uthere check` reports that SQLite is read-only, fix the database ownership
or use the same database path as the service.

Run tests:

```bash
PYTHONPATH=src pytest -q
```

Generate packaging files:

```bash
PYTHONPATH=src python3 -m uthere.packager all
```

Make shortcuts:

```bash
make install
make install-root
make install-user
make run
make clean
make reset
```

`make install` only shows the install mode choices. Use `make install-root` for
the root/systemd service mode, or `make install-user` for a user-home CLI
install that only runs when called.

`make reset` removes the default local development database at
`~/.local/state/uthere/uthere.db` and `/tmp/uthere.sock`. Override paths when
needed:

```bash
make run DB=/var/lib/uthere/uthere.db SOCKET=/tmp/uthere.sock
make reset DB=/path/to/uthere.db SOCKET=/path/to/uthere.sock
```

Docker:

```bash
docker build -t uthere:latest .
docker volume create uthere-data
docker run -d --name uthere --restart unless-stopped -v uthere-data:/var/lib/uthere uthere:latest
```

The Docker container runs `uthere serve` as the foreground executable, so it
performs continuous checks while the container is running.
Unhealthy or invalid records should not stop the container; they are recorded as
`unhealthy` with the error message in the database.

Use `docker exec`, not a second `docker run`, when adding/listing records in the
running container:

```bash
docker exec uthere uthere add example.com --type ping --interval 60
docker exec uthere uthere list
docker exec uthere uthere check all
docker logs -f uthere
```

To open a shell in the same running container:

```bash
docker exec -it uthere sh
```

Records are stored in the `uthere-data` named volume. If you start another
container without mounting the same volume, it will use a new empty database.

Docker Compose:

```bash
docker compose up -d
docker compose exec uthere uthere add example.com --type ping --interval 60
docker compose exec uthere uthere list
docker compose logs -f uthere
```

Release images are published to GitHub Container Registry when a `v*` tag is
pushed:

```text
ghcr.io/<owner>/<repo>:v0.1.0
ghcr.io/<owner>/<repo>:0.1.0
ghcr.io/<owner>/<repo>:latest
```
