# Installation Guide for FastPgCache

This guide will help you install and publish the FastPgCache library.

## For Users

### Install from PyPI (once published)

```bash
pip install fastpgcache
```

### Install from source

```bash
# Clone the repository
git clone https://github.com/yourusername/fastpgcache.git
cd fastpgcache

# Install in development mode
pip install -e .

# Or install normally
pip install .
```

### Install with development dependencies

```bash
pip install -e ".[dev]"
```

## For Developers

### 1. Prerequisites

- Python 3.7 or higher
- PostgreSQL 9.6 or higher
- pip and setuptools

### 2. Set up development environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Unix/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### 3. Run tests (if you create them)

```bash
pytest tests/
```

### 4. Run examples

```bash
# Make sure PostgreSQL is running and update credentials in examples
python examples/basic_usage.py
python examples/connection_string.py
python examples/context_manager.py
python examples/advanced_usage.py
```

## Publishing to PyPI

### 1. Install build tools

```bash
pip install build twine
```

### 2. Build the package

```bash
# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Build source and wheel distributions
python -m build
```

This creates:
- `dist/fastpgcache-0.1.0.tar.gz` (source distribution)
- `dist/fastpgcache-0.1.0-py3-none-any.whl` (wheel distribution)

### 3. Test the build locally

```bash
# Install the built package in a test environment
pip install dist/fastpgcache-0.1.0-py3-none-any.whl
```

### 4. Upload to TestPyPI (optional, for testing)

```bash
# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*

# Install from TestPyPI to test
pip install --index-url https://test.pypi.org/simple/ fastpgcache
```

### 5. Upload to PyPI (production)

```bash
# Upload to PyPI
python -m twine upload dist/*
```

You'll be prompted for your PyPI username and password.

### 6. Use API token (recommended)

Instead of username/password, use PyPI API tokens:

1. Create API token at: https://pypi.org/manage/account/token/
2. Create `~/.pypirc` file:

```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmcC...your-token-here
```

3. Upload:
```bash
python -m twine upload dist/*
```

## Quick Start After Installation

```python
from fastpgcache import FastPgCache

# Initialize
cache = FastPgCache(
    host="localhost",
    database="postgres",
    user="postgres",
    password="your_password",
    auto_setup=True
)

# Use it!
cache.set("key", {"data": "value"}, ttl=300)
value = cache.get("key")
print(value)  # {'data': 'value'}

cache.close()
```

## Environment Variables (Optional)

You can use environment variables for connection:

```bash
export PGCACHE_HOST=localhost
export PGCACHE_PORT=5432
export PGCACHE_DATABASE=postgres
export PGCACHE_USER=postgres
export PGCACHE_PASSWORD=your_password
```

Then in your code:
```python
import os
from fastpgcache import FastPgCache

cache = FastPgCache(
    host=os.getenv('PGCACHE_HOST', 'localhost'),
    port=int(os.getenv('PGCACHE_PORT', 5432)),
    database=os.getenv('PGCACHE_DATABASE', 'postgres'),
    user=os.getenv('PGCACHE_USER', 'postgres'),
    password=os.getenv('PGCACHE_PASSWORD', ''),
    auto_setup=True
)
```

## Troubleshooting

### PostgreSQL connection errors

If you get connection errors, verify:
1. PostgreSQL is running
2. Credentials are correct
3. Database exists
4. User has necessary permissions

```bash
# Test connection with psql
psql -h localhost -U postgres -d postgres
```

### Permission errors during setup

Make sure your PostgreSQL user has permissions to:
- CREATE TABLE
- CREATE FUNCTION
- CREATE INDEX
- CREATE VIEW

```sql
GRANT CREATE ON SCHEMA public TO your_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO your_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_user;
```

### Module not found errors

Make sure you've installed the package:
```bash
pip install -e .
```

Or the dependencies:
```bash
pip install -r requirements.txt
```

## Uninstall

```bash
pip uninstall fastpgcache
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/fastpgcache/issues
- Documentation: https://github.com/yourusername/fastpgcache#readme

