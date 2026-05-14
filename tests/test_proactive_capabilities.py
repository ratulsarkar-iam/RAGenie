"""
Unit tests for Proactive Capabilities
Based on openspec/changes/personal-assistant-enhancements/specs/proactive-capabilities/spec.md
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from src.proactive.proactive_engine import ProactiveEngine, UserContext, TimeContext
from src.proactive.context_analyzer import ContextAnalyzer
from src.proactive.content_generator import ContentGenerator, Briefing, Nudge
from src.proactive.notification_service import NotificationService

class TestProactiveEngine:
    """Test the core proactive engine."""
    
    @pytest.fixture
    def mock_context_analyzer(self):
        """Create mock context analyzer."""
        analyzer = Mock(spec=ContextAnalyzer)
        analyzer.get_current_context = AsyncMock(return_value=UserContext(
            time_context=TimeContext(
                current_time=datetime(2024, 1, 15, 9, 0),
                time_of_day="morning",
                day_of_week=0,
                is_weekend=False,
                is_work_hours=True
            )
        ))
        return analyzer
    
    @pytest.fixture
    def mock_trigger_manager(self):
        """Create mock trigger manager."""
        manager = Mock()
        manager.identify_triggers = AsyncMock(return_value=[])
        return manager
    
    @pytest.fixture
    def mock_content_generator(self):
        """Create mock content generator."""
        generator = Mock(spec=ContentGenerator)
        generator.generate_daily_briefing = AsyncMock(return_value=Briefing(
            content="Good morning! Today's priorities...",
            priority="high",
            delivery_time="09:00",
            channels=["notification"]
        ))
        return generator
    
    @pytest.fixture
    def mock_notification_service(self):
        """Create mock notification service."""
        service = Mock(spec=NotificationService)
        service.deliver = AsyncMock()
        return service
    
    @pytest.fixture
    def proactive_engine(self, mock_context_analyzer, mock_trigger_manager, 
                         mock_content_generator, mock_notification_service):
        """Initialize ProactiveEngine."""
        return ProactiveEngine(
            context_analyzer=mock_context_analyzer,
            trigger_manager=mock_trigger_manager,
            content_generator=mock_content_generator,
            notification_service=mock_notification_service
        )
    
    @pytest.mark.asyncio
    async def test_run_proactive_cycle_morning_briefing(self, proactive_engine, 
                                                        mock_context_analyzer,
                                                        mock_content_generator,
                                                        mock_notification_service):
        """Test proactive cycle generates morning briefing."""
        # Set up morning context
        mock_context_analyzer.get_current_context.return_value = UserContext(
            time_context=TimeContext(
                current_time=datetime(2024, 1, 15, 9, 0),
                time_of_day="morning",
                day_of_week=0,
                is_weekend=False,
                is_work_hours=True
            )
        )
        
        await proactive_engine.run_proactive_cycle()
        
        # Should analyze context
        mock_context_analyzer.get_current_context.assert_called_once()
        
        # Should generate and deliver briefing
        mock_content_generator.generate_daily_briefing.assert_called_once()
        mock_notification_service.deliver.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_proactive_cycle_with_learning_nudge(self, proactive_engine,
                                                       mock_trigger_manager,
                                                       mock_content_generator):
        """Test proactive cycle with learning nudge."""
        # Set up learning trigger
        mock_trigger = Mock()
        mock_trigger.type = "learning_review"
        mock_trigger.topic = "python"
        mock_trigger.urgency = "medium"
        mock_trigger_manager.identify_triggers.return_value = [mock_trigger]
        
        # Mock nudge generation
        mock_content_generator.generate_learning_nudge = AsyncMock(return_value=Nudge(
            message="Quick review: Python?",
            topic="python",
            action_type="review",
            urgency="low"
        ))
        
        await proactive_engine.run_proactive_cycle()
        
        # Should generate learning nudge
        mock_content_generator.generate_learning_nudge.assert_called_once_with(
            "python", 0.5  # Default mastery
        )
    
    @pytest.mark.asyncio
    async def test_should_deliver_time_appropriate(self, proactive_engine):
        """Test delivery decision based on time appropriateness."""
        context = UserContext(
            time_context=TimeContext(
                current_time=datetime(2024, 1, 15, 23, 0),  # 11 PM
                time_of_day="night",
                is_quiet_hours=True
            )
        )
        
        opportunity = Mock()
        opportunity.priority = "low"
        
        # Should not deliver low priority during quiet hours
        should_deliver = await proactive_engine.should_deliver(opportunity, context)
        assert should_deliver is False
        
        # Should deliver urgent during quiet hours
        opportunity.priority = "urgent"
        should_deliver = await proactive_engine.should_deliver(opportunity, context)
        assert should_deliver is True


class TestContextAnalyzer:
    """Test user context analysis."""
    
    @pytest.fixture
    def mock_memory_store(self):
        """Create mock memory store."""
        store = Mock()
        store.get_recent_activities = AsyncMock(return_value=[
            {"type": "task", "content": "Working on project"},
            {"type": "learning", "content": "Studying Python"}
        ])
        return store
    
    @pytest.fixture
    def mock_task_engine(self):
        """Create mock task engine."""
        engine = Mock()
        engine.get_current_tasks = AsyncMock(return_value=[
            {"title": "Complete project", "deadline": "2024-01-16"},
            {"title": "Review code", "deadline": "2024-01-15"}
        ])
        return engine
    
    @pytest.fixture
    def context_analyzer(self, mock_memory_store, mock_task_engine):
        """Initialize ContextAnalyzer."""
        return ContextAnalyzer(mock_memory_store, mock_task_engine)
    
    @pytest.mark.asyncio
    async def test_get_time_context(self, context_analyzer):
        """Test time context analysis."""
        now = datetime(2024, 1, 15, 14, 30)  # Monday 2:30 PM
        
        time_context = await context_analyzer.get_time_context(now)
        
        assert time_context.current_time == now
        assert time_context.time_of_day == "afternoon"
        assert time_context.day_of_week == 0  # Monday
        assert time_context.is_weekend is False
        assert time_context.is_work_hours is True
    
    @pytest.mark.asyncio
    async def test_get_task_context(self, context_analyzer, mock_task_engine):
        """Test task context analysis."""
        task_context = await context_analyzer.get_task_context()
        
        assert "current_task" in task_context
        assert "upcoming_deadlines" in task_context
        assert len(task_context["upcoming_deadlines"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_learning_context(self, context_analyzer, mock_memory_store):
        """Test learning context analysis."""
        learning_context = await context_analyzer.get_learning_context()
        
        assert "recent_topics" in learning_context
        assert "current_focus" in learning_context
        assert "python" in learning_context["recent_topics"]
    
    @pytest.mark.asyncio
    async def test_get_comprehensive_context(self, context_analyzer):
        """Test building comprehensive user context."""
        context = await context_analyzer.get_current_context()
        
        assert isinstance(context, UserContext)
        assert context.time_context is not None
        assert context.task_context is not None
        assert context.learning_context is not None


class TestContentGenerator:
    """Test proactive content generation."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = Mock()
        llm.generate = AsyncMock(return_value="Generated briefing content")
        return llm
    
    @pytest.fixture
    def content_generator(self, mock_llm):
        """Initialize ContentGenerator."""
        return ContentGenerator(mock_llm)
    
    @pytest.mark.asyncio
    async def test_generate_daily_briefing(self, content_generator, mock_llm):
        """Test daily briefing generation."""
        context = UserContext(
            time_context=TimeContext(
                current_time=datetime(2024, 1, 15, 9, 0),
                time_of_day="morning"
            ),
            task_context={
                "today_priorities": ["Complete project", "Review code"],
                "upcoming_deadlines": ["Project due tomorrow"]
            },
            learning_context={
                "recent_topics": ["python", "machine_learning"]
            }
        )
        
        briefing = await content_generator.generate_daily_briefing(context)
        
        assert isinstance(briefing, Briefing)
        assert briefing.priority == "high"
        assert briefing.delivery_time == "09:00"
        assert "notification" in briefing.channels
        
        # Verify LLM was called with proper prompt
        mock_llm.generate.assert_called_once()
        prompt = mock_llm.generate.call_args[0][0]
        assert "Complete project" in prompt
        assert "python" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_learning_nudge_low_mastery(self, content_generator):
        """Test learning nudge for low mastery topic."""
        nudge = await content_generator.generate_learning_nudge("python", 0.3)
        
        assert isinstance(nudge, Nudge)
        assert "python" in nudge.message.lower()
        assert nudge.action_type == "review"
        assert nudge.urgency == "low"
        assert "2-minute" in nudge.message
    
    @pytest.mark.asyncio
    async def test_generate_learning_nudge_high_mastery(self, content_generator):
        """Test learning nudge for high mastery topic."""
        nudge = await content_generator.generate_learning_nudge("python", 0.9)
        
        assert isinstance(nudge, Nudge)
        assert "python" in nudge.message.lower()
        assert "advanced topics" in nudge.message.lower()
    
    @pytest.mark.asyncio
    async def test_generate_task_suggestion(self, content_generator, mock_llm):
        """Test task suggestion generation."""
        context = UserContext(
            task_context={
                "current_task": "Working on project",
                "pattern": "context_switching"
            }
        )
        
        mock_llm.generate.return_value = "Consider time-blocking similar tasks"
        
        suggestion = await content_generator.generate_task_suggestion(context)
        
        assert isinstance(suggestion, Nudge)
        assert "time-blocking" in suggestion.message.lower()
        assert suggestion.action_type == "optimization"


class TestNotificationService:
    """Test notification delivery system."""
    
    @pytest.fixture
    def notification_service(self):
        """Initialize NotificationService."""
        return NotificationService()
    
    @pytest.mark.asyncio
    async def test_deliver_notification(self, notification_service):
        """Test notification delivery."""
        notification = Mock()
        notification.channels = ["notification"]
        notification.content = "Test notification"
        notification.priority = "medium"
        
        with patch('src.proactive.notification_service.send_push_notification') as mock_push:
            await notification_service.deliver(notification)
            mock_push.assert_called_once_with(notification)
    
    @pytest.mark.asyncio
    async def test_deliver_to_multiple_channels(self, notification_service):
        """Test delivery to multiple channels."""
        notification = Mock()
        notification.channels = ["notification", "email", "dashboard"]
        
        with patch('src.proactive.notification_service.send_push_notification') as mock_push, \
             patch('src.proactive.notification_service.send_email') as mock_email, \
             patch('src.proactive.notification_service.update_dashboard') as mock_dashboard:
            
            await notification_service.deliver(notification)
            
            mock_push.assert_called_once()
            mock_email.assert_called_once()
            mock_dashboard.assert_called_once()
    
    def test_is_appropriate_time_work_hours(self, notification_service):
        """Test time appropriateness during work hours."""
        context = UserContext(
            time_context=TimeContext(
                current_time=datetime(2024, 1, 15, 14, 0),
                is_work_hours=True,
                in_meeting=False
            )
        )
        
        notification = Mock()
        notification.priority = "medium"
        
        assert notification_service.is_appropriate_time(notification, context) is True
    
    def test_is_appropriate_time_quiet_hours(self, notification_service):
        """Test time appropriateness during quiet hours."""
        context = UserContext(
            time_context=TimeContext(
                current_time=datetime(2024, 1, 15, 23, 0),
                is_quiet_hours=True
            )
        )
        
        # Low priority should not be delivered
        notification = Mock()
        notification.priority = "low"
        assert notification_service.is_appropriate_time(notification, context) is False
        
        # Urgent should be delivered
        notification.priority = "urgent"
        assert notification_service.is_appropriate_time(notification, context) is True


class TestProactiveIntegration:
    """Integration tests for proactive capabilities."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_morning_routine(self):
        """Test complete morning proactive routine."""
        # Mock all dependencies
        mock_memory = Mock()
        mock_memory.get_recent_activities = AsyncMock(return_value=[])
        
        mock_tasks = Mock()
        mock_tasks.get_current_tasks = AsyncMock(return_value=[])
        
        mock_llm = Mock()
        mock_llm.generate = AsyncMock(return_value="Briefing content")
        
        # Initialize components
        context_analyzer = ContextAnalyzer(mock_memory, mock_tasks)
        content_generator = ContentGenerator(mock_llm)
        notification_service = NotificationService()
        
        with patch.object(notification_service, 'send_push_notification'):
            # Run morning routine
            context = await context_analyzer.get_current_context()
            briefing = await content_generator.generate_daily_briefing(context)
            await notification_service.deliver(briefing)
            
            assert briefing.content == "Briefing content"
    
    @pytest.mark.asyncio
    async def test_learning_opportunity_detection(self):
        """Test detection and response to learning opportunities."""
        # Mock knowledge tracker
        mock_tracker = Mock()
        mock_tracker.get_due_reviews = AsyncMock(return_value=[
            {"topic": "python", "mastery": 0.4, "days_overdue": 2}
        ])
        
        # Create opportunity detector
        from src.proactive.opportunity_detector import OpportunityDetector
        detector = OpportunityDetector(mock_tracker)
        
        context = UserContext(learning_context={"current_focus": "programming"})
        opportunities = await detector.detect_learning_opportunities(context)
        
        assert len(opportunities) == 1
        assert opportunities[0].type == "learning_review"
        assert opportunities[0].topic == "python"
        assert opportunities[0].urgency == "medium"


# Performance Tests
class TestProactivePerformance:
    """Performance tests for proactive system."""
    
    @pytest.mark.asyncio
    async def test_proactive_cycle_performance(self):
        """Test proactive cycle completes within time limits."""
        # Mock fast dependencies
        mock_analyzer = Mock()
        mock_analyzer.get_current_context = AsyncMock(return_value=UserContext())
        
        mock_generator = Mock()
        mock_generator.generate_daily_briefing = AsyncMock(return_value=Briefing())
        
        mock_notification = Mock()
        mock_notification.deliver = AsyncMock()
        
        engine = ProactiveEngine(
            mock_analyzer, Mock(), mock_generator, mock_notification
        )
        
        # Measure cycle time
        start_time = asyncio.get_event_loop().time()
        await engine.run_proactive_cycle()
        end_time = asyncio.get_event_loop().time()
        
        cycle_time = end_time - start_time
        assert cycle_time < 1.0, f"Cycle took {cycle_time:.2f}s, expected <1s"
    
    @pytest.mark.asyncio
    async def test_notification_delivery_latency(self):
        """Test notification delivery meets <500ms requirement."""
        service = NotificationService()
        notification = Mock()
        notification.channels = ["notification"]
        
        with patch('src.proactive.notification_service.send_push_notification') as mock_push:
            mock_push.return_value = asyncio.sleep(0.001)  # Very fast
            
            start_time = asyncio.get_event_loop().time()
            await service.deliver(notification)
            end_time = asyncio.get_event_loop().time()
            
            delivery_time = (end_time - start_time) * 1000  # Convert to ms
            assert delivery_time < 500, f"Delivery took {delivery_time:.2f}ms"
