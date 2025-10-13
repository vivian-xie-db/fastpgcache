# Changelog

All notable changes to fastpgcache will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-10-13

### Fixed
- **BREAKING BUG FIX**: Cache data now persists across connection close/open cycles
  - Previous versions dropped the cache table on every `setup()` call
  - `setup()` now creates tables only if they don't exist (idempotent)
  - Cache data is only lost on PostgreSQL server restart (UNLOGGED table behavior) or explicit `setup(force_recreate=True)`

### Added
- New `is_setup()` method to check if cache is already initialized
  - Allows conditional setup: `if not cache.is_setup(): cache.setup()`
  - `auto_setup=True` now intelligently checks before running setup
  - Uses simple table query (no `information_schema` access needed)
- New `force_recreate` parameter to `setup()` method
  - `setup()` - Safe, creates tables if not exists (default)
  - `setup(force_recreate=True)` - Drops and recreates all objects (loses data)
- Documentation on cache persistence behavior and usage patterns
- Example code demonstrating cache persistence
- Test script `test_persistence.py` to verify persistence behavior

### Changed
- `CREATE TABLE cache` → `CREATE TABLE IF NOT EXISTS cache`
- `CREATE INDEX` → `CREATE INDEX IF NOT EXISTS`
- `setup()` is now safe to call multiple times without data loss

## [0.1.1] - 2025-10-13

### Changed
- Updated package metadata and documentation

## [0.1.0] - 2025-10-13

### Added
- Initial release
- Redis-like caching interface for PostgreSQL
- UNLOGGED tables for high performance
- TTL support for automatic expiry
- Connection pooling with psycopg2
- Databricks token authentication support
- Automatic token rotation with `DatabricksTokenProvider`
- Methods: `set()`, `get()`, `delete()`, `exists()`, `ttl()`, `cleanup()`
- JSON serialization/deserialization support
- Context manager support

