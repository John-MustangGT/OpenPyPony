# Contributing to OpenPyPony

## Development Setup

### Prerequisites
- Python 3.7+
- CircuitPython-compatible device
- Git

### Setup
```bash
git clone https://github.com/John-MustangGT/OpenPyPony.git
cd OpenPyPony
pip install -r tools/requirements.txt
```

## Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Code Style

- Python: Follow PEP 8
- C/C++: Follow Linux kernel style
- Comments: Clear and concise
- Documentation: Update relevant docs

## Testing
```bash
# Run tests
pytest tests/

# Test deployment
make deploy
```

## Submitting Changes

1. Ensure all tests pass
2. Update documentation
3. Add entry to CHANGELOG.md
4. Create pull request with clear description
