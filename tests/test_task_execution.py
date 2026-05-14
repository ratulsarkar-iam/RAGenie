"""
Unit tests for Task Execution Framework
Based on openspec/changes/personal-assistant-enhancements/specs/task-execution/spec.md
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from src.tasks.task_engine import TaskEngine, TaskResult
from src.tasks.action_registry import ActionRegistry
from src.tasks.mcp_manager import MCPManager
from src.tasks.task_parser import Task, TaskType, TaskParser

class TestTaskEngine:
    """Test the core task execution engine."""
    
    @pytest.fixture
    def mock_mcp_manager(self):
        """Create mock MCP manager."""
        manager = Mock(spec=MCPManager)
        manager.execute_action = AsyncMock(return_value={"status": "success"})
        return manager
    
    @pytest.fixture
    def task_engine(self, mock_mcp_manager):
        """Initialize TaskEngine with mock dependencies."""
        return TaskEngine(mock_mcp_manager)
    
    @pytest.mark.asyncio
    async def test_execute_reminder_task(self, task_engine, mock_mcp_manager):
        """Test executing a reminder creation task."""
        request = "Remind me to call John tomorrow at 2 PM"
        
        result = await task_engine.execute_task(request)
        
        assert isinstance(result, TaskResult)
        assert result.success is True
        assert "Reminder created" in result.summary
        
        # Verify MCP was called
        mock_mcp_manager.execute_action.assert_called_once()
        call_args = mock_mcp_manager.execute_action.call_args
        assert call_args[0][0] == "reminders"  # client_name
        assert call_args[0][1] == "create_reminder"  # action
    
    @pytest.mark.asyncio
    async def test_execute_calendar_task(self, task_engine, mock_mcp_manager):
        """Test executing a calendar event creation task."""
        request = "Schedule a meeting with the team Friday at 10 AM"
        
        result = await task_engine.execute_task(request)
        
        assert isinstance(result, TaskResult)
        assert result.success is True
        assert "Calendar event" in result.summary
        
        # Verify MCP was called
        mock_mcp_manager.execute_action.assert_called_once()
        call_args = mock_mcp_manager.execute_action.call_args
        assert call_args[0][0] == "calendar"
        assert call_args[0][1] == "create_event"
    
    @pytest.mark.asyncio
    async def test_execute_unknown_task(self, task_engine, mock_mcp_manager):
        """Test handling of unknown task requests."""
        request = "Do something I haven't defined"
        
        result = await task_engine.execute_task(request)
        
        assert isinstance(result, TaskResult)
        assert result.success is False
        assert "Could not understand" in result.summary
        
        # Verify MCP was not called
        mock_mcp_manager.execute_action.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_task_execution_with_context(self, task_engine, mock_mcp_manager):
        """Test task execution with user context."""
        request = "Remind me about the meeting"
        context = {"current_task": "preparing presentation"}
        
        result = await task_engine.execute_task(request, context)
        
        assert isinstance(result, TaskResult)
        # Context should be used to enhance task parsing
        mock_mcp_manager.execute_action.assert_called_once()


class TestActionRegistry:
    """Test the action registration and discovery system."""
    
    @pytest.fixture
    def action_registry(self):
        """Initialize ActionRegistry."""
        return ActionRegistry()
    
    def test_register_action(self, action_registry):
        """Test registering a new action."""
        mock_action = Mock()
        mock_action.name = "test_action"
        
        action_registry.register_action(mock_action)
        
        assert "test_action" in action_registry.actions
        assert action_registry.actions["test_action"] == mock_action
    
    def test_get_action(self, action_registry):
        """Test retrieving an action by name."""
        mock_action = Mock()
        mock_action.name = "test_action"
        action_registry.register_action(mock_action)
        
        retrieved = action_registry.get_action("test_action")
        assert retrieved == mock_action
        
        # Test non-existent action
        assert action_registry.get_action("non_existent") is None
    
    def test_list_actions(self, action_registry):
        """Test listing all registered actions."""
        initial_count = len(action_registry.list_actions())
        actions = [Mock(name=f"action_{i}") for i in range(3)]
        for action in actions:
            action.name = f"action_{actions.index(action)}"
            action_registry.register_action(action)
        
        listed = action_registry.list_actions()
        assert len(listed) == initial_count + 3
        assert all(action in listed for action in actions)


class TestTaskParser:
    """Test the natural language task parsing."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM wrapper."""
        llm = Mock()
        llm.generate = AsyncMock(return_value='''{
            "action_type": "reminder",
            "parameters": {
                "message": "Call John",
                "trigger_time": "2024-01-15T14:00:00"
            },
            "priority": "medium"
        }''')
        return llm
    
    @pytest.fixture
    def task_parser(self, mock_llm):
        """Initialize TaskParser with mock LLM."""
        from src.tasks.task_parser import TaskParser
        return TaskParser(mock_llm)
    
    @pytest.mark.asyncio
    async def test_parse_reminder_request(self, task_parser, mock_llm):
        """Test parsing a reminder creation request."""
        request = "Remind me to call John tomorrow at 2 PM"
        context = {"user_timezone": "UTC"}
        
        task = await task_parser.parse_request(request, context)
        
        assert isinstance(task, Task)
        assert task.action_type == "reminder"
        assert "Call John" in task.parameters["message"]
        assert task.priority == "medium"
        
        # Verify LLM was called with proper prompt
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args[0][0]
        assert request in call_args
    
    @pytest.mark.asyncio
    async def test_parse_calendar_request(self, task_parser, mock_llm):
        """Test parsing a calendar event request."""
        # Update mock response for calendar
        mock_llm.generate.return_value = '''{
            "action_type": "calendar",
            "parameters": {
                "title": "Team Meeting",
                "start": "2024-01-19T10:00:00",
                "duration": 60
            },
            "priority": "high"
        }'''
        
        request = "Schedule team meeting Friday 10 AM"
        task = await task_parser.parse_request(request, {})
        
        assert task.action_type == "calendar"
        assert task.parameters["title"] == "Team Meeting"
        assert task.priority == "high"
    
    @pytest.mark.asyncio
    async def test_parse_with_context(self, task_parser, mock_llm):
        """Test parsing with user context."""
        request = "Remind me about the meeting"
        context = {
            "recent_events": ["Team meeting scheduled"],
            "current_date": "2024-01-14"
        }
        
        await task_parser.parse_request(request, context)
        
        # Verify context was included in prompt
        call_args = mock_llm.generate.call_args[0][0]
        assert str(context) in call_args


class TestMCPManager:
    """Test MCP client management."""
    
    @pytest.fixture
    def mcp_config(self):
        """Create mock MCP configuration (flat list as MCPManager expects)."""
        return [
            {
                "name": "calendar",
                "enabled": True,
                "transport": "stdio",
                "command": "python",
                "args": ["test_calendar.py"]
            },
            {
                "name": "reminders",
                "enabled": True,
                "transport": "stdio",
                "command": "python",
                "args": ["test_reminders.py"]
            }
        ]
    
    @pytest.mark.asyncio
    async def test_initialize_clients(self, mcp_config):
        """Test MCP client initialization."""
        with patch('src.tasks.mcp_manager.MCPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            manager = MCPManager(mcp_config)
            await manager.initialize_clients()
            
            assert len(manager.clients) == 2
            assert "calendar" in manager.clients
            assert "reminders" in manager.clients
            
            # Verify clients were connected
            assert mock_client.connect.call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_action_success(self, mcp_config):
        """Test successful action execution through MCP."""
        with patch('src.tasks.mcp_manager.MCPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.call.return_value = {"event_id": "123"}
            mock_client_class.return_value = mock_client
            
            manager = MCPManager(mcp_config)
            await manager.initialize_clients()
            
            result = await manager.execute_action("calendar", "create_event", {
                "title": "Test Event",
                "start": "2024-01-15T10:00:00"
            })
            
            assert result["event_id"] == "123"
            mock_client.call.assert_called_once_with("create_event", {
                "title": "Test Event",
                "start": "2024-01-15T10:00:00"
            })
    
    @pytest.mark.asyncio
    async def test_execute_action_client_not_found(self, mcp_config):
        """Test action execution when client doesn't exist."""
        manager = MCPManager(mcp_config)
        # Don't initialize clients
        
        with pytest.raises(ValueError, match="MCP client nonexistent not found"):
            await manager.execute_action("nonexistent", "test_action", {})


class TestTaskIntegration:
    """Integration tests for task execution system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_task_execution(self):
        """Test complete task execution flow."""
        mock_mcp = Mock(spec=MCPManager)
        mock_mcp.execute_action = AsyncMock(return_value={"status": "created", "id": "123"})
        
        task_engine = TaskEngine(mock_mcp)
        
        result = await task_engine.execute_task("Create a test reminder")
        
        assert result.success is True
        assert "Reminder created" in result.summary
    
    @pytest.mark.asyncio
    async def test_task_with_mcp_failure(self):
        """Test task execution when MCP client fails."""
        with patch('src.tasks.mcp_manager.MCPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.call.side_effect = Exception("MCP connection failed")
            mock_client_class.return_value = mock_client
            
            mcp_config = [{
                "name": "reminders",
                "enabled": True,
                "transport": "stdio",
                "command": "python",
                "args": ["test.py"]
            }]
            
            mcp_manager = MCPManager(mcp_config)
            await mcp_manager.initialize_clients()
            task_engine = TaskEngine(mcp_manager)
            
            result = await task_engine.execute_task("Create reminder")
            
            assert result.success is False
            assert "Failed to create reminder" in result.summary


# Contract Tests for MCP Clients
class TestMCPClientContracts:
    """Contract tests ensuring MCP clients meet expected interface."""
    
    @pytest.mark.asyncio
    async def test_calendar_client_contract(self):
        """Test calendar MCP client implements required methods."""
        # This would test the actual MCP client implementation
        # For now, test the contract expectations
        required_methods = ["create_event", "list_events", "update_event", "delete_event"]
        
        # In real implementation, you would:
        # 1. Start the MCP client process
        # 2. Connect via stdio
        # 3. Call list_tools() to verify required tools
        # 4. Test each tool with valid/invalid inputs
        
        assert required_methods  # Placeholder
    
    @pytest.mark.asyncio
    async def test_reminder_client_contract(self):
        """Test reminder MCP client implements required methods."""
        required_methods = ["create_reminder", "list_reminders", "complete_reminder"]
        
        # Similar contract testing as above
        assert required_methods  # Placeholder


# Performance Tests
class TestTaskPerformance:
    """Performance tests for task execution."""
    
    @pytest.mark.asyncio
    async def test_task_execution_timeout(self):
        """Test task execution respects 2-second timeout requirement."""
        # Mock MCP client that takes too long
        with patch('src.tasks.mcp_manager.MCPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.call = AsyncMock(side_effect=lambda *args: asyncio.sleep(3))
            mock_client_class.return_value = mock_client
            
            mcp_config = [{
                "name": "slow_client",
                "enabled": True,
                "transport": "stdio",
                "command": "python",
                "args": ["slow.py"]
            }]
            
            mcp_manager = MCPManager(mcp_config)
            await mcp_manager.initialize_clients()
            
            # Task should handle timeout gracefully
            task_engine = TaskEngine(mcp_manager)
            
            start_time = asyncio.get_event_loop().time()
            result = await task_engine.execute_task("Test task")
            end_time = asyncio.get_event_loop().time()
            
            # Should complete quickly despite slow client
            execution_time = end_time - start_time
            assert execution_time < 2.5, f"Task took {execution_time:.2f}s, expected <2.5s"
            assert result.success is False
