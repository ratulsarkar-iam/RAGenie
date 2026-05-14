"""
Unit tests for Persistent Memory System
Based on openspec/changes/personal-assistant-enhancements/specs/persistent-memory/spec.md
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from src.memory.memory_store import MemoryStore
from src.memory.memory_manager import MemoryManager
from src.memory.models import Memory, MemoryType, UserContext

class TestMemoryStore:
    """Test the core memory storage functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp()
        os.close(fd)
        yield path
        os.unlink(path)
    
    @pytest.fixture
    def memory_store(self, temp_db):
        """Initialize MemoryStore with temporary database."""
        return MemoryStore(db_path=temp_db)
    
    def test_init_database(self, memory_store):
        """Test database initialization creates required tables."""
        with sqlite3.connect(memory_store.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='memories'
            """)
            assert cursor.fetchone() is not None
    
    def test_store_memory(self, memory_store):
        """Test storing a memory entry."""
        memory = Memory(
            id=None,
            type=MemoryType.PREFERENCE,
            content="User prefers dark mode",
            metadata={"ui_preference": "dark"},
            created_at=datetime.utcnow()
        )
        
        memory_id = memory_store.store_memory(memory)
        assert memory_id is not None
        assert len(memory_id) == 36  # UUID length
    
    def test_retrieve_memories_by_content(self, memory_store):
        """Test retrieving memories by content search."""
        # Store test memories
        memories = [
            Memory(id=None, type=MemoryType.PREFERENCE, content="Prefers dark mode", metadata={}, created_at=datetime.utcnow()),
            Memory(id=None, type=MemoryType.FACT, content="Python is a programming language", metadata={}, created_at=datetime.utcnow()),
            Memory(id=None, type=MemoryType.GOAL, content="Learn machine learning", metadata={}, created_at=datetime.utcnow())
        ]
        
        for memory in memories:
            memory_store.store_memory(memory)
        
        # Search for "dark" - returns preference match + all preference-type rows
        results = memory_store.retrieve_memories("dark", limit=5)
        assert any("dark mode" in m.content for m in results)
        
        # Search for "programming" - returns content match + all preference-type rows
        results = memory_store.retrieve_memories("programming", limit=5)
        assert any("programming language" in m.content for m in results)
    
    def test_retrieve_memories_by_type(self, memory_store):
        """Test retrieving memories by type."""
        # Store different types
        memory_store.store_memory(
            Memory(id=None, type=MemoryType.PREFERENCE, content="Prefers dark mode", metadata={}, created_at=datetime.utcnow())
        )
        memory_store.store_memory(
            Memory(id=None, type=MemoryType.PREFERENCE, content="Prefers minimal UI", metadata={}, created_at=datetime.utcnow())
        )
        memory_store.store_memory(
            Memory(id=None, type=MemoryType.GOAL, content="Learn ML", metadata={}, created_at=datetime.utcnow())
        )
        
        # Retrieve preferences
        results = memory_store.retrieve_memories("", limit=10)
        preference_count = sum(1 for m in results if m.type == MemoryType.PREFERENCE)
        assert preference_count >= 2
    
    def test_access_count_increment(self, memory_store):
        """Test that access count increments on retrieval."""
        memory = Memory(
            id=None, type=MemoryType.FACT, content="Test fact", metadata={}, created_at=datetime.utcnow()
        )
        memory_id = memory_store.store_memory(memory)
        
        # First retrieval
        results = memory_store.retrieve_memories("Test", limit=5)
        assert results[0].access_count == 1
        
        # Second retrieval
        results = memory_store.retrieve_memories("Test", limit=5)
        assert results[0].access_count == 2
    
    def test_memory_ordering(self, memory_store):
        """Test memories are ordered by access count and last accessed."""
        # Store memories with different timestamps
        old_time = datetime.utcnow() - timedelta(days=1)
        recent_time = datetime.utcnow()
        
        old_memory = Memory(
            id=None, type=MemoryType.FACT, content="Old fact", metadata={}, created_at=old_time
        )
        new_memory = Memory(
            id=None, type=MemoryType.FACT, content="New fact", metadata={}, created_at=recent_time
        )
        
        memory_store.store_memory(old_memory)
        memory_store.store_memory(new_memory)
        
        # Access old memory multiple times
        for _ in range(3):
            memory_store.retrieve_memories("Old", limit=5)
        
        # Should return old memory first due to higher access count
        results = memory_store.retrieve_memories("fact", limit=5)
        assert results[0].content == "Old fact"
        assert results[0].access_count >= 3  # 3 explicit loops + this retrieval call


class TestMemoryManager:
    """Test memory management and context building."""
    
    @pytest.fixture
    def memory_manager(self):
        """Initialize MemoryManager with temporary store."""
        fd, path = tempfile.mkstemp()
        os.close(fd)
        store = MemoryStore(db_path=path)
        manager = MemoryManager(store)
        yield manager
        os.unlink(path)
    
    def test_add_context(self, memory_manager):
        """Test adding context memories."""
        memory_id = memory_manager.add_context(
            "User likes concise answers",
            MemoryType.PREFERENCE,
            {"style": "concise"}
        )
        assert memory_id is not None
    
    def test_get_relevant_context(self, memory_manager):
        """Test building context from relevant memories."""
        # Add relevant memories
        memory_manager.add_context(
            "User is a software engineer",
            MemoryType.FACT,
            {"profession": "engineer"}
        )
        memory_manager.add_context(
            "User is learning Python",
            MemoryType.LEARNING,
            {"topic": "python", "level": "beginner"}
        )
        memory_manager.add_context(
            "Prefers practical examples",
            MemoryType.PREFERENCE,
            {"learning_style": "practical"}
        )
        
        # Get context - preferences always returned; learning/fact returned if content matches
        context = memory_manager.get_relevant_context("Python programming", max_context=1000)
        assert "learning Python" in context  # LEARNING type matches query
        assert "practical examples" in context  # PREFERENCE type always returned
    
    def test_context_length_limit(self, memory_manager):
        """Test context respects maximum length limit."""
        # Add many memories
        for i in range(10):
            memory_manager.add_context(
                f"Long memory entry number {i} with lots of extra text " * 20,
                MemoryType.FACT
            )
        
        # Context should be limited
        context = memory_manager.get_relevant_context("memory", max_context=500)
        assert len(context) <= 500
    
    def test_update_preferences(self, memory_manager):
        """Test updating user preferences."""
        preferences = {
            "theme": "dark",
            "language": "python",
            "notification_level": "minimal"
        }
        
        memory_manager.update_preferences(preferences)
        
        # Verify preferences were stored
        context = memory_manager.get_relevant_context("theme", max_context=1000)
        assert "theme = dark" in context
        assert "language = python" in context
    
    def test_track_learning(self, memory_manager):
        """Test tracking learning progress."""
        memory_manager.track_learning("machine learning", 0.7)
        memory_manager.track_learning("deep learning", 0.4)
        
        context = memory_manager.get_relevant_context("learning", max_context=1000)
        assert "machine learning" in context
        assert "deep learning" in context


class TestMemoryIntegration:
    """Integration tests for memory system with other components."""
    
    @pytest.mark.asyncio
    async def test_memory_with_chat_context(self):
        """Test memory integration with chat context building."""
        # This would integrate with the actual chat orchestrator
        # For now, test the context building logic
        pass
    
    def test_memory_persistence(self):
        """Test that memories persist across restarts."""
        fd, path = tempfile.mkstemp()
        os.close(fd)
        
        # Create store and add memory
        store = MemoryStore(db_path=path)
        memory = Memory(
            id=None, type=MemoryType.FACT, content="Persistent fact", metadata={}, created_at=datetime.utcnow()
        )
        memory_id = store.store_memory(memory)
        
        # Close and reopen store
        store = MemoryStore(db_path=path)
        results = store.retrieve_memories("Persistent", limit=5)
        
        assert len(results) == 1
        assert results[0].content == "Persistent fact"
        
        os.unlink(path)


# Performance Tests
class TestMemoryPerformance:
    """Performance tests for memory system."""
    
    def test_retrieval_performance(self):
        """Test memory retrieval meets <100ms requirement."""
        fd, path = tempfile.mkstemp()
        os.close(fd)
        
        store = MemoryStore(db_path=path)
        
        # Add 1000 memories
        for i in range(1000):
            memory = Memory(
                id=None,
                type=MemoryType.FACT,
                content=f"Test fact number {i}",
                metadata={"index": i},
                created_at=datetime.utcnow()
            )
            store.store_memory(memory)
        
        # Measure retrieval time
        import time
        start = time.time()
        results = store.retrieve_memories("Test", limit=10)
        end = time.time()
        
        retrieval_time = (end - start) * 1000  # Convert to ms
        assert retrieval_time < 100, f"Retrieval took {retrieval_time:.2f}ms, expected <100ms"
        assert len(results) == 10
        
        os.unlink(path)
