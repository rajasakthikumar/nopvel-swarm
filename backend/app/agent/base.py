"""
Base Agent class with cognitive modeling and state management.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, field
import uuid
import time


class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    OBSERVING = "observing"  # Taking in information
    DELIBERATING = "deliberating"  # Deciding what to do
    ACTING = "acting"  # Performing an action
    REFLECTING = "reflecting"  # Processing outcomes
    SOCIALIZING = "socializing"  # Engaging with other agents
    RESTING = "resting"  # Low activity, memory consolidation
    DISTRESSED = "distressed"  # Emotional override state


@dataclass
class CognitiveModel:
    """
    Cognitive architecture modeling how the agent thinks.
    
    Based on dual-process theory (System 1/2) with additions for
    creative and narrative thinking specific to novel writing.
    """
    # System 1: Fast, intuitive, emotional
    intuition_speed: float = 0.7  # 0-1, how quickly they form gut reactions
    emotional_reactivity: float = 0.5  # 0-1, emotional response strength
    pattern_recognition: float = 0.6  # 0-1, ability to spot patterns
    
    # System 2: Slow, analytical, deliberate
    analytical_depth: float = 0.5  # 0-1, depth of analysis
    critical_thinking: float = 0.5  # 0-1, skepticism and evaluation
    strategic_planning: float = 0.4  # 0-1, long-term planning ability
    
    # Creative/Narrative specific
    creativity: float = 0.5  # 0-1, novel idea generation
    narrative_sense: float = 0.5  # 0-1, story structure intuition
    worldbuilding_aptitude: float = 0.5  # 0-1, creating coherent world details
    
    # Cognitive biases (modifiers that skew thinking)
    biases: dict[str, float] = field(default_factory=dict)
    # e.g., {"confirmation": 0.8, "authority": 0.3, "availability": 0.6}
    
    # Blind spots (topics they literally cannot process well)
    blind_spots: list[str] = field(default_factory=list)
    
    def get_processing_mode(self, urgency: float, importance: float) -> str:
        """
        Determine whether agent uses System 1 (fast) or System 2 (slow) thinking.
        
        High urgency + low importance = System 1 (intuitive)
        Low urgency + high importance = System 2 (analytical)
        """
        system1_score = urgency * self.intuition_speed + (1 - importance) * 0.3
        system2_score = (1 - urgency) * 0.3 + importance * self.analytical_depth
        
        if system1_score > system2_score:
            return "intuitive"
        return "analytical"


@dataclass  
class EmotionalState:
    """
    Dynamic emotional state that affects agent behavior.
    
    Uses a simplified PAD model (Pleasure-Arousal-Dominance)
    with additional narrative-emotional dimensions.
    """
    # PAD dimensions (-1 to 1)
    pleasure: float = 0.0  # Positive/negative valence
    arousal: float = 0.0  # Energy level (calm vs excited)
    dominance: float = 0.0  # Control (submissive vs dominant)
    
    # Narrative emotions
    curiosity: float = 0.5  # Drive to explore/learn
    tension: float = 0.0  # Suspense/anxiety about outcomes
    investment: float = 0.0  # Emotional stake in topic
    
    # Emotional memory - recent emotional events
    recent_emotions: list[dict] = field(default_factory=list)
    
    def get_mood_label(self) -> str:
        """Convert PAD values to human-readable mood."""
        if self.pleasure > 0.3 and self.arousal > 0.3:
            return "excited" if self.dominance > 0 else "enthusiastic"
        elif self.pleasure > 0.3 and self.arousal < -0.3:
            return "content" if self.dominance > 0 else "relaxed"
        elif self.pleasure < -0.3 and self.arousal > 0.3:
            return "angry" if self.dominance > 0 else "anxious"
        elif self.pleasure < -0.3 and self.arousal < -0.3:
            return "depressed" if self.dominance < 0 else "resigned"
        return "neutral"
    
    def update_from_event(self, event_valence: float, event_arousal: float, 
                         description: str) -> None:
        """Update emotional state based on an event."""
        # Decay current state slightly
        self.pleasure *= 0.9
        self.arousal *= 0.9
        
        # Add new event effect
        self.pleasure += event_valence * 0.3
        self.arousal += event_arousal * 0.3
        
        # Clamp to [-1, 1]
        self.pleasure = max(-1, min(1, self.pleasure))
        self.arousal = max(-1, min(1, self.arousal))
        
        # Store emotional memory
        self.recent_emotions.append({
            "time": time.time(),
            "valence": event_valence,
            "arousal": event_arousal,
            "description": description
        })
        
        # Keep only last 10
        if len(self.recent_emotions) > 10:
            self.recent_emotions.pop(0)


class BaseAgent:
    """
    Enhanced base agent with cognitive modeling, emotional state,
    and sophisticated memory systems.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Agent",
        role: str = "participant",
        platform: str = "critics_forum",
        cognitive: Optional[CognitiveModel] = None,
    ):
        self.id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.role = role
        self.platform = platform
        
        # Core cognitive and emotional models
        self.cognitive = cognitive or CognitiveModel()
        self.emotional_state = EmotionalState()
        
        # Agent state machine
        self.state = AgentState.IDLE
        self.state_history: list[tuple[float, AgentState]] = []
        
        # Identity and personality (can be expanded from original AgentPersona)
        self.personality_traits: list[str] = []
        self.personality_summary: str = ""
        self.backstory: str = ""
        self.expertise: list[str] = []
        
        # World grounding
        self.grounded_entity: Optional[str] = None
        self.known_entities: list[str] = []
        self.faction_membership: Optional[str] = None
        
        # Behavioral parameters (0-1)
        self.influence_level: float = 0.5
        self.reaction_speed: float = 0.5
        self.susceptibility: float = 0.3
        
        # Simulation tracking
        self.created_at: float = time.time()
        self.last_action_time: Optional[float] = None
        self.action_count: int = 0
        self.interactions: list[dict] = []
        
        # Will be set by simulation engine
        self.memory_system: Optional[Any] = None
        self.bdi_model: Optional[Any] = None
        self.planner: Optional[Any] = None
    
    def transition_to(self, new_state: AgentState) -> None:
        """Transition to a new state with history tracking."""
        old_state = self.state
        self.state = new_state
        self.state_history.append((time.time(), new_state))
        
        # Keep history manageable
        if len(self.state_history) > 100:
            self.state_history = self.state_history[-100:]
    
    def is_available(self) -> bool:
        """Check if agent is available to act (not in blocking state)."""
        return self.state not in [AgentState.ACTING, AgentState.DELIBERATING]
    
    def get_state_duration(self) -> float:
        """Get how long agent has been in current state."""
        if not self.state_history:
            return 0.0
        return time.time() - self.state_history[-1][0]
    
    def get_cognitive_load(self) -> float:
        """
        Calculate current cognitive load (0-1).
        High when stressed, emotional, or processing complex info.
        """
        load = 0.0
        
        # Emotional arousal increases load
        load += abs(self.emotional_state.arousal) * 0.3
        
        # Recent activity increases load
        if len(self.state_history) > 0:
            recent_actions = sum(1 for t, s in self.state_history[-10:] 
                               if s == AgentState.ACTING)
            load += (recent_actions / 10) * 0.3
        
        # Investment in topic increases load
        load += self.emotional_state.investment * 0.2
        
        return min(1.0, load)
    
    def should_deliberate(self, topic_importance: float) -> bool:
        """
        Determine if agent should use deliberative thinking.
        Based on cognitive model, emotional state, and topic importance.
        """
        cognitive_load = self.get_cognitive_load()
        
        # High cognitive load = more likely to go intuitive
        # High importance = more likely to deliberate
        deliberate_score = (topic_importance * self.cognitive.analytical_depth) - \
                          (cognitive_load * 0.5)
        
        return deliberate_score > 0.3
    
    def record_interaction(self, other_agent_id: str, interaction_type: str,
                          outcome: str, sentiment: float) -> None:
        """Record an interaction with another agent."""
        self.interactions.append({
            "time": time.time(),
            "other_agent": other_agent_id,
            "type": interaction_type,
            "outcome": outcome,
            "sentiment": sentiment,
        })
        
        # Keep manageable
        if len(self.interactions) > 50:
            self.interactions = self.interactions[-50:]
    
    def get_relationship_with(self, other_agent_id: str) -> dict:
        """Calculate relationship metrics with another agent."""
        relevant = [i for i in self.interactions 
                   if i["other_agent"] == other_agent_id]
        
        if not relevant:
            return {"sentiment": 0.0, "interactions": 0, "last": None}
        
        avg_sentiment = sum(i["sentiment"] for i in relevant) / len(relevant)
        return {
            "sentiment": avg_sentiment,
            "interactions": len(relevant),
            "last": relevant[-1]["time"] if relevant else None
        }
    
    def to_dict(self) -> dict:
        """Serialize agent to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "platform": self.platform,
            "state": self.state.value,
            "cognitive": {
                "intuition_speed": self.cognitive.intuition_speed,
                "analytical_depth": self.cognitive.analytical_depth,
                "creativity": self.cognitive.creativity,
            },
            "emotional_state": {
                "pleasure": self.emotional_state.pleasure,
                "arousal": self.emotional_state.arousal,
                "mood": self.emotional_state.get_mood_label(),
            },
            "action_count": self.action_count,
            "created_at": self.created_at,
        }
