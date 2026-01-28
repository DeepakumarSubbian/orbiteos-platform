# Contributing to OrbitEOS

Thank you for your interest in contributing to OrbitEOS! This document provides guidelines and instructions for contributing.

## 🎯 Ways to Contribute

- 🐛 Report bugs and issues
- 💡 Suggest new features
- 📝 Improve documentation
- 🔧 Submit bug fixes
- ✨ Add new features
- 🧪 Write tests
- 🎨 Improve UI/UX
- 🌍 Translate documentation

## 🚀 Getting Started

### 1. Fork the Repository

Click the "Fork" button at the top of the repository page.

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR_USERNAME/orbiteos-platform
cd orbiteos-platform
```

### 3. Set Up Development Environment

```bash
# Copy environment template
cp .env.example .env

# Start development containers
docker-compose up -d

# Install development dependencies
docker-compose run orbiteos-api pip install -r requirements-dev.txt
```

### 4. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## 📋 Development Guidelines

### Code Style

**Python:**
- Follow PEP 8 style guide
- Use type hints for all functions
- Maximum line length: 100 characters
- Use meaningful variable names
- Write docstrings for all public functions

```python
def calculate_solar_production(
    latitude: float,
    longitude: float,
    timestamp: datetime,
    panel_capacity_kw: float
) -> float:
    """
    Calculate solar production based on sun position and panel capacity.
    
    Args:
        latitude: Location latitude in degrees
        longitude: Location longitude in degrees
        timestamp: Current timestamp (timezone-aware)
        panel_capacity_kw: Panel capacity in kilowatts
    
    Returns:
        Solar production in kilowatts
    """
    # Implementation...
    pass
```

**JavaScript/TypeScript:**
- Use ESLint configuration provided
- Prefer const over let, avoid var
- Use async/await over promises
- Write JSDoc comments

### Testing

**Required:**
- Unit tests for all new functions
- Integration tests for API endpoints
- Minimum 80% code coverage

**Running Tests:**

```bash
# Python tests
docker-compose run orbiteos-api pytest

# With coverage
docker-compose run orbiteos-api pytest --cov=src --cov-report=html

# Specific test file
docker-compose run orbiteos-api pytest tests/test_solar.py
```

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**

```bash
git commit -m "feat(simulators): add heat pump COP curves"
git commit -m "fix(api): correct battery SOC calculation"
git commit -m "docs(readme): update installation instructions"
```

### Documentation

- Update README.md if adding user-facing features
- Add docstrings to all functions
- Update API documentation
- Include examples for complex features

## 🐛 Reporting Bugs

**Before Submitting:**
- Check existing issues
- Test on latest version
- Verify it's reproducible

**Bug Report Should Include:**
- Clear description
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (OS, Docker version)
- Logs and error messages

**Template:**

```markdown
**Bug Description:**
Brief description of the bug

**Steps to Reproduce:**
1. Start containers with `docker-compose up`
2. Navigate to http://localhost:9000
3. Click on...
4. See error

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Environment:**
- OS: Ubuntu 22.04
- Docker: 24.0.5
- OrbitEOS: v0.1.0

**Logs:**
```
[paste relevant logs]
```
```

## 💡 Suggesting Features

**Feature Request Should Include:**
- Clear description of the feature
- Use case and motivation
- Proposed implementation (optional)
- Examples (optional)

## 📝 Pull Request Process

### 1. Ensure Your Code Passes All Checks

```bash
# Run tests
pytest

# Check code style
black --check src/
flake8 src/
mypy src/

# Run linters
pylint src/
```

### 2. Update Documentation

- Update README.md if needed
- Add/update docstrings
- Update API documentation
- Add examples if relevant

### 3. Create Pull Request

**PR Title:** Follow conventional commits format

**PR Description Should Include:**
- What changed
- Why it changed
- How to test it
- Related issues (if any)

**Template:**

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How to test these changes

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] All tests passing
- [ ] No breaking changes (or documented)
```

### 4. Review Process

- Maintainers will review your PR
- Address review comments
- Keep PR focused and small
- Be responsive to feedback

## 🏗️ Project Structure

```
orbiteos-platform/
├── orbiteos-simulators/      # Device simulators
│   ├── src/
│   │   ├── solar_simulator.py
│   │   ├── battery_simulator.py
│   │   └── ...
│   └── tests/
├── orbiteos-api/             # Core API
│   ├── src/
│   └── tests/
├── orbiteos-llm/             # LLM agent
├── homeassistant/            # HA config
├── grafana/                  # Dashboards
└── docs/                     # Documentation
```

## 🔍 Code Review Checklist

**Before Submitting PR:**
- [ ] Code follows style guidelines
- [ ] Tests added for new features
- [ ] All tests passing
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] Error handling included
- [ ] Logging added appropriately
- [ ] No commented-out code
- [ ] No debug print statements

## 🌟 Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- Project documentation

## 📞 Getting Help

- **GitHub Discussions:** Ask questions
- **Discord:** Join our community (coming soon)
- **Email:** dev@orbiteos.io

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You!

Your contributions help make OrbitEOS better for everyone!
