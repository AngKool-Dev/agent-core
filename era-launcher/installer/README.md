# EraLauncher Web Installer

## Overview

This directory contains the source code and build scripts for EraLauncher's web-based installer, inspired by [SKlauncher's web setup installer](https://github.com/sklauncher) (`SKlauncher-4.0.29-web-setup.exe`).

## SKlauncher Analysis

The SKlauncher installer (`SKlauncher-4.0.29-web-setup.exe`) is a **web-based installer** (not a bundled installer). It works as follows:

1. **Tiny bootstrap** (~200KB NSIS/Inno Setup installer)
2. **Downloads JRE at install time** — uses a mirror system:
   - Primary: Azul Zulu JRE
   - Fallback: Adoptium Temurin
3. **Downloads JavaFX separately** — downloads individual JavaFX modules from `maven.skmedix.pl`
4. **SHA-256 verification** — all downloads are verified against known checksums
5. **Rollback capability** — if JRE install fails, restores the backup
6. **Installation to `{userappdata}\sklauncher`** — portable installation in user AppData
7. **Minecraft directory** at `{userappdata}\.minecraft\sklauncher`

**Key design pattern**: The installer itself is tiny. The actual application (Java + JavaFX + SKlauncher JAR) is downloaded at install time, ensuring the latest version is always installed and minimizing installer size.

## EraLauncher Web Installer Design

Our web installer follows the same pattern but adapted for a Rust-based launcher:

### Components

| Component | Description |
|-----------|-------------|
| `src/bin/era-launcher-web-installer.rs` | Standalone bootstrap binary — downloads launcher + Java |
| `src/installer.rs` | In-launcher installer module (for programmatic installs) |
| `installer/install.nsi` | NSIS script for packaging the bootstrap into an .exe |
| `installer/install.iss` | Inno Setup script (alternative to NSIS) |

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  era-launcher-web-installer.exe (NSIS/Inno wrapper)│
│  ┌──────────────────────────────────────────────┐  │
│  │  era-launcher-web-installer (Rust binary)   │  │
│  │  ├─ Downloads era-launcher binary           │  │
│  │  │   from GitHub releases                   │  │
│  │  ├─ Downloads Java JRE (optional)          │  │
│  │  │   from Adoptium Temurin (primary)        │  │
│  │  │   from Azul Zulu (fallback)              │  │
│  │  ├─ Verifies SHA-256 checksums             │  │
│  │  ├─ Creates desktop shortcut              │  │
│  │  └─ Saves Java path to config             │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Key Differences from SKlauncher

| Aspect | SKlauncher | EraLauncher |
|--------|-----------|-------------|
| Language | Java (JAR) | Rust (native binary) |
| JRE requirement | Required (Java + JavaFX) | Required only for Minecraft |
| Installer framework | NSIS | NSIS + Inno Setup (dual support) |
| Download source | Maven + Adoptium | GitHub Releases + Adoptium |
| Shortcut format | .lnk + .url | .bat + .url (Windows) / .desktop (Linux) |

## Usage

### Building the web installer

```bash
# Build the web installer binary
cargo build --release --bin era-launcher-web-installer

# The binary will be at:
# target/release/era-launcher-web-installer.exe
```

### Running the web installer

```bash
# Full installation (downloads launcher + Java + creates shortcut)
era-launcher-web-installer.exe

# Skip Java installation
era-launcher-web-installer.exe --no-java

# Skip desktop shortcut
era-launcher-web-installer.exe --no-shortcut

# Specify Java version
era-launcher-web-installer.exe --java 17
```

### Packaging as .exe (Windows)

Requires [NSIS](https://nsis.sourceforge.io/) or [Inno Setup](https://jrsoftware.org/isinfo.php):

```bash
# Using NSIS
makensis installer/install.nsi

# Using Inno Setup (alternative)
ISCC installer/install.iss
```

## Mirror Fallback Strategy

The installer tries Java mirrors in order, following SKlauncher's approach:

1. **Adoptium Temurin** (primary) — `https://api.adoptium.net/v3/binary/latest/{version}/ga/windows/x64/jre/hotspot`
2. **Azul Zulu** (fallback) — `https://cdn.azul.com/zulu/bin/...`

If the primary mirror fails (network error, checksum mismatch), the installer automatically falls back to the secondary mirror.

## Security

- All downloaded files are verified via SHA-256 checksums where available
- The Adoptium API provides TLS with valid certificates
- The Java version is validated by running `java -version` after extraction
- The launcher binary is downloaded directly from GitHub releases (verified by GitHub's TLS)

## License

This installer is part of the EraLauncher project and is licensed under MIT.
