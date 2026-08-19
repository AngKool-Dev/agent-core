import pytest

from agentcore.memory import MemoryBackend, MemoryManager


class TestMemoryBackend:
    def test_memory_backend_is_abstract(self):
        with pytest.raises(TypeError):
            MemoryBackend()

    def test_memory_backend_methods_are_abstract(self):
        class ConcreteMemory(MemoryBackend):
            def search(self, query, project=None, limit=20):
                return []

            def store(self, type, content, project=None, importance=0.5):
                return {}

            def update(self, memory_id, content):
                return {}

            def list(self, project=None, type=None, limit=50):
                return []

        backend = ConcreteMemory()
        assert backend.search("test") == []
        assert backend.store("fact", "test content") == {}


class TestMemoryManager:
    def test_memory_manager_wraps_backend(self):
        class FakeBackend(MemoryBackend):
            def __init__(self):
                self.stored = []

            def search(self, query, project=None, limit=20):
                return [m for m in self.stored if query in m.get("content", "")]

            def store(self, type, content, project=None, importance=0.5):
                mem = {"id": "test-1", "type": type, "content": content, "project": project}
                self.stored.append(mem)
                return mem

            def update(self, memory_id, content):
                for m in self.stored:
                    if m["id"] == memory_id:
                        m["content"] = content
                        return m
                return {}

            def list(self, project=None, type=None, limit=50):
                return [m for m in self.stored if (project is None or m["project"] == project)]

        backend = FakeBackend()
        manager = MemoryManager(backend)

        result = manager.store("decision", "Use async pattern", project="test-project")
        assert result["id"] == "test-1"
        assert result["type"] == "decision"

        results = manager.search("async", project="test-project")
        assert len(results) == 1

    def test_store_decision(self):
        class FakeBackend(MemoryBackend):
            def __init__(self):
                self.last_type = None
                self.last_content = None

            def search(self, query, project=None, limit=20):
                return []

            def store(self, type, content, project=None, importance=0.5):
                self.last_type = type
                self.last_content = content
                return {"id": "new-id", "type": type, "content": content, "project": project}

            def update(self, memory_id, content):
                return {}

            def list(self, project=None, type=None, limit=50):
                return []

        backend = FakeBackend()
        manager = MemoryManager(backend)

        manager.store_decision("Use memory abstraction", "my-project", "Discussed design")

        assert backend.last_type == "decision"
        assert "Use memory abstraction" in backend.last_content

    def test_retrieve_relevant_memory(self):
        class FakeBackend(MemoryBackend):
            def __init__(self):
                self.data = []

            def search(self, query, project=None, limit=20):
                if "database" in query:
                    return [
                        {"id": "m1", "type": "architecture", "content": "Use SQLite for database"},
                    ]
                return []

            def store(self, type, content, project=None, importance=0.5):
                return {"id": "new", "type": type, "content": content}

            def update(self, memory_id, content):
                return {"id": memory_id, "content": content}

            def list(self, project=None, type=None, limit=50):
                return []

        backend = FakeBackend()
        manager = MemoryManager(backend)

        results = manager.retrieve_relevant_memory("database choice", "my-project")
        assert "SQLite" in results
