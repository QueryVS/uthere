# uthere Documentation

## Project Overview

uthere is a small monitoring tool for Linux systems. It provides a CLI command
and a long-running systemd-friendly service. You can register IP addresses,
domains, or URLs and choose whether each record is checked with `ping` or an
HTTP request.

The service stores monitor records in SQLite and records the latest status,
latency, HTTP status code, error message, and check timestamp. When a monitor
becomes unhealthy, uthere can send alerts through mail, Telegram, WhatsApp, or
any combination of those channels.

## Main Features

- Add, list, edit, remove, and manually check monitor records from the CLI.
- Run scheduled checks from a Linux service.
- Use ping checks for IP/domain reachability.
- Use HTTP checks and treat `2xx` responses as healthy.
- Store all state in SQLite.
- Show the last check time and last health status in `uthere list`.
- Wake the service immediately when CLI records change.
- Send unhealthy alerts through mail, Telegram, and WhatsApp.
- Generate Debian, Fedora, and Gentoo packaging files.
- Publish release assets through the tag-based GitHub Actions workflow.

## Components

### CLI

The CLI entrypoint is `uthere`, implemented in `src/uthere/cli.py`.

Important commands:

- `uthere add`: add a monitor record.
- `uthere list`: show records and their last status.
- `uthere edit`: update target, type, interval, timeout, or enabled state.
- `uthere remove`: delete one or more monitors.
- `uthere description` / `uthere des`: add, show, or clear descriptions.
- `uthere check`: run checks immediately.
- `uthere serve`: run the service scheduler.
- `uthere alert-test`: send a test alert to configured channels.

### Service Scheduler

The service is started with `uthere serve`. It does not poll constantly. It
calculates the next due check time and sleeps until then. When the CLI changes a
record, it sends a wake message through a Unix domain socket so the service can
recalculate the schedule immediately.

### Database

SQLite is used for monitor storage. The default user-level database path is:

```text
~/.local/state/uthere/uthere.db
```

The systemd installer uses:

```text
/var/lib/uthere/uthere.db
```

You can override the path with `--db` or `UTHERE_DB`.

### Wake Socket

The CLI wakes the service through a Unix domain socket. The default path is:

```text
/tmp/uthere.sock
```

You can override it with `--socket` or `UTHERE_SOCKET`.

### Checks

Ping checks call the system `ping` command. HTTP checks use Python's standard
library and consider `2xx` responses healthy.

### Alerts

Alerts are configured through environment variables. Supported channels:

- `mail`
- `telegram`
- `whatsapp`

The default alert mode is `on_change`, which sends an alert only when a monitor
moves from `healthy` or `unknown` to `unhealthy`. Use `UTHERE_ALERT_MODE=always`
to send an alert on every failed check.

### Packaging

The `uthere-packager` command generates packaging files for:

- Debian
- Fedora
- Gentoo

### Release CI

The GitHub Actions release workflow runs only on tag pushes matching `v*`. It
runs tests, verifies the tag version against `uthere.__version__`, generates
packaging files, creates release archives, uploads them to a GitHub Release,
and publishes a Docker image to GitHub Container Registry.

## Installation

### Development Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

On Debian/Ubuntu, if you see `externally-managed-environment`, you are running
`pip install` against the system Python. Use a virtual environment instead:

```bash
sudo apt install python3-venv python3-full
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

You may need the version-specific venv package:

```bash
sudo apt install python3.13-venv
```

Avoid `--break-system-packages`; it can damage system-managed Python packages.

### Systemd Installation

```bash
sudo scripts/install-systemd.sh
```

The installer:

- Creates `.venv` in the project directory.
- Installs the package into that virtual environment.
- Writes `/usr/local/bin/uthere`.
- Writes `/etc/default/uthere`.
- Writes `/etc/systemd/system/uthere.service`.
- Enables and starts the service.

Systemd installation is system mode. The service runs as `root` by default,
uses `/var/lib/uthere/uthere.db`, and reads configuration from
`/etc/default/uthere`. Use `sudo uthere ...` for CLI commands that read or write
the service database:

```bash
sudo uthere add example.com --type ping --interval 60
sudo uthere list
sudo uthere check all
```

To run the service as another user:

```bash
sudo UTHERE_SERVICE_USER=anc scripts/install-systemd.sh
```

### User-Mode Installation

```bash
scripts/install-systemd.sh
```

When the installer is run without root privileges, it installs only the CLI into
the current user's home directory:

- Binary: `~/.local/bin/uthere`
- Config: `~/.config/uthere/uthere.env`
- Database: `~/.local/state/uthere/uthere.db`

User mode is not a background service. It only runs when a user calls a command.
Use system mode for continuous interval checks.

Check service status:

```bash
systemctl status uthere
journalctl -u uthere -f
```

## Usage

### Add Records

```bash
uthere add example.com --type ping --interval 60 --timeout 3 --name dns
uthere add https://example.com --type http --interval 120 --timeout 5
```

New records are checked immediately after they are added.

### List Records

```bash
uthere list
uthere list --all
```

### Run Checks Immediately

```bash
uthere check
uthere check all
uthere check 1
uthere check 1 2 3
```

### Edit Records

```bash
uthere edit 1 --interval 30 --timeout 2
uthere edit 1 --target https://example.org --type http
uthere edit 1 --disable
uthere edit 1 --enable
```

### Remove Records

```bash
uthere remove 1
uthere remove 1 2 3
```

### Descriptions

```bash
uthere description add 1 "this description server"
uthere des add 1 "this description server"
uthere des show 1
uthere des show all
uthere des clear 1
```

### Run the Service Manually

```bash
uthere serve
```

### Database and Socket Overrides

```bash
uthere --db /path/to/uthere.db list
UTHERE_DB=/path/to/uthere.db uthere list

uthere --socket /path/to/uthere.sock add example.com --type ping
UTHERE_SOCKET=/path/to/uthere.sock uthere serve
```

## Alert Configuration

### Channel Selection

```bash
UTHERE_ALERT_CHANNELS=mail
UTHERE_ALERT_CHANNELS=telegram
UTHERE_ALERT_CHANNELS=whatsapp
UTHERE_ALERT_CHANNELS=mail,telegram,whatsapp
```

### Alert Mode

```bash
UTHERE_ALERT_MODE=on_change
UTHERE_ALERT_MODE=always
```

### Mail

```bash
UTHERE_ALERT_CHANNELS=mail
UTHERE_MAIL_HOST=smtp.example.com
UTHERE_MAIL_PORT=587
UTHERE_MAIL_TLS=starttls
UTHERE_MAIL_USER=user@example.com
UTHERE_MAIL_PASSWORD=secret
UTHERE_MAIL_FROM=uthere@example.com
UTHERE_MAIL_TO=ops@example.com,admin@example.com
```

### Telegram

```bash
UTHERE_ALERT_CHANNELS=telegram
UTHERE_TELEGRAM_BOT_TOKEN=123456:token
UTHERE_TELEGRAM_CHAT_ID=123456789
```

### WhatsApp

WhatsApp support uses the Meta WhatsApp Cloud API format.

```bash
UTHERE_ALERT_CHANNELS=whatsapp
UTHERE_WHATSAPP_TOKEN=secret
UTHERE_WHATSAPP_PHONE_NUMBER_ID=123456789
UTHERE_WHATSAPP_TO=905xxxxxxxxx
UTHERE_WHATSAPP_API_VERSION=v20.0
```

### Test Alerts

```bash
uthere alert-test
```

For systemd installations, put these variables in `/etc/default/uthere` and
restart the service:

```bash
sudo systemctl restart uthere
```

## Testing

```bash
PYTHONPATH=src pytest -q
```

Test groups:

- `tests/unit`: repository, alert decisions, and package file generation.
- `tests/integration`: CLI flows and service wake socket behavior.

## Packaging

Generate all packaging files:

```bash
PYTHONPATH=src python3 -m uthere.packager all
```

After installation:

```bash
uthere-packager all
```

Individual targets:

```bash
uthere-packager debian
uthere-packager fedora
uthere-packager gentoo
```

Default output directory:

```text
dist/packages
```

Generated structures:

- Debian: `dist/packages/debian/uthere-<version>/debian`
- Fedora: `dist/packages/fedora/SPECS/uthere.spec` and `dist/packages/fedora/SOURCES/uthere-<version>.tar.gz`
- Gentoo: `dist/packages/gentoo/uthere-<version>.ebuild` and `dist/packages/gentoo/files`

If native build tools are installed:

```bash
uthere-packager all --build
```

## Docker

```bash
docker build -t uthere:latest .
docker volume create uthere-data
docker run -d --name uthere --restart unless-stopped -v uthere-data:/var/lib/uthere uthere:latest
```

The container runs `uthere serve` as the foreground executable. It continuously
checks registered records while the container is running.
Unhealthy or invalid records should not stop the container; they are recorded as
`unhealthy` with the error message in the database.

Use `docker exec` to manage records inside the already-running container:

```bash
docker exec uthere uthere add example.com --type ping --interval 60
docker exec uthere uthere list
docker exec uthere uthere check all
docker exec -it uthere sh
```

Do not use a second `docker run` just to enter the container; that creates a new
container. If that new container does not mount the same `uthere-data` volume,
it will have a fresh empty SQLite database.

Docker Compose:

```bash
docker compose up -d
docker compose exec uthere uthere add example.com --type ping --interval 60
docker compose exec uthere uthere list
docker compose logs -f uthere
```

Release images are published to GitHub Container Registry:

```text
ghcr.io/<owner>/<repo>:v0.1.0
ghcr.io/<owner>/<repo>:0.1.0
ghcr.io/<owner>/<repo>:latest
```

## Release CI

The release workflow runs only when a tag is pushed:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The tag version must match `uthere.__version__`. Beta tags such as
`1.0.1-beta` are normalized to the Python package version `1.0.1b0`.

The workflow also publishes Docker images to GitHub Container Registry:

```text
ghcr.io/<owner>/<repo>:v0.1.0
ghcr.io/<owner>/<repo>:0.1.0
ghcr.io/<owner>/<repo>:latest
```
