from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    CONVERSATION = "conversation"
    LEARNING = "learning"
    FACT = "fact"
    GOAL = "goal"
    TASK = "task"


class Memory(BaseModel):
    id: Optional[str] = Field(default=None)
    type: MemoryType
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = Field(default=0)

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = str(uuid.uuid4())


class UserProfile(BaseModel):
    preferences: Dict[str, Any] = Field(default_factory=dict)
    learning_goals: List[str] = Field(default_factory=list)
    recent_topics: List[str] = Field(default_factory=list)
    interaction_style: str = Field(default="balanced")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Alias for backward compatibility with tests
UserContext = UserProfile
