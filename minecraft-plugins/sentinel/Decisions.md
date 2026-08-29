# Sentinel Decisions

## Architectural Decisions

### 2024-01-15: Maven Multi-Module Structure
**Decision**: Use Maven multi-module for license-server, plugins, and shared code.
**Rationale**: Clear separation of concerns, independent versioning, standard Java tooling.
**Alternatives**: Gradle, single module with packages.

### 2024-01-20: REST API over gRPC
**Decision**: Use REST for license validation API.
**Rationale**: Language-agnostic, easier debugging, broader client support.
**Trade-offs**: More verbose than gRPC, no built-in streaming.

### 2024-02-01: H2 for Development, PostgreSQL for Production
**Decision**: Embedded H2 for dev/test, PostgreSQL for production.
**Rationale**: Zero-config development, production-grade for deployment.

## Related
- [[Architecture.md]]
- [[Requirements.md]]