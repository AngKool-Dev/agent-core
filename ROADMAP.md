# ARGUS Roadmap

This document outlines candidate future work for ARGUS beyond 1.0.0.

## Current Version: 1.0.0

ARGUS 1.0.0 is a capability-based AI coding agent framework with:
- Security-first execution model
- Durable execution with crash recovery
- Replay/forensics capabilities
- Provider resilience
- MCP support
- Benchmarking infrastructure
- Performance controls
- UX layer

## Candidate Future Work

### Provider & Model
- Stronger provider qualification with automated health checks
- Broader platform testing (Linux, macOS)
- Improved model routing with latency-based selection
- Support for additional LLM providers

### MCP & Interoperability
- Improved MCP interoperability with standard tool schemas
- MCP server discovery and auto-configuration
- Support for MCP resources and prompts

### User Experience
- Richer TUI with better navigation and visualization
- Interactive configuration wizard
- Improved error messages and troubleshooting guidance
- User configuration UX improvements

### Performance
- Performance optimization for large-scale operations
- Reduced memory footprint
- Faster CLI startup time
- Optimized import times

### Benchmarking
- Expanded benchmark datasets
- Standardized evaluation protocols
- Community benchmark contributions
- Comparative analysis tools

### Build & Release
- Deterministic artifact builds (byte-for-byte reproducible)
- Automated release pipeline
- Multi-platform testing
- Signed releases

### Architecture
- Plugin ecosystem for extensibility
- Remote execution capabilities
- Distributed execution support
- Richer observability and metrics

### Security
- Enhanced audit logging
- Integration with external secret managers
- Compliance reporting
- Regular security audits

## Planning Notes

These are planning items only. Implementation priority will be determined based on:
- User feedback and feature requests
- Security requirements
- Performance benchmarks
- Community contributions

Do not implement these features unless required for release correctness.
