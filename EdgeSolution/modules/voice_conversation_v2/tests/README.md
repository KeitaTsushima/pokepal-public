# PokePal Voice Conversation - Test Suite

## Overview

This test suite provides comprehensive testing for the PokePal voice conversation module, following Clean Architecture principles with unit, integration, contract, and end-to-end tests.

## Test Coverage

- **Total Tests**: ~460 tests
- **Target Coverage**: 80%
- **Test Distribution**:
  - Unit Tests: 75%
  - Integration Tests: 15%
  - Contract Tests: 5%
  - E2E Tests: 5%

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── domain/             # Domain model tests
│   ├── application/        # Use case and service tests
│   ├── infrastructure/     # External dependency tests
│   └── adapters/           # Input/output adapter tests
├── integration/            # Integration tests
├── contract/               # API contract validation tests
├── e2e/                    # End-to-end system tests
└── pytest.ini             # pytest configuration
```

## Installation

1. **Install test dependencies**:
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

2. **Install additional test tools**:
```bash
pip install coverage pytest-html pytest-xdist
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Contract tests only
pytest tests/contract/

# E2E tests only
pytest tests/e2e/
```

### Run tests with coverage
```bash
pytest --cov=. --cov-report=html --cov-report=term
```

### Run tests in parallel
```bash
pytest -n auto
```

### Run specific test file
```bash
pytest tests/unit/domain/test_conversation.py
```

### Run with verbose output
```bash
pytest -v
```

## Test Requirements

### External Dependencies
The test suite mocks all external dependencies including:
- Azure IoT Hub
- OpenAI API (Whisper, GPT-4)
- Azure Cognitive Services
- Audio devices
- File system operations

### Environment Variables
No environment variables required for running tests - all external services are mocked.

## Test Categories

### Unit Tests (`tests/unit/`)
Tests individual components in isolation:
- **Domain Models**: Core business entities
- **Application Services**: Use case implementations
- **Infrastructure**: External service integrations
- **Adapters**: Input/output interfaces

### Integration Tests (`tests/integration/`)
Tests interaction between multiple components:
- Voice pipeline integration
- Memory persistence
- Configuration management
- Audio processing pipeline

### Contract Tests (`tests/contract/`)
Validates API contracts:
- OpenAI API schemas
- Azure IoT Hub message formats
- Configuration schemas

### E2E Tests (`tests/e2e/`)
Tests complete system flows:
- Full conversation flows
- System startup/shutdown
- Error recovery scenarios

## Writing Tests

### Test Naming Convention
```python
def test_<component>_<scenario>_<expected_result>():
    """Brief description of what the test validates"""
```

### Async Test Pattern
```python
@pytest.mark.asyncio
async def test_async_operation():
    # Test async code
    result = await async_function()
    assert result == expected
```

### Mocking External Dependencies
```python
@patch('infrastructure.ai.openai_client')
def test_with_mock(mock_client):
    mock_client.return_value = "mocked response"
    # Test code
```

## Common Test Commands

### Generate coverage report
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

### Run failed tests only
```bash
pytest --lf
```

### Stop on first failure
```bash
pytest -x
```

### Show test durations
```bash
pytest --durations=10
```

## CI/CD Integration

The test suite is integrated with Azure DevOps CI/CD pipeline. Tests run automatically on:
- Pull request creation
- Commits to main branch
- Nightly builds

## Troubleshooting

### Import Errors
If you encounter import errors, ensure you're running tests from the module root:
```bash
cd EdgeSolution/modules/voice_conversation_v2
pytest
```

### Async Test Warnings
The `pytest.ini` file is configured with `asyncio_mode = auto` to handle async tests properly.

### Mock Issues
All external dependencies are pre-mocked in test files. If a test fails due to missing mocks, check the top of the test file for the mock setup.

## Contributing

When adding new tests:
1. Follow the existing test structure
2. Maintain test independence (no shared state)
3. Mock all external dependencies
4. Include both positive and negative test cases
5. Document complex test scenarios

## Test Maintenance

### Regular Updates
- Update mocks when external API contracts change
- Add tests for new features before implementation
- Remove obsolete tests when features are deprecated

### Performance
- Keep unit tests fast (<100ms each)
- Use fixtures for expensive setup operations
- Consider using pytest-xdist for parallel execution

## Contact

For questions about the test suite, please refer to the main project README or create an issue in the GitHub repository.