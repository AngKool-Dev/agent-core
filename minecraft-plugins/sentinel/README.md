<p align="center">
  <img src="assets/sentinel-banner.png" alt="Sentinel" width="640"/>
</p>

<h1 align="center">Sentinel</h1>

<p align="center">
  Advanced audit logging, inspection &amp; rollback for <strong>Paper 1.21+</strong>
</p>

<p align="center">
  <a href="https://github.com/AngKool-Dev/Sentinel/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/AngKool-Dev/Sentinel/ci.yml?branch=main&label=CI&logo=github" alt="CI"/>
  </a>
  <a href="https://github.com/AngKool-Dev/Sentinel/releases">
    <img src="https://img.shields.io/github/v/release/AngKool-Dev/Sentinel?label=Release&logo=github" alt="Release"/>
  </a>
  <a href="https://github.com/AngKool-Dev/Sentinel/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/AngKool-Dev/Sentinel" alt="License"/>
  </a>
  <img src="https://img.shields.io/badge/Java-21-orange?logo=openjdk&logoColor=white" alt="Java 21"/>
  <img src="https://img.shields.io/badge/Paper-1.21%2B-blue?logo=paper&logoColor=white" alt="Paper 1.21+"/>
</p>

---

## What is Sentinel?

Sentinel is an **audit & recovery plugin** that records what happens on your
server and lets you answer one question: *"who did this, and can we undo it?"*

- **Inspect** any block or entity — see who placed, broke, or modified it, and when.
- **Rollback** griefing, theft, or accidents — restore blocks and inventories to a previous state.
- **Persist** everything to **SQLite** (zero setup) or **PostgreSQL** (multi-server / heavy traffic).

> Built for Java 21 with virtual threads, a bounded async audit pipeline, and
> an in-memory cache so the hot path never blocks the main server thread.

## Features

| | |
|---|---|
| ⛏️ **Block inspection** | Ray-traced inspection with a 3×3×3 neighborhood fallback — even find blocks that were *removed*. |
| 🧾 **Player history** | Query the last 30 actions by a player, or every edit within a radius around you. |
| ↩️ **Rollback** | Restore blocks by player, region, or world; restore inventories; restore item losses from despawn, void, fire & lava. |
| 🧱 **38 audit actions** | Block, inventory, environment, entity, chat, command, and item-loss events — configurable per action. |
| 🗄️ **Two databases** | SQLite file (`sentinel.db`, WAL mode) or PostgreSQL with Flyway migrations. |
| ⚡ **Async & cached** | Bounded queue + periodic flush + LRU caches; zero-blocking by design. |
| 🧹 **Auto-purge** | Scheduled cleanup of records older than your retention window. |
| 🔒 **Public API** | `AuditService`, `InspectionService`, `RollbackService` for other plugins. |

## Screenshots

> Coming soon. Have a screenshot of Sentinel in action? Drop it in a PR!

## Requirements

- **Java 21** (virtual threads)
- **Paper 1.21+** (or a Paper-fork like Purpur)

*PostgreSQL 14+ is optional — SQLite works out of the box.*

## Installation

1. Download the latest `Sentinel-*.jar` from the [Releases](https://github.com/AngKool-Dev/Sentinel/releases) page.
2. Drop the jar into your server's `plugins/` folder.
3. Restart the server (or run `/reload`).
4. Configure `plugins/Sentinel/config.yml` to taste.
5. Check it's healthy: `/sentinel status`.

## Commands

All commands live under the `/sentinel` root (alias `/sn`).

| Command | Description |
|---------|-------------|
| `/sentinel inspect [on\|off]` | Toggle inspection mode; click blocks/entities to see their history |
| `/sentinel inspect player:<name>` | Last 30 actions by a player |
| `/sentinel inspect radius:<blocks>` | Edits within a radius around you |
| `/sentinel rollback <target>:<value> [t:<time>]` | Restore changes by `player`, `inventory`, `inventory:world`, `radius`, or `world` |
| `/sentinel purge <time>` | Delete audit records older than a duration (e.g. `30d`) |
| `/sentinel reload` | Reload configuration |
| `/sentinel status` | Show version, database backend, and status |
| `/sentinel license` | Show license state, bound IP, and expiry (release builds) |

Rollback time windows: `t:HH:MM:SS` (clock time) or `t:1day`, `t:30days`, `t:2h`, `t:45m`. Default window: last 7 days.

## Permissions

All permissions default to **op** (`default: op`).

| Permission | Description |
|------------|-------------|
| `sentinel.admin` | Access to all Sentinel commands |
| `sentinel.inspect` | Inspect blocks |
| `sentinel.rollback` | Rollback changes |
| `sentinel.purge` | Purge audit records |
| `sentinel.reload` | Reload configuration |
| `sentinel.status` | View plugin status |

## Configuration

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the full reference.
Highlights from `config.yml`:

```yaml
database:
  type: SQLITE            # SQLITE | POSTGRESQL
  host: localhost
  port: 5432
  database: sentinel
  username: sentinel
  password: ""

audit:
  enabled: true
  batch-size: 500
  flush-interval-ms: 5000
  log-inventory: true
  log-chat: true
  log-commands: true

rollback:
  enabled: true
  max-blocks-per-operation: 100000
  restore-inventories: true
  notify-players: true
```

## Documentation

- [Configuration](docs/CONFIGURATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database Schema](docs/DATABASE.md)
- [Public API](docs/API.md)
- [UML](docs/UML.md)

## Building from source

```bash
mvn clean package            # free Lite edition (no premium features, no license)
mvn package -P dev           # full feature set, license enforcement OFF (local dev only)
mvn package -P release       # sellable build: full features + license enforcement ON
```

- The default build is the **Lite** edition (free, no license key needed).
- `-P dev` compiles the full premium feature set with enforcement disabled — for
  local development/testing only. It must not be distributed.
- `-P release` produces the sellable premium jar. It enables license
  enforcement and requires `license.serverUrl` and `license.publicKey`:

```bash
mvn package -P release \
  -Dlicense.serverUrl=https://your-license-server \
  -Dlicense.publicKey=<ed25519 public key>
```

The shaded jar is written to `target/Sentinel-<version>.jar` (or
`target/Sentinel-Lite-<version>.jar` / `target/Sentinel-Dev-<version>.jar`).

### License server security

- License responses are Ed25519-signed and now include an issuance timestamp
  (`iat`); the plugin rejects any response older than a few minutes, so a captured
  response cannot be replayed after a key is revoked or expires.
- The buyer's license key is sent in the `X-Sentinel-Key` request header (not the
  URL), and admin operations accept the token via `X-Admin-Token`. Deploy the
  updated `license-server` (Java or Cloudflare Worker) together with a `release`
  jar.

## License

Released under the [MIT License](LICENSE).
