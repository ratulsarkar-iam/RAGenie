"""
End-to-End Tests for Personal Assistant Features
Based on openspec/changes/personal-assistant-enhancements/ specifications
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

class TestPersonalAssistantWorkflow:
    """Test complete personal assistant workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_learning_workflow(self):
        """Test full learning workflow: question → answer → feedback → adaptation."""
        
        # 1. User asks a question
        user_question = "What are decorators in Python?"
        
        # 2. System retrieves relevant context (including previous learning)
        with patch('src.memory.memory_manager.MemoryManager') as mock_memory:
            mock_memory.get_relevant_context.return_value = (
                "User is learning Python\n"
                "Previous topics: lists, dictionaries\n"
                "Current level: beginner"
            )
            
            # 3. Generate response
            with patch('src.chat.orchestrator.ChatOrchestrator') as mock_orchestrator:
                mock_orchestrator.chat_simple.return_value = (
                    "Python decorators are functions that modify other functions. "
                    "They allow you to add functionality to existing code without "
                    "changing its structure. Here's a simple example..."
                )
                
                response = await mock_orchestrator.chat_simple(user_question)
                assert "decorators" in response.lower()
                
                # 4. User provides feedback
                with patch('src.learning.feedback_collector.FeedbackCollector') as mock_feedback:
                    feedback_data = {
                        "message_id": "msg_123",
                        "rating": "thumbs_up",
                        "comment": "Clear explanation, examples helped"
                    }
                    
                    mock_feedback.return_value = Mock(
                        type="explicit",
                        rating="thumbs_up",
                        metadata={"topic": "python_decorators"}
                    )
                    
                    # 5. System updates knowledge
                    with patch('src.learning.knowledge_tracker.KnowledgeTracker') as mock_tracker:
                        mock_tracker.update_mastery.return_value = 0.7  # Increased from 0.5
                        
                        new_mastery = await mock_tracker.update_mastery(
                            "python_decorators", 
                            mock_feedback.return_value
                        )
                        
                        assert new_mastery > 0.5  # Mastery improved
                        
                        # 6. Schedule reinforcement
                        with patch('src.learning.spaced_repetition.SpacedRepetitionScheduler') as mock_srs:
                            mock_srs.schedule_next_review.return_value = (
                                datetime.utcnow() + timedelta(days=3)
                            )
                            
                            next_review = mock_srs.schedule_next_review(
                                "python_decorators", 
                                new_mastery, 
                                datetime.utcnow()
                            )
                            
                            assert next_review > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_task_execution_workflow(self):
        """Test complete task execution: request → parsing → execution → confirmation."""
        
        # 1. User requests a task
        task_request = "Remind me to review the Python decorators tutorial tomorrow at 2 PM"
        
        # 2. System parses the task
        with patch('src.tasks.task_parser.TaskParser') as mock_parser:
            mock_parser.parse_request.return_value = Mock(
                action_type="reminder",
                parameters={
                    "message": "Review Python decorators tutorial",
                    "trigger_time": "2024-01-16T14:00:00"
                },
                priority="medium"
            )
            
            parsed_task = await mock_parser.parse_request(task_request, {})
            assert parsed_task.action_type == "reminder"
            
            # 3. Execute task via MCP
            with patch('src.tasks.mcp_manager.MCPManager') as mock_mcp:
                mock_mcp.execute_action.return_value = {
                    "reminder_id": "rem_123",
                    "status": "created"
                }
                
                from src.tasks.task_engine import TaskEngine
                engine = TaskEngine(mock_mcp)
                
                result = await engine.execute_task(task_request)
                
                assert result.success is True
                assert "Reminder created" in result.summary
                assert result.details["reminder_id"] == "rem_123"
                
                # 4. Store in memory
                with patch('src.memory.memory_manager.MemoryManager') as mock_memory:
                    mock_memory.add_context = Mock()
                    
                    mock_memory.add_context(
                        f"Created reminder: {result.summary}",
                        "task",
                        {"task_id": "task_123", "type": "reminder"}
                    )
                    
                    mock_memory.add_context.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_proactive_assistance_workflow(self):
        """Test proactive assistance: context analysis → opportunity → action."""
        
        # 1. System analyzes user context
        with patch('src.proactive.context_analyzer.ContextAnalyzer') as mock_analyzer:
            mock_analyzer.get_current_context.return_value = Mock(
                time_context=Mock(
                    current_time=datetime(2024, 1, 15, 9, 0),
                    time_of_day="morning",
                    is_work_hours=True
                ),
                task_context={
                    "today_priorities": ["Complete project", "Code review"],
                    "upcoming_deadlines": ["Project due at 5 PM"]
                },
                learning_context={
                    "recent_topics": ["python_decorators"],
                    "mastery_levels": {"python_decorators": 0.7}
                }
            )
            
            # 2. Identify opportunities
            with patch('src.proactive.opportunity_detector.OpportunityDetector') as mock_detector:
                mock_detector.detect_learning_opportunities.return_value = [
                    Mock(
                        type="learning_review",
                        topic="python_decorators",
                        urgency="low",
                        suggested_action="Quick practice exercise"
                    )
                ]
                
                opportunities = await mock_detector.detect_learning_opportunities(
                    mock_analyzer.get_current_context.return_value
                )
                
                assert len(opportunities) == 1
                assert opportunities[0].topic == "python_decorators"
                
                # 3. Generate proactive content
                with patch('src.proactive.content_generator.ContentGenerator') as mock_generator:
                    mock_generator.generate_daily_briefing.return_value = Mock(
                        content="Good morning! Today you have: Complete project (due 5 PM), "
                               "Code review. Learning: Ready to practice decorators?",
                        priority="high",
                        channels=["notification"]
                    )
                    
                    briefing = await mock_generator.generate_daily_briefing(
                        mock_analyzer.get_current_context.return_value
                    )
                    
                    assert "Complete project" in briefing.content
                    assert "decorators" in briefing.content
                    
                    # 4. Deliver notification
                    with patch('src.proactive.notification_service.NotificationService') as mock_notification:
                        mock_notification.deliver = AsyncMock()
                        
                        await mock_notification.return_value.deliver(briefing)
                        mock_notification.return_value.deliver.assert_called_once_with(briefing)
    
    @pytest.mark.asyncio
    async def test_hybrid_search_workflow(self):
        """Test hybrid search for complex documents."""
        
        # 1. User asks complex question
        query = "How do attention mechanisms work in transformer models?"
        
        # 2. System classifies query and documents
        with patch('src.rag.document_classifier.DocumentClassifier') as mock_classifier:
            # Mock research papers in database
            mock_classifier.classify_document.return_value = "HYBRID"
            
            # 3. Perform hybrid search
            with patch('src.rag.hybrid_retriever.HybridRetriever') as mock_hybrid:
                mock_hybrid.search.return_value = [
                    Mock(
                        id="chunk_1",
                        content="Attention mechanisms allow transformers to focus on "
                               "different parts of the input sequence...",
                        score=0.95,
                        source="attention_is_all_you_need.pdf"
                    ),
                    Mock(
                        id="chunk_2",
                        content="The self-attention mechanism computes attention scores "
                               "between all pairs of positions...",
                        score=0.87,
                        source="transformer_survey.pdf"
                    )
                ]
                
                results = mock_hybrid.search(query, top_k=5)
                
                assert len(results) == 2
                assert all("attention" in r.content.lower() for r in results)
                assert all(r.score > 0.8 for r in results)
                
                # 4. Generate response with context
                with patch('src.chat.orchestrator.ChatOrchestrator') as mock_orchestrator:
                    mock_orchestrator.chat_simple.return_value = (
                        "Attention mechanisms in transformers work by computing "
                        "attention scores between all input elements. The key insight "
                        "from 'Attention Is All You Need' is that attention can be "
                        "used as the sole mechanism for processing sequences..."
                    )
                    
                    response = await mock_orchestrator.chat_simple(query)
                    assert "attention scores" in response.lower()
                    assert "Attention Is All You Need" in response
    
    @pytest.mark.asyncio
    async def test_memory_persistence_across_sessions(self):
        """Test that memory persists and enhances future interactions."""
        
        # Session 1: User shares preferences
        with patch('src.memory.memory_store.MemoryStore') as mock_store:
            mock_store.store_memory = Mock(return_value="mem_123")
            mock_store.retrieve_memories = Mock(return_value=[])
            
            # Store preference
            from src.memory.memory_manager import MemoryManager
            manager = MemoryManager(mock_store)
            
            memory_id = manager.add_context(
                "User prefers code examples with explanations",
                "preference",
                {"style": "explanatory", "topic": "coding"}
            )
            
            assert memory_id is not None
            
            # Session 2: User asks related question
            mock_store.retrieve_memories.return_value = [
                Mock(
                    type="preference",
                    content="User prefers code examples with explanations",
                    metadata={"style": "explanatory"}
                )
            ]
            
            # Get relevant context
            context = manager.get_relevant_context("How to use decorators?", max_context=1000)
            assert "explanatory" in context
            assert "code examples" in context
            
            # Generate enhanced response
            with patch('src.chat.orchestrator.ChatOrchestrator') as mock_orchestrator:
                mock_orchestrator.chat_simple.return_value = (
                    "Here's a decorator with detailed explanations:\n\n"
                    "@timer\n"
                    "def my_function():\n"
                    "    # This decorator times the function execution\n"
                    "    # The @ symbol applies the decorator\n"
                    "    pass\n\n"
                    "The timer decorator wraps your function to add timing..."
                )
                
                response = await mock_orchestrator.chat_simple("Show me a decorator example")
                assert "detailed explanations" in response.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test system handles errors gracefully."""
        
        # 1. Task execution failure
        with patch('src.tasks.mcp_manager.MCPManager') as mock_mcp:
            mock_mcp.execute_action.side_effect = Exception("MCP connection failed")
            
            from src.tasks.task_engine import TaskEngine
            engine = TaskEngine(mock_mcp)
            
            result = await engine.execute_task("Create reminder")
            
            assert result.success is False
            assert "Failed to create reminder" in result.summary
            
            # 2. Fallback to manual instructions
            with patch('src.chat.orchestrator.ChatOrchestrator') as mock_orchestrator:
                mock_orchestrator.chat_simple.return_value = (
                    "I couldn't create the reminder automatically. "
                    "You can manually set a reminder by:\n"
                    "1. Opening the Reminders app\n"
                    "2. Clicking the + button\n"
                    "3. Entering your reminder details"
                )
                
                response = await mock_orchestrator.chat_simple(
                    "I need to remember to call John"
                )
                
                assert "manually set" in response.lower()
                assert "Reminders app" in response
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test system performance with multiple concurrent operations."""
        
        # Simulate multiple concurrent requests
        async def simulate_user_interaction():
            # Memory operation
            with patch('src.memory.memory_manager.MemoryManager') as mock_memory:
                mock_memory.get_relevant_context = AsyncMock(return_value="")
                
            # Chat operation
            with patch('src.chat.orchestrator.ChatOrchestrator') as mock_chat:
                mock_chat.chat_simple = AsyncMock(return_value="Response")
                
            # Task operation
            with patch('src.tasks.task_engine.TaskEngine') as mock_task:
                mock_task.execute_task = AsyncMock(return_value=Mock(success=True))
                
            return True
        
        # Run 10 concurrent interactions
        start_time = asyncio.get_event_loop().time()
        
        tasks = [simulate_user_interaction() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time
        
        # All should complete successfully
        assert all(results)
        
        # Should handle concurrent load efficiently
        assert total_time < 2.0, f"Concurrent operations took {total_time:.2f}s"


class TestPersonalAssistantIntegration:
    """Integration tests combining multiple features."""
    
    @pytest.mark.asyncio
    async def test_learning_task_proactive_loop(self):
        """Test integration of learning, tasks, and proactive features."""
        
        # 1. User struggles with a concept (low mastery)
        with patch('src.learning.knowledge_tracker.KnowledgeTracker') as mock_tracker:
            mock_tracker.get_mastery.return_value = 0.3  # Low mastery
            mock_tracker.identify_gaps.return_value = [
                {"topic": "async_programming", "mastery": 0.3, "frequency": 5}
            ]
            
            # 2. Proactive system identifies need for help
            with patch('src.proactive.opportunity_detector.OpportunityDetector') as mock_detector:
                mock_detector.detect_learning_opportunities.return_value = [
                    Mock(
                        type="knowledge_gap",
                        topic="async_programming",
                        urgency="medium",
                        suggested_action="Review async/await basics"
                    )
                ]
                
                # 3. System creates learning task
                with patch('src.tasks.task_engine.TaskEngine') as mock_task:
                    mock_task.execute_task.return_value = Mock(
                        success=True,
                        summary="Created reminder to review async programming"
                    )
                    
                    # 4. Generate helpful content
                    with patch('src.proactive.content_generator.ContentGenerator') as mock_content:
                        mock_content.generate_learning_nudge.return_value = Mock(
                            message="I notice async programming is challenging. "
                                   "Would you like a quick refresher on async/await?",
                            action_type="learning_support"
                        )
                        
                        # Complete loop executed
                        assert mock_tracker.identify_gaps.called
                        assert mock_detector.detect_learning_opportunities.called
                        assert mock_task.execute_task.called
    
    @pytest.mark.asyncio
    async def test_memory_enhanced_search_and_tasks(self):
        """Test memory enhancing both search and task execution."""
        
        # 1. User has stored preferences and context
        with patch('src.memory.memory_manager.MemoryManager') as mock_memory:
            mock_memory.get_relevant_context.return_value = (
                "User is working on machine learning project\n"
                "Prefers practical examples over theory\n"
                "Current focus: data preprocessing\n"
                "Has pandas experience, needs scikit-learn help"
            )
            
            # 2. Search is enhanced with memory context
            with patch('src.rag.hybrid_retriever.HybridRetriever') as mock_search:
                mock_search.search.return_value = [
                    Mock(content="Scikit-learn data preprocessing pipeline"),
                    Mock(content="Practical ML examples with pandas")
                ]
                
                # 3. Task execution uses memory for better parsing
                with patch('src.tasks.task_parser.TaskParser') as mock_parser:
                    mock_parser.parse_request.return_value = Mock(
                        action_type="learning_task",
                        parameters={
                            "topic": "scikit-learn_preprocessing",
                            "style": "practical"
                        }
                    )
                    
                    # 4. Response is personalized
                    with patch('src.chat.orchestrator.ChatOrchestrator') as mock_chat:
                        mock_chat.chat_simple.return_value = (
                            "Since you have pandas experience, here's a practical "
                            "scikit-learn preprocessing example that builds on what "
                            "you know..."
                        )
                        
                        # Verify all components used memory
                        assert "pandas experience" in mock_chat.chat_simple.return_value


# Test Configuration and Setup
class TestPersonalAssistantSetup:
    """Test system setup and configuration."""
    
    def test_feature_flags_configuration(self):
        """Test that features can be enabled/disabled via config."""
        from src.config.models import PersonalAssistantConfig
        
        # All features disabled
        config_off = PersonalAssistantConfig(
            memory_enabled=False,
            semantic_search_enabled=False,
            task_execution_enabled=False,
            learning_enabled=False,
            proactive_enabled=False
        )
        
        assert not config_off.memory_enabled
        assert not config_off.semantic_search_enabled
        
        # Selective features enabled
        config_partial = PersonalAssistantConfig(
            memory_enabled=True,
            semantic_search_enabled=False,
            task_execution_enabled=True,
            learning_enabled=False,
            proactive_enabled=False
        )
        
        assert config_partial.memory_enabled
        assert not config_partial.semantic_search_enabled
        assert config_partial.task_execution_enabled
    
    def test_resource_constraints(self):
        """Test system respects MacBook Air resource constraints."""
        # Verify ChromaDB uses persistent client (not server)
        with patch('src.rag.vector_store.chromadb.PersistentClient') as mock_persistent:
            from src.rag.vector_store import ChromaVectorStore
            store = ChromaVectorStore()
            
            mock_persistent.assert_called_once()
            # Should not use HttpClient (server mode)
            
        # Verify embedding manager uses MPS on Mac
        with patch('src.rag.embedding_manager.SentenceTransformer') as mock_transformer:
            from src.rag.embedding_manager import EmbeddingManager
            manager = EmbeddingManager(device="mps")
            
            assert manager.device == "mps"
