"""
Unit tests for Learning Feedback Loop
Based on openspec/changes/personal-assistant-enhancements/specs/learning-feedback/spec.md
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from src.learning.feedback_collector import FeedbackCollector, Feedback, FeedbackType
from src.learning.learning_engine import LearningEngine, KnowledgeTracker
from src.learning.spaced_repetition import SpacedRepetitionScheduler

class TestFeedbackCollector:
    """Test feedback collection and processing."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock feedback storage."""
        storage = Mock()
        storage.store = AsyncMock()
        storage.retrieve = AsyncMock(return_value=[])
        return storage
    
    @pytest.fixture
    def feedback_collector(self, mock_storage):
        """Initialize FeedbackCollector."""
        return FeedbackCollector(mock_storage)
    
    @pytest.mark.asyncio
    async def test_collect_explicit_feedback(self, feedback_collector, mock_storage):
        """Test collecting explicit user feedback."""
        feedback_data = {
            "message_id": "msg_123",
            "rating": "thumbs_up",
            "comment": "Helpful answer"
        }
        
        feedback = await feedback_collector.collect_feedback("explicit", feedback_data)
        
        assert isinstance(feedback, Feedback)
        assert feedback.type == "explicit"
        assert feedback.message_id == "msg_123"
        assert feedback.rating == "thumbs_up"
        assert feedback.comment == "Helpful answer"
        
        # Verify storage was called
        mock_storage.store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_implicit_feedback(self, feedback_collector, mock_storage):
        """Test collecting implicit feedback from user behavior."""
        feedback_data = {
            "message_id": "msg_456",
            "metrics": {
                "read_time": 5.2,
                "copy_count": 1,
                "follow_up": False,
                "rephrase": False
            }
        }
        
        feedback = await feedback_collector.collect_feedback("implicit", feedback_data)
        
        assert isinstance(feedback, Feedback)
        assert feedback.type == "implicit"
        assert feedback.metrics["read_time"] == 5.2
        assert feedback.metrics["copy_count"] == 1
    
    @pytest.mark.asyncio
    async def test_collect_correction_feedback(self, feedback_collector, mock_storage):
        """Test collecting user corrections."""
        feedback_data = {
            "message_id": "msg_789",
            "original_response": "Python is a compiled language",
            "corrected_response": "Python is an interpreted language",
            "explanation": "Python uses an interpreter, not a compiler"
        }
        
        feedback = await feedback_collector.collect_feedback("correction", feedback_data)
        
        assert isinstance(feedback, Feedback)
        assert feedback.type == "correction"
        assert "interpreted" in feedback.corrected_response
    
    @pytest.mark.asyncio
    async def test_feedback_processing_pipeline(self, feedback_collector):
        """Test that feedback is processed correctly."""
        # Test different processors
        processors = feedback_collector.processors
        
        assert "explicit" in processors
        assert "implicit" in processors
        assert "correction" in processors
        
        # Each processor should have process method
        for processor in processors.values():
            assert hasattr(processor, 'process')


class TestLearningEngine:
    """Test the core learning and adaptation engine."""
    
    @pytest.fixture
    def learning_config(self):
        """Create learning configuration."""
        from src.learning.config import LearningConfig
        return LearningConfig(
            adaptation_rate=0.1,
            window_size=100,
            min_samples=10
        )
    
    @pytest.fixture
    def mock_knowledge_tracker(self):
        """Create mock knowledge tracker."""
        tracker = Mock(spec=KnowledgeTracker)
        tracker.update = AsyncMock()
        tracker.identify_gaps = AsyncMock(return_value=[])
        return tracker
    
    @pytest.fixture
    def mock_strategy_optimizer(self):
        """Create mock strategy optimizer."""
        optimizer = Mock()
        optimizer.adjust = AsyncMock()
        return optimizer
    
    @pytest.fixture
    def learning_engine(self, learning_config, mock_knowledge_tracker, mock_strategy_optimizer):
        """Initialize LearningEngine."""
        engine = LearningEngine(learning_config)
        engine.knowledge_tracker = mock_knowledge_tracker
        engine.strategy_optimizer = mock_strategy_optimizer
        return engine
    
    @pytest.mark.asyncio
    async def test_process_positive_feedback(self, learning_engine, mock_knowledge_tracker):
        """Test processing positive feedback."""
        feedback = Feedback(
            type="explicit",
            message_id="msg_123",
            rating="thumbs_up",
            timestamp=datetime.utcnow()
        )
        
        await learning_engine.process_feedback(feedback)
        
        # Should update knowledge
        mock_knowledge_tracker.update.assert_called_once_with(feedback)
    
    @pytest.mark.asyncio
    async def test_process_correction_feedback(self, learning_engine):
        """Test processing correction feedback."""
        feedback = Feedback(
            type="correction",
            message_id="msg_456",
            original_response="Wrong answer",
            corrected_response="Right answer",
            timestamp=datetime.utcnow()
        )
        
        with patch.object(learning_engine, 'schedule_reinforcement') as mock_schedule:
            await learning_engine.process_feedback(feedback)
            
            # Should schedule reinforcement for corrections
            mock_schedule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_adaptation_rate_application(self, learning_engine):
        """Test that adaptation rate is applied correctly."""
        feedback = Feedback(
            type="explicit",
            message_id="msg_789",
            rating="thumbs_down",
            timestamp=datetime.utcnow()
        )
        
        # Track initial state
        initial_strategy = learning_engine.current_strategy
        
        await learning_engine.process_feedback(feedback)
        
        # Strategy should be adjusted based on feedback
        learning_engine.strategy_optimizer.adjust.assert_called_once_with(feedback)


class TestKnowledgeTracker:
    """Test knowledge tracking and gap identification."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock knowledge storage."""
        storage = Mock()
        storage.get_mastery = AsyncMock(return_value=0.5)
        storage.set_mastery = AsyncMock()
        storage.get_recent_questions = AsyncMock(return_value=[])
        return storage
    
    @pytest.fixture
    def knowledge_tracker(self, mock_storage):
        """Initialize KnowledgeTracker."""
        return KnowledgeTracker(mock_storage)
    
    @pytest.mark.asyncio
    async def test_update_mastery_positive_feedback(self, knowledge_tracker, mock_storage):
        """Test mastery update with positive feedback."""
        feedback = Feedback(
            type="explicit",
            rating="thumbs_up",
            metadata={"topic": "python"},
            timestamp=datetime.utcnow()
        )
        
        new_mastery = await knowledge_tracker.update_mastery("python", feedback)
        
        assert new_mastery > 0.5  # Should increase from 0.5
        mock_storage.set_mastery.assert_called_once_with("python", new_mastery)
    
    @pytest.mark.asyncio
    async def test_update_mastery_negative_feedback(self, knowledge_tracker, mock_storage):
        """Test mastery update with negative feedback."""
        feedback = Feedback(
            type="explicit",
            rating="thumbs_down",
            metadata={"topic": "python"},
            timestamp=datetime.utcnow()
        )
        
        new_mastery = await knowledge_tracker.update_mastery("python", feedback)
        
        assert new_mastery < 0.5  # Should decrease from 0.5
    
    @pytest.mark.asyncio
    async def test_identify_knowledge_gaps(self, knowledge_tracker, mock_storage):
        """Test identification of knowledge gaps."""
        # Mock recent questions about python
        mock_storage.get_recent_questions.return_value = [
            "How to use list comprehension in python?",
            "What is python decorator?",
            "Python class inheritance",
            "Python async/await",
            "Python generators"
        ]
        
        gaps = await knowledge_tracker.identify_gaps({})
        
        # Should identify python as a gap due to low mastery and high interest
        assert any(gap.topic == "python" for gap in gaps)
        assert all(gap.mastery < 0.5 for gap in gaps)
    
    @pytest.mark.asyncio
    async def test_mastery_bounds(self, knowledge_tracker, mock_storage):
        """Test mastery stays within 0-1 bounds."""
        # Test upper bound
        feedback = Feedback(type="explicit", rating="thumbs_up")
        mock_storage.get_mastery.return_value = 0.95
        
        mastery = await knowledge_tracker.update_mastery("topic", feedback)
        assert mastery <= 1.0
        
        # Test lower bound
        mock_storage.get_mastery.return_value = 0.05
        feedback = Feedback(type="explicit", rating="thumbs_down")
        
        mastery = await knowledge_tracker.update_mastery("topic", feedback)
        assert mastery >= 0.0


class TestSpacedRepetitionScheduler:
    """Test spaced repetition scheduling."""
    
    @pytest.fixture
    def scheduler_config(self):
        """Create scheduler configuration."""
        from src.learning.config import SRSConfig
        return SRSConfig(
            intervals=[1, 3, 7, 14, 30, 90],
            max_interval=180
        )
    
    @pytest.fixture
    def scheduler(self, scheduler_config):
        """Initialize SpacedRepetitionScheduler."""
        return SpacedRepetitionScheduler(scheduler_config)
    
    def test_schedule_next_review_high_mastery(self, scheduler):
        """Test scheduling for high mastery topics."""
        mastery = 0.9
        last_review = datetime.utcnow()
        current_interval = 2  # Currently at 7-day interval
        
        next_review = scheduler.schedule_next_review("topic", mastery, last_review)
        
        # Should increase interval for high mastery
        expected = last_review + timedelta(days=14)  # Next interval
        assert next_review.date() == expected.date()
    
    def test_schedule_next_review_low_mastery(self, scheduler):
        """Test scheduling for low mastery topics."""
        mastery = 0.3
        last_review = datetime.utcnow()
        current_interval = 2  # Currently at 7-day interval
        
        next_review = scheduler.schedule_next_review("topic", mastery, last_review)
        
        # Should decrease interval for low mastery
        expected = last_review + timedelta(days=3)  # Previous interval
        assert next_review.date() == expected.date()
    
    def test_schedule_next_review_medium_mastery(self, scheduler):
        """Test scheduling for medium mastery topics."""
        mastery = 0.7
        last_review = datetime.utcnow()
        current_interval = 2  # Currently at 7-day interval
        
        next_review = scheduler.schedule_next_review("topic", mastery, last_review)
        
        # Should maintain interval for medium mastery
        expected = last_review + timedelta(days=7)
        assert next_review.date() == expected.date()
    
    def test_max_interval_limit(self, scheduler):
        """Test that intervals don't exceed maximum."""
        mastery = 0.95
        last_review = datetime.utcnow()
        
        # Set to max interval
        scheduler._get_current_interval = lambda x: 5  # 90-day interval
        
        next_review = scheduler.schedule_next_review("topic", mastery, last_review)
        
        # Should not exceed max interval
        days_diff = (next_review - last_review).days
        assert days_diff <= 180


class TestLearningIntegration:
    """Integration tests for learning system."""
    
    @pytest.mark.asyncio
    async def test_feedback_to_learning_loop(self):
        """Test complete feedback to learning loop."""
        # Mock all components
        mock_storage = Mock()
        mock_storage.store = AsyncMock()
        mock_storage.get_mastery = AsyncMock(return_value=0.6)
        mock_storage.set_mastery = AsyncMock()
        
        # Initialize components
        feedback_collector = FeedbackCollector(mock_storage)
        knowledge_tracker = KnowledgeTracker(mock_storage)
        
        # Simulate user interaction
        feedback_data = {
            "message_id": "msg_123",
            "rating": "thumbs_up",
            "metadata": {"topic": "machine_learning"}
        }
        
        # Collect feedback
        feedback = await feedback_collector.collect_feedback("explicit", feedback_data)
        
        # Update knowledge
        new_mastery = await knowledge_tracker.update_mastery(
            "machine_learning", 
            feedback
        )
        
        assert new_mastery > 0.6
        mock_storage.set_mastery.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_learning_analytics_generation(self):
        """Test generation of learning analytics."""
        # This would test the LearningAnalytics class
        # For now, test the data flow
        
        mock_storage = Mock()
        mock_storage.get_mastery_overview = AsyncMock(return_value={
            "python": 0.8,
            "machine_learning": 0.6,
            "statistics": 0.4
        })
        mock_storage.identify_gaps = AsyncMock(return_value=[
            {"topic": "statistics", "mastery": 0.4, "urgency": "high"}
        ])
        
        # Generate analytics
        from src.learning.analytics import LearningAnalytics
        analytics = LearningAnalytics(mock_storage)
        
        report = await analytics.generate_progress_report("user_123")
        
        assert "mastery_levels" in report
        assert "knowledge_gaps" in report
        assert len(report["knowledge_gaps"]) == 1
        assert report["knowledge_gaps"][0]["topic"] == "statistics"


# Performance Tests
class TestLearningPerformance:
    """Performance tests for learning system."""
    
    @pytest.mark.asyncio
    async def test_feedback_processing_performance(self):
        """Test feedback processing meets performance requirements."""
        mock_storage = Mock()
        mock_storage.store = AsyncMock()
        
        collector = FeedbackCollector(mock_storage)
        
        # Process multiple feedbacks
        start_time = asyncio.get_event_loop().time()
        
        tasks = []
        for i in range(100):
            feedback_data = {
                "message_id": f"msg_{i}",
                "rating": "thumbs_up" if i % 2 == 0 else "thumbs_down"
            }
            tasks.append(collector.collect_feedback("explicit", feedback_data))
        
        await asyncio.gather(*tasks)
        
        end_time = asyncio.get_event_loop().time()
        processing_time = end_time - start_time
        
        # Should process 100 feedbacks quickly
        assert processing_time < 1.0, f"Processing took {processing_time:.2f}s"
        assert mock_storage.store.call_count == 100
    
    @pytest.mark.asyncio
    async def test_knowledge_update_performance(self):
        """Test knowledge tracking performance."""
        mock_storage = Mock()
        mock_storage.get_mastery = AsyncMock(return_value=0.5)
        mock_storage.set_mastery = AsyncMock()
        
        tracker = KnowledgeTracker(mock_storage)
        feedback = Feedback(type="explicit", rating="thumbs_up")
        
        # Measure update time
        start_time = asyncio.get_event_loop().time()
        
        for _ in range(1000):
            await tracker.update_mastery("topic", feedback)
        
        end_time = asyncio.get_event_loop().time()
        update_time = end_time - start_time
        
        # Should handle 1000 updates efficiently
        assert update_time < 0.5, f"Updates took {update_time:.2f}s"
