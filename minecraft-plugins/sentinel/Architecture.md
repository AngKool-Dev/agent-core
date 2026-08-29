# Sentinel Architecture

## High-Level Architecture

```
Sentinel/
├── license-server/     # Core license validation and management
├── plugins/            # Extensible plugin system
├── src/                # Shared utilities and core classes
└── pom.xml             # Maven multi-module configuration
```

## Modules

### License Server (`license-server/`)
- Handles license generation, validation, revocation
- REST API for license operations
- Database persistence (H2/PostgreSQL)
- Webhook notifications

### Plugins (`plugins/`)
- Modular plugin architecture
- Each plugin is a separate Maven module
- Plugin loader and lifecycle management

## Data Flow
1. Client requests license validation
2. License server validates against database
3. Returns license status + metadata
4. Plugins can extend validation logic

## Key Decisions
- Maven multi-module for clear separation
- REST API for language-agnostic integration
- Plugin system for extensibility

## Related
- [[Overview.md]]
- [[Requirements.md]]
- [[Decisions.md]]