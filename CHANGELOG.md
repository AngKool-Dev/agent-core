# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-31

### Added

#### Core Architecture
- **Capability-based architecture** with universal `Capability` interface
- **CapabilityRegistry** for dynamic capability registration and discovery
- **CapabilityRouter** for intelligent capability selection
- **ModelCapabilityAdapter** for pluggable LLM provider integration
- **ModelRegistry** for provider management

#### Security
- **SecurityPolicy** with risk classification and permission management
- **TrustBoundary** for execution isolation
- **ApprovalManager** for human-in-the-loop approval workflows
- **SecretManager** for credential handling
- **AuditTrail** for security event logging
- **Sandbox** for execution isolation
- Security-first execution model: MODEL → CAPABILITY ROUTER → SECURITY POLICY → ALLOW/ASK/DENY → EXECUTION

#### Durable Execution
- **DurableExecutor** for journaled, crash-resilient operations
- **ExecutionJournal** for operation persistence
- **CrashDetector** for failure detection
- **ResumeEngine** for operation recovery
- **Reconciler** for state reconciliation after crashes
- **LockManager** for concurrent resume prevention
- Recovery budget to prevent infinite loops

#### Verification & Recovery
- **VerificationEngine** for outcome verification
- **RecoveryEngine** for failure recovery
- **StateStore** for persistent state management
- **SnapshotManager** for state snapshots

#### Event System
- **EventBus** for publish/subscribe event handling
- Canonical event model for observability
- Event-driven architecture for loose coupling

#### Replay & Forensics
- **ReplayEngine** for observational replay of past executions
- Forensic analysis capabilities
- Timeline reconstruction
- Diff checking between executions

#### Review
- **ReviewEngine** for automated code review
- Multi-axis code review (correctness, security, performance, maintainability)
- Evidence-based review reporting

#### MCP (Model Context Protocol)
- **MCPAdapter** for MCP server integration
- **MCPCapabilityAdapter** for MCP tool exposure
- Security-gated MCP execution
- Subprocess lifecycle management

#### Provider Resilience
- **CircuitBreaker** for provider failure handling
- **RetryPolicy** with exponential backoff
- **ProviderHealth** monitoring
- Fallback provider support
- Provider availability classification

#### Benchmarking
- **BenchmarkRunner** for scientific agent evaluation
- **BenchmarkScorecard** for results aggregation
- Reproducibility tracking
- Statistical analysis of results

#### Performance
- **PerformanceMonitor** for resource tracking
- **Scheduler** for task scheduling
- **Backpressure** handling
- Resource contention management

#### UX Layer
- **CommandRegistry** for CLI command dispatch
- **ThemeManager** for UI customization
- **FormattingEngine** for output formatting
- Interactive REPL mode

#### Subagents
- **SubagentManager** for controlled delegation
- **DelegationPolicy** for delegation rules
- **BudgetManager** for resource allocation
- Lifecycle management for subagent execution

#### Validation
- **ValidationRunner** for A-J scenario validation
- **OutcomeContract** for defining success criteria
- **ScenarioVerifier** for scenario execution
- Real Agent Outcome Contract

#### Reality Qualification
- **RealityRunner** for production-reality qualification
- **ProductionEnvironment** capture
- **RealProviderValidator** for provider validation
- **RealMCPValidator** for MCP validation
- **SecretSafetyAuditor** for secret scanning
- **WindowsHardeningTester** for platform-specific testing

#### Release Engineering
- **ReleaseRunner** for release qualification
- **ReleaseReporter** for qualification reporting
- **ArtifactValidator** for build artifact validation
- **Cleanroom** installation testing
- **ReleaseManifest** generation

### Security
- All execution paths gated by SecurityPolicy
- Approval boundaries enforced at multiple levels
- Secrets never enter persisted model-visible state
- Replay remains observational (cannot execute)
- Provider fallback cannot bypass security
- Recovery cannot bypass security
- MCP cannot bypass security

### Qualification
- 418+ tests passing
- Clean wheel and sdist installation verified
- Security invariants validated
- Red-team testing completed
- Crash/resume durability verified
- UNKNOWN reconciliation verified
- Recovery budget preservation verified
- Concurrent execution isolation verified
- Stability soak testing completed
- A-J validation scenarios passed
- GA-001 through GA-014 invariants passed

### Known Limitations
- External provider tests require opt-in credentials
- Long-duration stability tests not executed in CI
- Platform-specific tests may vary outside Windows
- Build reproducibility is semantic (timestamps vary)

[1.0.0]: https://github.com/AngKool-Dev/agent-core/releases/tag/v1.0.0
