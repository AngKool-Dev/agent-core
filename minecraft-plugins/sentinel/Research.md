# Sentinel Research

## Technology Evaluations

### License Validation Libraries
- **Bouncy Castle**: Comprehensive crypto, large dependency
- **Java Built-in**: Limited to standard algorithms
- **Decision**: Use Bouncy Castle for license signing

### Database Options
- **H2**: Embedded, fast, good for dev
- **PostgreSQL**: Production standard
- **SQLite**: Single file, no server needed
- **Decision**: H2 for dev, PostgreSQL for prod

### Plugin Systems
- **Pf4j**: Mature, Spring integration
- **JPF**: Simple, lightweight
- **Custom**: Full control, more maintenance
- **Decision**: Custom for now, evaluate Pf4j later

## Related
- [[Decisions.md]]
- [[Architecture.md]]