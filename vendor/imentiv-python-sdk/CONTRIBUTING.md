# Contributing to Imentiv Python SDK

Thank you for your interest in contributing to the Imentiv Python SDK! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/imentiv-python-sdk.git
   cd imentiv-python-sdk
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

1. **Install the package in development mode**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Verify the installation**:
   ```bash
   python -c "import imentiv; print(imentiv.__version__)"
   ```

## Making Changes

### Code Style

We follow Python best practices and use automated tools for code quality:

- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **mypy** for type checking
- **pytest** for testing

### Running Quality Checks

Before submitting your changes, run:

```bash
# Format code
black imentiv tests examples

# Check linting
ruff check imentiv tests examples

# Run tests
pytest

# Run tests with coverage
pytest --cov=imentiv --cov-report=term-missing
```

### Writing Tests

- Add tests for any new functionality
- Ensure all tests pass before submitting
- Aim for high test coverage (>80%)
- Place tests in the `tests/` directory

Example test:

```python
def test_my_feature(mock_api_key):
    """Test my new feature."""
    client = ImentivClient(api_key=mock_api_key)
    result = client.my_feature()
    assert result is not None
```

### Documentation

- Add docstrings to all public methods
- Follow Google-style docstring format
- Include examples in docstrings
- Update README.md if adding new features

Example docstring:

```python
def my_method(self, param: str) -> dict:
    """
    Brief description of the method.

    Args:
        param: Description of the parameter.

    Returns:
        Dictionary containing the result.

    Example:
        >>> client.my_method("value")
        {"key": "value"}
    """
    pass
```

## Submitting Changes

1. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

2. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Open a Pull Request** on GitHub with:
   - Clear description of changes
   - Link to any related issues
   - List of tests added/modified
   - Screenshots (if UI changes)

## Pull Request Guidelines

- Keep changes focused and atomic
- Write clear commit messages
- Include tests for new features
- Update documentation as needed
- Ensure all CI checks pass
- Respond to review feedback promptly

## Code Review Process

1. Automated checks run on all PRs
2. Maintainers review code for quality and design
3. Feedback is provided for improvements
4. Once approved, changes are merged

## Reporting Issues

When reporting bugs or requesting features:

- Use the GitHub issue tracker
- Provide a clear description
- Include steps to reproduce (for bugs)
- Add code examples if relevant
- Specify your environment (Python version, OS)

## Questions?

If you have questions about contributing, feel free to:
- Open an issue on GitHub
- Email: support@imentiv.ai

Thank you for contributing to the Imentiv Python SDK! 🎉
