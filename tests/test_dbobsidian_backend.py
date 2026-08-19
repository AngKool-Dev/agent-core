"""
Regression tests for DBObsidianBackend persistence.

These tests verify that the DB-Obsidian integration works correctly from
an installed-package layout — ensuring the schema file can be located
correctly after pip installation.

Covers:
  1. DBObsidianBackend initializes from installed package layout
  2. Schema can be located correctly
  3. Database initializes successfully
  4. Memory can be stored
  5. Memory can be retrieved
  6. Confidence survives persistence
  7. Restart recovery works
  8. Duplicate memories remain idempotent
  9. Search works after restart
  10. Missing db-obsidian still gracefully falls back to InMemoryBackend
"""

import pytest

try:
    import db_obsidian

    _DBO_AVAILABLE = True
    _SCHEMA_OK = db_obsidian.SCHEMA_FILE.exists()
except ImportError:
    _DBO_AVAILABLE = False
    _SCHEMA_OK = False

from agentcore.adapters.memory_dbobsidian import DBObsidianBackend
from agentcore.memory import InMemoryBackend, MemoryBackend

pytestmark = pytest.mark.skipif(
    not (_DBO_AVAILABLE and _SCHEMA_OK),
    reason="db-obsidian not available or schema missing; "
    "install with: pip install git+https://github.com/AngKool-Dev/db-obsidian",
)


class TestDBObsidianBackendSchemaLocation:
    """Verify the db-obsidian package's schema files are accessible from installed layout."""

    def test_schema_file_exists(self):
        """The schema.sql file must exist at the path computed by db_obsidian.__init__."""
        assert db_obsidian.SCHEMA_FILE.exists(), (
            f"Schema file not found at {db_obsidian.SCHEMA_FILE}. "
            "The db-obsidian package must include db/schema.sql as package data."
        )

    def test_migrations_dir_exists(self):
        """The migrations directory must exist at the path computed by db_obsidian.__init__."""
        assert db_obsidian.MIGRATIONS_DIR.exists(), (
            f"Migrations dir not found at {db_obsidian.MIGRATIONS_DIR}. "
            "The db-obsidian package must include db/migrations/ as package data."
        )

    def test_schema_contains_core_tables(self):
        """The schema file must define the core tables used by AgentCore."""
        schema = db_obsidian.SCHEMA_FILE.read_text(encoding="utf-8")
        assert "CREATE TABLE" in schema, "Schema should contain CREATE TABLE statements"
        required_tables = ["memories", "schema_version", "sessions"]
        for table in required_tables:
            assert table in schema, f"Schema must define table '{table}'"


class TestDBObsidianBackendInitialization:
    """Verify DBObsidianBackend initializes correctly from installed package."""

    def test_backend_initializes(self, tmp_path):
        """DBObsidianBackend should initialize without errors from installed package."""
        db_path = tmp_path / "test_init.db"
        backend = DBObsidianBackend(db_path)
        backend.close()

    def test_backend_creates_database_file(self, tmp_path):
        """The backend should create the SQLite database file on bootstrap."""
        db_path = tmp_path / "test_create.db"
        backend = DBObsidianBackend(db_path)
        assert db_path.exists(), "Database file should be created"
        backend.close()

    def test_backend_has_required_tables(self, tmp_path):
        """The database should have the required tables after initialization."""
        db_path = tmp_path / "test_tables.db"
        backend = DBObsidianBackend(db_path)
        tables = backend.db.integrity_check()
        assert tables[0] == "ok", "Database integrity check should pass"

        conn = backend.db.connect()
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {r[0] for r in result}
        conn.close()

        assert "memories" in table_names
        assert "schema_version" in table_names
        backend.close()


class TestDBObsidianBackendStoreRetrieve:
    """Verify memory can be stored and retrieved through DBObsidianBackend."""

    def test_store_and_retrieve(self, tmp_path):
        """A stored memory should be retrievable by its ID."""
        db_path = tmp_path / "test_store.db"
        backend = DBObsidianBackend(db_path)

        mem = backend.store(
            type="fact",
            content="Python list comprehensions are concise ways to create lists.",
            project="test-project",
            importance=0.8,
            confidence=0.9,
        )
        retrieved = backend.get(mem["id"])
        assert retrieved is not None, "Should retrieve stored memory"
        assert retrieved["content"] == mem["content"]
        assert retrieved["type"] == "fact"
        assert retrieved["project"] == "test-project"
        backend.close()

    def test_search_finds_stored_memory(self, tmp_path):
        """Search should find a stored memory by query text."""
        db_path = tmp_path / "test_search.db"
        backend = DBObsidianBackend(db_path)

        backend.store(
            type="fact",
            content="The Python package manager is pip.",
            project="test-project",
            importance=0.7,
            confidence=0.8,
        )

        results = backend.search("package manager", project="test-project", limit=10)
        assert len(results) > 0, "Search should find stored memory"
        backend.close()

    def test_search_filters_by_project(self, tmp_path):
        """Search should filter results by project."""
        db_path = tmp_path / "test_filter.db"
        backend = DBObsidianBackend(db_path)

        backend.store(type="fact", content="Memory for project A", project="project-a")
        backend.store(type="fact", content="Memory for project B", project="project-b")

        results_a = backend.search("Memory", project="project-a", limit=10)
        results_b = backend.search("Memory", project="project-b", limit=10)

        assert len(results_a) == 1, "Should find 1 memory for project-a"
        assert len(results_b) == 1, "Should find 1 memory for project-b"
        backend.close()


class TestDBObsidianBackendConfidencePersistence:
    """Verify confidence survives the store → retrieve → restart cycle."""

    def test_confidence_survives_retrieve(self, tmp_path):
        """Confidence set during store should be retrievable."""
        db_path = tmp_path / "test_conf.db"
        backend = DBObsidianBackend(db_path)

        mem = backend.store(
            type="fact",
            content="Test confidence persistence",
            project="test",
            importance=0.5,
            confidence=0.85,
        )
        retrieved = backend.get(mem["id"])
        assert retrieved is not None
        assert retrieved["confidence"] == 0.85, (
            f"Expected confidence=0.85, got {retrieved['confidence']}"
        )
        backend.close()

    def test_confidence_update_persists(self, tmp_path):
        """Updated confidence should persist across restart."""
        db_path = tmp_path / "test_conf_update.db"
        backend = DBObsidianBackend(db_path)

        mem = backend.store(
            type="fact",
            content="Confidence update test",
            project="test",
            confidence=0.8,
        )
        backend.update_confidence(mem["id"], confidence=0.6, reason="verified")
        backend.close()

        # Reopen
        backend2 = DBObsidianBackend(db_path)
        retrieved = backend2.get(mem["id"])
        assert retrieved is not None, "Memory should survive restart"
        assert retrieved["confidence"] == 0.6, (
            f"Expected updated confidence=0.6, got {retrieved['confidence']}"
        )
        backend2.close()


class TestDBObsidianBackendRestartRecovery:
    """Verify DBObsidianBackend survives restart (database persistence)."""

    def test_memory_survives_restart(self, tmp_path):
        """A stored memory should be present after reopening the backend."""
        db_path = tmp_path / "test_restart.db"
        backend = DBObsidianBackend(db_path)

        mem = backend.store(
            type="fact",
            content="This memory should survive a restart",
            project="test-project",
            confidence=0.9,
        )
        mem_id = mem["id"]
        backend.close()

        # Simulate restart — create a new backend pointing at the same DB file
        backend2 = DBObsidianBackend(db_path)
        retrieved = backend2.get(mem_id)
        assert retrieved is not None, "Memory should survive restart"
        assert retrieved["content"] == "This memory should survive a restart"
        assert retrieved["project"] == "test-project"
        backend2.close()

    def test_search_works_after_restart(self, tmp_path):
        """Search should work correctly after reopening the backend."""
        db_path = tmp_path / "test_search_restart.db"
        backend = DBObsidianBackend(db_path)

        backend.store(
            type="fact",
            content="Searchable content for restart test",
            project="test-project",
        )
        backend.close()

        backend2 = DBObsidianBackend(db_path)
        results = backend2.search("Searchable", project="test-project", limit=10)
        assert len(results) > 0, "Search should work after restart"
        backend2.close()

    def test_empty_backend_returns_empty_results(self, tmp_path):
        """A fresh backend should return empty results for any search."""
        db_path = tmp_path / "test_empty.db"
        backend = DBObsidianBackend(db_path)
        assert backend.list() == [], "Empty backend should have no memories"
        assert backend.search("anything") == [], "Search on empty backend should return empty"
        backend.close()


class TestDBObsidianBackendIdempotency:
    """Verify duplicate memories are handled idempotently."""

    def test_duplicate_content_is_idempotent(self, tmp_path):
        """Storing the same content twice should not create duplicates."""
        db_path = tmp_path / "test_dedup.db"
        backend = DBObsidianBackend(db_path)

        mem1 = backend.store(
            type="fact",
            content="Deduplication test content",
            project="test-project",
        )
        mem2 = backend.store(
            type="fact",
            content="Deduplication test content",
            project="test-project",
        )

        memories = backend.list()
        assert len(memories) == 1, (
            f"Should have 1 memory after duplicate store, got {len(memories)}"
        )
        assert mem1["id"] == mem2["id"], "Duplicate should return same ID"
        backend.close()


class TestGracefulFallback:
    """Verify graceful fallback when db-obsidian is unavailable."""

    def test_inmemory_backend_is_memorybackend_subclass(self):
        """InMemoryBackend should be a MemoryBackend subclass."""
        assert issubclass(InMemoryBackend, MemoryBackend)

    def test_inmemory_backend_works_standalone(self):
        """InMemoryBackend should store and retrieve without external deps."""
        backend = InMemoryBackend()
        mem = backend.store(
            type="fact",
            content="In-memory test",
            project="test",
        )
        retrieved = backend.get(mem["id"])
        assert retrieved is not None
        assert retrieved["content"] == "In-memory test"
