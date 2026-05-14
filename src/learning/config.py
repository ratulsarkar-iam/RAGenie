from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class LearningConfig:
    adaptation_rate: float = 0.1
    mastery_threshold: float = 0.8
    min_mastery: float = 0.0
    max_mastery: float = 1.0
    window_size: int = 100
    min_samples: int = 10
    spaced_repetition_base_days: int = 1
    max_interval_days: int = 30
    feedback_weights: Dict[str, float] = field(default_factory=lambda: {
        "thumbs_up": 0.1,
        "thumbs_down": -0.15,
        "correction": -0.2,
    })


@dataclass
class SRSConfig:
    intervals: List[int] = field(default_factory=lambda: [1, 3, 7, 14, 30, 90])
    max_interval: int = 180
