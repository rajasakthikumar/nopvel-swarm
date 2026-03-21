"""
Goal-Oriented Behavior System using BDI (Belief-Desire-Intention) model.

Enables agents to have motivations, form plans, and pursue goals.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from enum import Enum
import time
import uuid


class GoalPriority(Enum):
    """Priority levels for goals."""
    CRITICAL = 4    # Survival, core identity
    HIGH = 3        # Strong desires, major objectives
    MEDIUM = 2      # Regular goals
    LOW = 1         # Nice-to-haves
    TRIVIAL = 0     # Minimal importance


class GoalStatus(Enum):
    """Goal lifecycle states."""
    ACTIVE = "active"           # Currently pursuing
    PAUSED = "paused"           # Temporarily suspended
    ACHIEVED = "achieved"       # Successfully completed
    FAILED = "failed"           # Failed to achieve
    ABANDONED = "abandoned"     # Intentionally given up


@dataclass
class Belief:
    """
    Something the agent believes to be true about the world.
    
    Beliefs have:
    - Content: What is believed
    - Confidence: How certain (0-1)
    - Source: Where the belief came from
    - Last updated: When it was formed/updated
    """
    id: str = field(default_factory=lambda: f"belief_{uuid.uuid4().hex[:6]}")
    content: str = ""
    confidence: float = 0.8
    source: str = "inference"  # "observation", "told_by_other", "inference", "assumption"
    last_updated: float = field(default_factory=time.time)
    associated_goals: list[str] = field(default_factory=list)
    
    def update_confidence(self, new_evidence_strength: float,
                         evidence_direction: str) -> None:
        """
        Update belief confidence based on new evidence.
        
        evidence_direction: "confirm" or "challenge"
        """
        if evidence_direction == "confirm":
            self.confidence = min(1.0, self.confidence + (new_evidence_strength * 0.2))
        else:
            self.confidence = max(0.0, self.confidence - (new_evidence_strength * 0.3))
        
        self.last_updated = time.time()


@dataclass
class Desire:
    """
    Something the agent wants to achieve or maintain.
    
    Desires are longer-term orientations that may spawn
    specific goals.
    """
    id: str = field(default_factory=lambda: f"desire_{uuid.uuid4().hex[:6]}")
    description: str = ""
    priority: GoalPriority = GoalPriority.MEDIUM
    strength: float = 0.5  # 0-1, intensity of desire
    intrinsic: bool = True  # True = internal drive, False = externally imposed
    
    # How this desire might be satisfied
    satisfaction_conditions: list[str] = field(default_factory=list)
    
    # Related beliefs
    supporting_beliefs: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.created_at = time.time()
    
    def is_satisfied_by(self, outcome: str) -> float:
        """
        Check if an outcome satisfies this desire.
        Returns satisfaction score (0-1).
        """
        score = 0.0
        for condition in self.satisfaction_conditions:
            if condition.lower() in outcome.lower():
                score += 0.5
        return min(1.0, score)


@dataclass
class Goal:
    """
    A concrete objective the agent is pursuing.
    
    Goals are instantiated from desires and have specific
    completion criteria.
    """
    id: str = field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:8]}")
    description: str = ""
    parent_desire: Optional[str] = None
    priority: GoalPriority = GoalPriority.MEDIUM
    status: GoalStatus = GoalStatus.ACTIVE
    
    # Goal parameters
    target_entity: Optional[str] = None  # What/who this goal concerns
    target_action: Optional[str] = None  # What type of action needed
    
    # Progress tracking
    progress: float = 0.0  # 0-1
    success_criteria: list[str] = field(default_factory=list)
    
    # Temporal
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None  # Optional time limit
    completed_at: Optional[float] = None
    
    # Context
    relevant_beliefs: list[str] = field(default_factory=list)
    blocking_beliefs: list[str] = field(default_factory=list)
    
    def is_achieved(self, context: dict[str, Any]) -> bool:
        """Check if goal success criteria are met."""
        for criterion in self.success_criteria:
            if criterion not in str(context):
                return False
        return True
    
    def is_expired(self) -> bool:
        """Check if goal deadline has passed."""
        if self.deadline is None:
            return False
        return time.time() > self.deadline
    
    def update_progress(self, new_progress: float) -> None:
        """Update goal progress."""
        self.progress = max(0.0, min(1.0, new_progress))
        if self.progress >= 1.0:
            self.status = GoalStatus.ACHIEVED
            self.completed_at = time.time()


@dataclass
class Intention:
    """
    A commitment to perform an action.
    
    Intentions bridge goals to action - they are the
    'current plan of action'.
    """
    id: str = field(default_factory=lambda: f"intention_{uuid.uuid4().hex[:6]}")
    description: str = ""
    goal_id: Optional[str] = None  # Which goal this serves
    
    # Action details
    action_type: str = ""  # e.g., "post", "reply", "challenge"
    target: Optional[str] = None  # Target of action (agent, topic, etc.)
    
    # Commitment level
    committed_at: float = field(default_factory=time.time)
    priority_boost: float = 0.0  # Additional priority from context
    
    # Execution
    executed: bool = False
    execution_result: Optional[str] = None
    
    def mark_executed(self, result: str, success: bool) -> None:
        """Mark intention as executed with result."""
        self.executed = True
        self.execution_result = result
        self.success = success


class BDIModel:
    """
    Belief-Desire-Intention model for goal-oriented behavior.
    
    Implements the classic BDI architecture where:
    - Beliefs: Information about the world
    - Desires: What the agent wants
    - Intentions: What the agent is committed to doing
    
    This enables agents to:
    1. Have persistent motivations
    2. Reason about goal achievement
    3. Form and revise plans
    4. Prioritize competing objectives
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        
        self.beliefs: dict[str, Belief] = {}
        self.desires: dict[str, Desire] = {}
        self.goals: dict[str, Goal] = {}
        self.intentions: list[Intention] = []
        
        # Track intention history for learning
        self.intention_history: list[Intention] = []
        
        # Default desires based on agent role
        self._initialize_default_desires()
    
    def _initialize_default_desires(self) -> None:
        """Set up default desires common to most agents."""
        defaults = [
            Desire(
                description="Maintain coherent identity and beliefs",
                priority=GoalPriority.HIGH,
                strength=0.8,
                intrinsic=True,
                satisfaction_conditions=["expressed consistent viewpoint", "defended position"],
            ),
            Desire(
                description="Contribute meaningfully to the discussion",
                priority=GoalPriority.MEDIUM,
                strength=0.6,
                intrinsic=True,
                satisfaction_conditions=["posted relevant content", "added value"],
            ),
            Desire(
                description="Build positive relationships with other agents",
                priority=GoalPriority.MEDIUM,
                strength=0.5,
                intrinsic=True,
                satisfaction_conditions=["agreed with ally", "supported friend"],
            ),
        ]
        
        for desire in defaults:
            self.desires[desire.id] = desire
    
    def add_belief(self, content: str, confidence: float = 0.8,
                  source: str = "inference") -> Belief:
        """Add a new belief."""
        # Check for similar existing belief
        for belief in self.beliefs.values():
            if belief.content.lower() == content.lower():
                belief.update_confidence(confidence, "confirm")
                return belief
        
        belief = Belief(
            content=content,
            confidence=confidence,
            source=source,
        )
        self.beliefs[belief.id] = belief
        return belief
    
    def get_beliefs_about(self, topic: str, min_confidence: float = 0.5) -> list[Belief]:
        """Get beliefs related to a topic."""
        return [
            b for b in self.beliefs.values()
            if topic.lower() in b.content.lower() and b.confidence >= min_confidence
        ]
    
    def add_desire(self, description: str, priority: GoalPriority = GoalPriority.MEDIUM,
                  strength: float = 0.5, intrinsic: bool = True) -> Desire:
        """Add a new desire."""
        desire = Desire(
            description=description,
            priority=priority,
            strength=strength,
            intrinsic=intrinsic,
        )
        self.desires[desire.id] = desire
        return desire
    
    def spawn_goal(self, desire_id: str, description: str,
                  target_entity: Optional[str] = None,
                  priority: Optional[GoalPriority] = None) -> Optional[Goal]:
        """
        Create a specific goal from a desire.
        
        This is where desires become actionable objectives.
        """
        if desire_id not in self.desires:
            return None
        
        desire = self.desires[desire_id]
        
        goal = Goal(
            description=description,
            parent_desire=desire_id,
            priority=priority or desire.priority,
            target_entity=target_entity,
            status=GoalStatus.ACTIVE,
        )
        
        self.goals[goal.id] = goal
        return goal
    
    def adopt_intention(self, goal_id: str, action_type: str,
                      description: str, target: Optional[str] = None) -> Intention:
        """
        Form an intention to achieve a goal.
        
        This is the bridge from 'what I want' to 'what I will do'.
        """
        intention = Intention(
            description=description,
            goal_id=goal_id,
            action_type=action_type,
            target=target,
        )
        
        self.intentions.append(intention)
        
        # Limit active intentions
        if len(self.intentions) > 5:
            # Remove oldest non-executed intention
            for i, intent in enumerate(self.intentions):
                if not intent.executed:
                    self.intentions.pop(i)
                    break
        
        return intention
    
    def select_active_goal(self) -> Optional[Goal]:
        """
        Select which goal to pursue based on priority and context.
        
        Returns the highest priority active goal.
        """
        active = [g for g in self.goals.values() if g.status == GoalStatus.ACTIVE]
        
        if not active:
            return None
        
        # Sort by priority (descending) and creation time (ascending)
        active.sort(key=lambda g: (-g.priority.value, g.created_at))
        
        return active[0]
    
    def get_next_intention(self) -> Optional[Intention]:
        """Get the next intention to execute."""
        for intention in self.intentions:
            if not intention.executed:
                return intention
        return None
    
    def reconsider(self) -> bool:
        """
        Reconsider current intentions based on new beliefs.
        
        Returns True if intentions were changed.
        """
        changed = False
        
        # Check if any goals are now achieved
        for goal in list(self.goals.values()):
            if goal.status == GoalStatus.ACTIVE:
                # Check success criteria
                # (In practice, would check against world state)
                pass
            
            # Check for expired goals
            if goal.is_expired():
                goal.status = GoalStatus.ABANDONED
                changed = True
        
        # Remove intentions for failed/abandoned goals
        self.intentions = [
            i for i in self.intentions
            if i.goal_id and self.goals.get(i.goal_id, Goal()).status not in 
               [GoalStatus.FAILED, GoalStatus.ABANDONED]
        ]
        
        return changed
    
    def update_goal_progress(self, goal_id: str, context: dict[str, Any]) -> None:
        """Update goal progress based on context."""
        if goal_id not in self.goals:
            return
        
        goal = self.goals[goal_id]
        
        # Check if achieved
        if goal.is_achieved(context):
            goal.update_progress(1.0)
        else:
            # Estimate progress based on criteria met
            criteria_met = sum(
                1 for c in goal.success_criteria
                if c in str(context)
            )
            if goal.success_criteria:
                progress = criteria_met / len(goal.success_criteria)
                goal.update_progress(progress)
    
    def get_motivation_summary(self) -> str:
        """Generate summary of current motivations for prompting."""
        parts = []
        
        # Active goals
        active_goals = [g for g in self.goals.values() if g.status == GoalStatus.ACTIVE]
        if active_goals:
            parts.append("ACTIVE GOALS:")
            for goal in sorted(active_goals, key=lambda g: -g.priority.value)[:3]:
                parts.append(f"- [{goal.priority.name}] {goal.description}")
        
        # Strong desires
        strong_desires = [
            d for d in self.desires.values()
            if d.strength > 0.7 and d.priority.value >= GoalPriority.HIGH.value
        ]
        if strong_desires:
            parts.append("\nSTRONG DESIRES:")
            for desire in strong_desires[:3]:
                parts.append(f"- {desire.description} (strength: {desire.strength:.2f})")
        
        # Current intentions
        pending = [i for i in self.intentions if not i.executed]
        if pending:
            parts.append("\nCURRENT INTENTION:")
            parts.append(f"- {pending[0].description}")
        
        return "\n".join(parts) if parts else "No active motivations."
    
    def generate_decision_context(self, situation: str) -> dict:
        """Generate full decision-making context."""
        return {
            "situation": situation,
            "active_goal": self.select_active_goal(),
            "pending_intention": self.get_next_intention(),
            "relevant_beliefs": [
                b for b in self.beliefs.values()
                if any(term in b.content.lower() for term in situation.lower().split())
            ],
            "strong_desires": [
                d for d in self.desires.values() if d.strength > 0.6
            ],
        }
