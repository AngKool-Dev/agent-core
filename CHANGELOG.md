# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-18

### Added
- Initial public framework release
- Runtime adapter abstraction (`RuntimeAdapter` base class)
- Hermes runtime adapter (`HermesRuntime`)
- Task state machine with persistence
- Skill discovery and routing
- Memory abstraction with in-memory backend
- Verification system with project-type awareness
- Tool execution framework
- Event bus and observability
- Real-runtime test separation with `AGENTCORE_REAL_RUNTIME` opt-in
- Verification scope (`project` / `changed-files`) with Git delta tracking
- Runtime capability contract (`text_generation`, `tool_calls`, `external_tool_execution`, `streaming`, `cancellation`)
- Agent capability awareness with contract violation detection

### Changed
- Public API surface defined in `agentcore/__init__.py`
- Package metadata and distribution configuration

### Deprecated
- None

### Removed
- None

### Fixed
- None

### Security
- Subprocess invocations audited for portability
