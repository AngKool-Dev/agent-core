# Contributing to ARGUS

Thank you for your interest in contributing to ARGUS. This document provides guidelines for contributing.

## Code of Conduct

Be respectful, constructive, and professional in all interactions.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported
2. Open a bug report issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details (Python version, OS, ARGUS version)

### Suggesting Features

1. Open a feature request issue with:
   - Clear description of the feature
   - Use cases and benefits
   - Potential implementation approach

### Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Update documentation if needed
7. Submit a pull request

## Development Setup

```bash
# Clone the repository
git clone https://github.com/AngKool-Dev/agent-core.git
cd agent-core

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in development mode
pip install -e ".[dev]"

# Run tests
python -m pytest tests/
```

## Coding Standards

- Follow existing code patterns and conventions
- Add tests for new functionality
- Document public APIs
- Keep changes focused and minimal

## Security

- Never commit secrets, credentials, or API keys
- Report security vulnerabilities privately
- Follow the security model when making changes

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
