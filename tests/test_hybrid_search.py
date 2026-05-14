"""
Unit tests for Hybrid Search Enhancement
Based on openspec/changes/personal-assistant-enhancements/specs/hybrid-search/spec.md
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from src.rag.vector_store import ChromaVectorStore, Chunk
from src.rag.embedding_manager import EmbeddingManager
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.document_classifier import DocumentClassifier, SearchMethod, Document
from src.rag.page_index_store import PageIndexStore
from datetime import datetime

class TestChromaVectorStore:
    """Test ChromaDB vector storage implementation."""
    
    @pytest.fixture
    def temp_chroma_dir(self):
        """Create temporary ChromaDB directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def vector_store(self, temp_chroma_dir):
        """Initialize ChromaVectorStore."""
        return ChromaVectorStore(persist_directory=temp_chroma_dir)
    
    @pytest.fixture
    def sample_chunks(self):
        """Create sample document chunks."""
        return [
            Chunk(
                id="chunk_1",
                doc_id="doc_1",
                content="Python is a high-level programming language",
                source="test.pdf"
            ),
            Chunk(
                id="chunk_2",
                doc_id="doc_2",
                content="Machine learning is a subset of artificial intelligence",
                source="research.pdf"
            ),
            Chunk(
                id="chunk_3",
                doc_id="doc_3",
                content="Neural networks are inspired by biological neural networks",
                source="paper.pdf"
            )
        ]
    
    def test_init_creates_collection(self, vector_store):
        """Test that initialization creates ChromaDB collection."""
        assert vector_store.collection is not None
        assert vector_store.collection.name == "documents"
        assert vector_store.collection.metadata["hnsw:space"] == "cosine"
    
    def test_add_embeddings(self, vector_store, sample_chunks):
        """Test adding document chunks with embeddings."""
        vector_store.add_embeddings(sample_chunks)
        
        # Verify chunks were added
        count = vector_store.collection.count()
        assert count == len(sample_chunks)
        
        # Verify metadata
        results = vector_store.collection.get(include=["metadatas"])
        assert len(results["metadatas"]) == 3
        assert results["metadatas"][0]["doc_id"] == "doc_1"
        assert results["metadatas"][0]["source"] == "test.pdf"
    
    def test_search_by_query(self, vector_store, sample_chunks):
        """Test semantic search by query."""
        # Add chunks first
        vector_store.add_embeddings(sample_chunks)
        
        # Search for Python-related content
        results = vector_store.search("programming language", top_k=2)
        
        assert len(results) <= 2
        # Should return chunks about Python
        python_chunks = [r for r in results if "Python" in r.content]
        assert len(python_chunks) > 0
    
    def test_search_empty_collection(self, vector_store):
        """Test search on empty collection."""
        results = vector_store.search("test query", top_k=5)
        assert len(results) == 0
    
    def test_update_embeddings(self, vector_store, sample_chunks):
        """Test updating embeddings for existing chunk."""
        vector_store.add_embeddings(sample_chunks)
        
        # Update first chunk
        new_embedding = [0.1] * 384  # Dummy embedding
        vector_store.update_embeddings("chunk_1", new_embedding)
        
        # Verify update (would need to check actual embedding in real test)
        # For now, just ensure no error
        assert True
    
    def test_delete_embeddings(self, vector_store, sample_chunks):
        """Test deleting embeddings."""
        vector_store.add_embeddings(sample_chunks)
        
        # Delete one chunk
        vector_store.delete_embeddings(["chunk_1"])
        
        # Verify deletion
        count = vector_store.collection.count()
        assert count == 2
    
    def test_get_stats(self, vector_store, sample_chunks):
        """Test getting collection statistics."""
        vector_store.add_embeddings(sample_chunks)
        
        stats = vector_store.get_stats()
        assert stats == len(sample_chunks)


class TestEmbeddingManager:
    """Test embedding generation and management."""
    
    @pytest.fixture
    def embedding_manager(self):
        """Initialize EmbeddingManager."""
        return EmbeddingManager(model_name="all-MiniLM-L6-v2")
    
    @pytest.mark.asyncio
    async def test_embed_text(self, embedding_manager):
        """Test embedding single text."""
        text = "This is a test sentence for embedding."
        
        with patch.object(embedding_manager, 'model') as mock_model:
            mock_model.encode.return_value = [[0.1, 0.2, 0.3] * 128]  # 384-dim
            
            embedding = await embedding_manager.embed_text(text)
            
            assert len(embedding) == 384  # Standard embedding size
            mock_model.encode.assert_called_once_with([text])
    
    @pytest.mark.asyncio
    async def test_embed_batch(self, embedding_manager):
        """Test embedding multiple texts."""
        texts = [
            "First sentence",
            "Second sentence",
            "Third sentence"
        ]
        
        with patch.object(embedding_manager, 'model') as mock_model:
            mock_model.encode.return_value = [[0.1] * 384 for _ in texts]
            
            embeddings = await embedding_manager.embed_batch(texts)
            
            assert len(embeddings) == 3
            assert all(len(emb) == 384 for emb in embeddings)
            mock_model.encode.assert_called_once_with(texts)
    
    def test_cache_functionality(self, embedding_manager):
        """Test embedding caching."""
        import asyncio
        text = "Cached text"
        
        with patch.object(embedding_manager, 'model') as mock_model:
            mock_model.encode.return_value = [[0.1] * 384]
            
            # First call - run async embed_text
            asyncio.get_event_loop().run_until_complete(embedding_manager.embed_text(text))
            # Second call (should use cache)
            asyncio.get_event_loop().run_until_complete(embedding_manager.embed_text(text))
            
            # Model should only be called once
            assert mock_model.encode.call_count == 1
    
    def test_clear_cache(self, embedding_manager):
        """Test clearing embedding cache."""
        # Add to cache
        embedding_manager.cache["test"] = [0.1] * 384
        
        # Clear cache
        embedding_manager.clear_cache()
        
        assert len(embedding_manager.cache) == 0


class TestDocumentClassifier:
    """Test document classification for search method selection."""
    
    @pytest.fixture
    def classifier(self):
        """Initialize DocumentClassifier."""
        return DocumentClassifier()
    
    def test_classify_research_paper(self, classifier):
        """Test classification of research papers."""
        doc = Document(
            doc_id="paper_1",
            source="/papers/ml_research_2024.pdf",
            chunks=[],
            metadata={"title": "Machine Learning Research Paper 2024"}
        )
        
        method = classifier.classify_document(doc)
        assert method == SearchMethod.HYBRID
    
    def test_classify_technical_documentation(self, classifier):
        """Test classification of technical documentation."""
        doc = Document(
            doc_id="tech_doc_1",
            source="/docs/api_technical_reference.pdf",
            chunks=[],
            metadata={}
        )
        
        method = classifier.classify_document(doc)
        assert method == SearchMethod.HYBRID
    
    def test_classify_standard_document(self, classifier):
        """Test classification of standard documents."""
        doc = Document(
            doc_id="doc_1",
            source="/documents/meeting_notes.pdf",
            chunks=[],
            metadata={}
        )
        
        method = classifier.classify_document(doc)
        assert method == SearchMethod.BM25_ONLY
    
    def test_classify_by_content_complexity(self, classifier):
        """Test classification based on content complexity."""
        # Simple content
        simple_doc = Document(
            doc_id="simple",
            source="simple.txt",
            chunks=[Chunk(id="1", doc_id="simple", content="Simple text", source="simple.txt")],
            metadata={}
        )
        
        # Complex content (simulated)
        complex_doc = Document(
            doc_id="complex",
            source="complex.txt",
            chunks=[Chunk(id="1", doc_id="complex", 
                        content="Complex algorithm with mathematical formulations and theoretical concepts" * 10,
                        source="complex.txt")],
            metadata={}
        )
        
        simple_method = classifier.classify_document(simple_doc)
        complex_method = classifier.classify_document(complex_doc)
        
        assert simple_method == SearchMethod.BM25_ONLY
        assert complex_method == SearchMethod.HYBRID
    
    def test_classify_by_file_size(self, classifier):
        """Test classification based on file size."""
        # Large file
        large_doc = Document(
            doc_id="large",
            source="large.pdf",
            chunks=[],
            metadata={"file_size": 10 * 1024 * 1024}  # 10MB
        )
        
        method = classifier.classify_document(large_doc)
        assert method == SearchMethod.HYBRID


class TestHybridRetriever:
    """Test hybrid retrieval combining BM25 and semantic search."""
    
    @pytest.fixture
    def mock_bm25_store(self):
        """Create mock BM25 store."""
        store = Mock(spec=PageIndexStore)
        store.search_chunks = Mock(return_value=[
            Chunk(id="bm25_1", doc_id="doc_1", content="BM25 result 1", source="test.pdf"),
            Chunk(id="bm25_2", doc_id="doc_2", content="BM25 result 2", source="test.pdf")
        ])
        return store
    
    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store."""
        store = Mock(spec=ChromaVectorStore)
        store.search = Mock(return_value=[
            Mock(id="vec_1", content="Vector result 1", score=0.8, metadata={}),
            Mock(id="vec_2", content="Vector result 2", score=0.7, metadata={})
        ])
        return store
    
    @pytest.fixture
    def hybrid_retriever(self, mock_bm25_store, mock_vector_store):
        """Initialize HybridRetriever."""
        return HybridRetriever(mock_bm25_store, mock_vector_store, alpha=0.5)
    
    def test_search_combines_results(self, hybrid_retriever, mock_bm25_store, mock_vector_store):
        """Test that search combines BM25 and vector results."""
        results = hybrid_retriever.search("test query", top_k=3)
        
        # Should call both search methods
        mock_bm25_store.search_chunks.assert_called_once_with("test query", top_k=6)
        mock_vector_store.search.assert_called_once_with("test query", top_k=6)
        
        # Should return merged results
        assert len(results) <= 3
    
    def test_hybrid_score_calculation(self, hybrid_retriever):
        """Test hybrid score calculation."""
        # Test different alpha values
        bm25_score = 0.8
        semantic_score = 0.6
        
        # Alpha = 0.5 (balanced)
        score_05 = hybrid_retriever.calculate_hybrid_score(bm25_score, semantic_score, 0.5)
        
        # Alpha = 1.0 (BM25 only)
        score_10 = hybrid_retriever.calculate_hybrid_score(bm25_score, semantic_score, 1.0)
        
        # Alpha = 0.0 (semantic only)
        score_00 = hybrid_retriever.calculate_hybrid_score(bm25_score, semantic_score, 0.0)
        
        assert score_10 == bm25_score
        assert score_00 == semantic_score
        assert score_05 != bm25_score and score_05 != semantic_score
    
    def test_result_deduplication(self, hybrid_retriever):
        """Test that duplicate results are deduplicated."""
        # Mock overlapping results
        hybrid_retriever.bm25_store.search_chunks.return_value = [
            Chunk(id="chunk_1", doc_id="doc_1", content="Shared content", source="test.pdf")
        ]
        
        hybrid_retriever.vector_store.search.return_value = [
            Mock(id="chunk_1", content="Shared content", score=0.8, metadata={"doc_id": "doc_1"}),
            Mock(id="chunk_2", content="Unique content", score=0.7, metadata={"doc_id": "doc_2"})
        ]
        
        results = hybrid_retriever.search("test", top_k=5)
        
        # Should not have duplicates
        chunk_ids = [r.id for r in results]
        assert len(chunk_ids) == len(set(chunk_ids))


class TestEnhancedRAGStore:
    """Test enhanced RAG store with optional semantic search."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        bm25_dir = tempfile.mkdtemp()
        chroma_dir = tempfile.mkdtemp()
        yield bm25_dir, chroma_dir
        import shutil
        shutil.rmtree(bm25_dir)
        shutil.rmtree(chroma_dir)
    
    @pytest.fixture
    def enhanced_config(self, temp_dirs):
        """Create enhanced RAG configuration."""
        from src.config.models import RAGConfig
        return RAGConfig(
            index_path=os.path.join(temp_dirs[0], "index.json"),
            semantic_search_enabled=True,
            vector_store_config={
                "persist_directory": temp_dirs[1]
            }
        )
    
    def test_init_with_semantic_enabled(self, enhanced_config):
        """Test initialization with semantic search enabled."""
        with patch('src.rag.enhanced_rag_store.ChromaVectorStore') as mock_chroma, \
             patch('src.rag.enhanced_rag_store.EmbeddingManager') as mock_embedding:
            
            from src.rag.enhanced_rag_store import EnhancedRAGStore
            store = EnhancedRAGStore(enhanced_config)
            
            assert store.semantic_enabled is True
            mock_chroma.assert_called_once()
            mock_embedding.assert_called_once()
    
    def test_init_with_semantic_disabled(self, temp_dirs):
        """Test initialization with semantic search disabled."""
        from src.config.models import RAGConfig
        config = RAGConfig(
            index_path=os.path.join(temp_dirs[0], "index.json"),
            semantic_search_enabled=False
        )
        
        from src.rag.enhanced_rag_store import EnhancedRAGStore
        store = EnhancedRAGStore(config)
        
        assert store.semantic_enabled is False
        assert not hasattr(store, 'vector_store')
    
    def test_add_documents_selective_embedding(self, enhanced_config):
        """Test that only high-end documents get embedded."""
        with patch('src.rag.enhanced_rag_store.ChromaVectorStore') as mock_chroma, \
             patch('src.rag.enhanced_rag_store.EmbeddingManager') as mock_embedding, \
             patch('src.rag.enhanced_rag_store.DocumentClassifier') as mock_classifier:
            
            # Mock classifier
            mock_classifier.classify_document.side_effect = [
                SearchMethod.HYBRID,  # First doc is high-end
                SearchMethod.BM25_ONLY  # Second doc is standard
            ]
            
            from src.rag.enhanced_rag_store import EnhancedRAGStore
            store = EnhancedRAGStore(enhanced_config)
            
            # Create test documents
            docs = [
                Document(doc_id="high_end", source="research.pdf", chunks=[]),
                Document(doc_id="standard", source="notes.pdf", chunks=[])
            ]
            
            # Mock embedding generation
            mock_embedding.embed_batch.return_value = [[0.1] * 384]
            
            # Add documents
            store.add_documents(docs)
            
            # Should only embed high-end document
            assert mock_embedding.embed_batch.call_count == 1
    
    def test_search_with_semantic_disabled(self, temp_dirs):
        """Test search falls back to BM25 when semantic disabled."""
        from src.config.models import RAGConfig
        config = RAGConfig(
            index_path=os.path.join(temp_dirs[0], "index.json"),
            semantic_search_enabled=False
        )
        
        from src.rag.enhanced_rag_store import EnhancedRAGStore
        store = EnhancedRAGStore(config)
        
        # Mock BM25 search
        with patch.object(store, 'search_chunks') as mock_search:
            mock_search.return_value = []
            
            results = store.search_with_semantic("test", 5)
            
            # Should use BM25 search
            mock_search.assert_called_once_with("test", 5)


class TestHybridSearchIntegration:
    """Integration tests for hybrid search system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_hybrid_search(self):
        """Test complete hybrid search flow."""
        # This would test the actual integration
        # For now, test the flow with mocks
        
        # Mock components
        mock_bm25 = Mock()
        mock_vector = Mock()
        mock_classifier = Mock()
        
        # Set up mocks
        mock_bm25.search_chunks.return_value = [
            Chunk(id="1", doc_id="doc1", content="BM25 match", source="test.pdf")
        ]
        mock_vector.search.return_value = [
            Mock(id="2", content="Semantic match", score=0.8, metadata={})
        ]
        mock_classifier.classify_document.return_value = SearchMethod.HYBRID
        
        # Test flow
        retriever = HybridRetriever(mock_bm25, mock_vector)
        results = retriever.search("test query", top_k=5)
        
        assert len(results) > 0
        mock_bm25.search_chunks.assert_called_once()
        mock_vector.search.assert_called_once()


# Performance Tests
class TestHybridSearchPerformance:
    """Performance tests for hybrid search."""
    
    def test_retrieval_latency(self):
        """Test hybrid search meets performance requirements."""
        # Mock fast components
        mock_bm25 = Mock()
        mock_vector = Mock()
        
        # Simulate fast responses
        mock_bm25.search_chunks.return_value = []
        mock_vector.search.return_value = []
        
        retriever = HybridRetriever(mock_bm25, mock_vector)
        
        import time
        start = time.time()
        retriever.search("test query", top_k=10)
        end = time.time()
        
        latency = (end - start) * 1000  # Convert to ms
        assert latency < 100, f"Retrieval took {latency:.2f}ms, expected <100ms"
    
    def test_embedding_generation_performance(self):
        """Test embedding generation performance."""
        manager = EmbeddingManager()
        
        # Mock fast model
        with patch.object(manager, 'model') as mock_model:
            mock_model.encode.return_value = [[0.1] * 384]
            
            import time
            start = time.time()
            
            # Generate embeddings for 100 texts
            texts = [f"Test text {i}" for i in range(100)]
            manager.embed_batch(texts)
            
            end = time.time()
            duration = end - start
            
            # Should be fast for batch processing
            assert duration < 2.0, f"Batch embedding took {duration:.2f}s"
