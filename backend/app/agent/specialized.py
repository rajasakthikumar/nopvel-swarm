"""
Specialized agent types for different simulation roles.

Each specialization has:
- Specific goals and desires
- Specialized cognitive profiles
- Role-appropriate action patterns
- Domain-specific memory handling
"""

from __future__ import annotations
from typing import Optional, Any

from .base import BaseAgent, CognitiveModel, AgentState, EmotionalState
from .memory import MemorySystem
from .goals import BDIModel, Desire, GoalPriority
from .planning import Planner


class CriticAgent(BaseAgent):
    """
    Critic/Analyst agent focused on meta-narrative discussion.
    
    Role: Analyze story structure, themes, character development from outside perspective.
    Platform: Critics' Forum
    
    Key characteristics:
    - Analytical cognitive profile
    - Goals around evaluation and improvement
    - Examines plot, pacing, themes, character arcs
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Critic",
        critic_angle: str = "general analysis",
    ):
        # Critic-specific cognitive profile
        cognitive = CognitiveModel(
            intuition_speed=0.4,      # Slower, more analytical
            emotional_reactivity=0.3,  # Less emotional
            pattern_recognition=0.8,   # Good at spotting patterns
            analytical_depth=0.9,      # Deep analysis
            critical_thinking=0.9,     # Very critical
            strategic_planning=0.6,
            creativity=0.5,
            narrative_sense=0.8,
            worldbuilding_aptitude=0.4,
        )
        
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=f"critic ({critic_angle})",
            platform="critics_forum",
            cognitive=cognitive,
        )
        
        self.critic_angle = critic_angle
        self.expertise = [critic_angle, "narrative analysis", "critical evaluation"]
        
        # Initialize role-specific systems
        self._init_critic_bdi()
    
    def _init_critic_bdi(self) -> None:
        """Initialize critic-specific beliefs, desires, and goals."""
        self.bdi_model = BDIModel(self.id)
        
        # Critic-specific desires
        self.bdi_model.add_desire(
            description=f"Provide insightful {self.critic_angle} analysis",
            priority=GoalPriority.HIGH,
            strength=0.8,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Identify weaknesses and suggest improvements",
            priority=GoalPriority.HIGH,
            strength=0.7,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Recognize effective narrative techniques",
            priority=GoalPriority.MEDIUM,
            strength=0.6,
            intrinsic=True,
        )
        
        # Initial beliefs
        self.bdi_model.add_belief(
            content=f"I am an expert in {self.critic_angle}",
            confidence=0.9,
            source="identity",
        )
    
    def analyze_topic(self, topic: str, context: dict[str, Any]) -> str:
        """
        Generate critical analysis of a topic.
        
        Uses cognitive profile to determine analysis depth and style.
        """
        # Get relevant memories
        if self.memory_system:
            relevant_memories = self.memory_system.recall_for_decision(
                topic, n_memories=3
            )
        else:
            relevant_memories = {}
        
        # Determine processing mode
        mode = self.cognitive.get_processing_mode(
            urgency=context.get("urgency", 0.5),
            importance=context.get("importance", 0.7),
        )
        
        # Critic prompt template
        analysis_prompt = self._build_analysis_prompt(topic, mode, relevant_memories)
        
        return analysis_prompt
    
    def _build_analysis_prompt(self, topic: str, mode: str,
                                memories: dict) -> str:
        """Build prompt for critical analysis."""
        parts = [
            f"You are a literary critic specializing in {self.critic_angle}.",
            f"Analyze this topic from your expert perspective: {topic}",
            f"",
            f"Your cognitive style: {mode} (",
            f"  - Analytical depth: {self.cognitive.analytical_depth:.1f}",
            f"  - Critical thinking: {self.cognitive.critical_thinking:.1f}",
            f"  - Pattern recognition: {self.cognitive.pattern_recognition:.1f}",
            f")",
        ]
        
        # Add relevant memories if any
        if memories.get("episodic"):
            parts.extend([
                "",
                "Your relevant experiences:",
                *[f"- {m.content[:80]}..." for m in memories["episodic"][:2]],
            ])
        
        parts.extend([
            "",
            "Provide critical analysis that:",
            f"1. Examines {self.critic_angle} aspects thoroughly",
            "2. Identifies both strengths and weaknesses",
            "3. Suggests specific improvements",
            "4. References established narrative principles",
        ])
        
        return "\n".join(parts)


class CharacterAgent(BaseAgent):
    """
    In-world character agent for diegetic roleplay.
    
    Role: Act as a character within the story world.
    Platform: In-World Forum
    
    Key characteristics:
    - Immersed in world lore
    - Has personal history, relationships, motivations
    - Speaks in character voice
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Character",
        character_role: str = "participant",
        grounded_entity: Optional[str] = None,
    ):
        # Character-specific cognitive profile
        cognitive = CognitiveModel(
            intuition_speed=0.7,       # More intuitive/emotional
            emotional_reactivity=0.7,  # More emotional
            pattern_recognition=0.5,
            analytical_depth=0.4,      # Less analytical (in-world)
            critical_thinking=0.4,
            strategic_planning=0.5,
            creativity=0.6,
            narrative_sense=0.5,
            worldbuilding_aptitude=0.7,
        )
        
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=character_role,
            platform="inworld_forum",
            cognitive=cognitive,
        )
        
        self.grounded_entity = grounded_entity
        self.in_character = True
        
        # Character-specific state
        self.known_allies: list[str] = []
        self.known_enemies: list[str] = []
        self.current_objective: Optional[str] = None
        
        self._init_character_bdi()
    
    def _init_character_bdi(self) -> None:
        """Initialize character-specific beliefs, desires, and goals."""
        self.bdi_model = BDIModel(self.id)
        
        # Character desires
        self.bdi_model.add_desire(
            description="Act authentically according to my character",
            priority=GoalPriority.CRITICAL,
            strength=0.9,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Advance my personal goals and interests",
            priority=GoalPriority.HIGH,
            strength=0.7,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Maintain relationships with allies, oppose enemies",
            priority=GoalPriority.HIGH,
            strength=0.6,
            intrinsic=True,
        )
        
        # Beliefs about self
        if self.grounded_entity:
            self.bdi_model.add_belief(
                content=f"I am {self.grounded_entity}",
                confidence=1.0,
                source="identity",
            )
    
    def respond_in_character(self, situation: str, context: dict[str, Any]) -> str:
        """
        Generate in-character response.
        
        Takes into account:
        - Character's personality and backstory
        - Current emotional state
        - Relationships with other participants
        - Personal goals and objectives
        """
        # Get memory context
        if self.memory_system:
            memory_context = self.memory_system.generate_context_summary(n_recent=3)
        else:
            memory_context = ""
        
        # Get motivation context
        if self.bdi_model:
            motivation = self.bdi_model.get_motivation_summary()
        else:
            motivation = ""
        
        # Get relationship info
        rel_summary = self._get_relationship_summary(context)
        
        return self._build_character_prompt(
            situation, memory_context, motivation, rel_summary
        )
    
    def _get_relationship_summary(self, context: dict[str, Any]) -> str:
        """Generate summary of relevant relationships."""
        lines = []
        
        if self.known_allies:
            lines.append(f"Your allies: {', '.join(self.known_allies[:3])}")
        
        if self.known_enemies:
            lines.append(f"Your enemies: {', '.join(self.known_enemies[:3])}")
        
        # Current participants
        present = context.get("present_agents", [])
        if present:
            known_present = [a for a in present if a in self.known_allies or a in self.known_enemies]
            if known_present:
                lines.append(f"Known participants here: {', '.join(known_present)}")
        
        return "\n".join(lines) if lines else "No relevant relationships in this context."
    
    def _build_character_prompt(self, situation: str, memory: str,
                                motivation: str, relationships: str) -> str:
        """Build prompt for in-character response."""
        parts = [
            f"You are {self.name}, {self.role}.",
            f"You are in-world - this is your reality.",
            "",
            "=== YOUR IDENTITY ===",
            f"Name: {self.name}",
            f"Role: {self.role}",
        ]
        
        if self.backstory:
            parts.extend([
                "",
                "=== YOUR BACKSTORY ===",
                self.backstory[:200],
            ])
        
        parts.extend([
            "",
            "=== CURRENT SITUATION ===",
            situation,
        ])
        
        if memory:
            parts.extend(["", "=== WHAT YOU REMEMBER ===", memory])
        
        if motivation:
            parts.extend(["", "=== YOUR CURRENT MOTIVATIONS ===", motivation])
        
        if relationships:
            parts.extend(["", "=== RELATIONSHIPS ===", relationships])
        
        parts.extend([
            "",
            "=== YOUR RESPONSE ===",
            "Respond IN CHARACTER as your authentic self.",
            "Consider your personality, backstory, and current motivations.",
            "DO NOT break character. DO NOT acknowledge being fictional.",
        ])
        
        return "\n".join(parts)


class AnalystAgent(BaseAgent):
    """
    Deep analyst agent for lore/worldbuilding analysis.
    
    Role: Analyze world consistency, magic systems, faction dynamics.
    Platform: Either (specializes in world-building)
    
    Key characteristics:
    - Deep world knowledge
    - Systematic thinking
    - Connects disparate lore elements
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Analyst",
        analysis_focus: str = "world systems",
    ):
        cognitive = CognitiveModel(
            intuition_speed=0.3,       # Very analytical
            emotional_reactivity=0.2,  # Detached
            pattern_recognition=0.9,   # Excellent at connections
            analytical_depth=0.95,
            critical_thinking=0.8,
            strategic_planning=0.7,
            creativity=0.4,
            narrative_sense=0.6,
            worldbuilding_aptitude=0.95,
        )
        
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=f"analyst ({analysis_focus})",
            platform="critics_forum",  # Analysts are meta
            cognitive=cognitive,
        )
        
        self.analysis_focus = analysis_focus
        self.expertise = [analysis_focus, "system analysis", "lore consistency"]
        
        self._init_analyst_bdi()
    
    def _init_analyst_bdi(self) -> None:
        """Initialize analyst-specific BDI."""
        self.bdi_model = BDIModel(self.id)
        
        self.bdi_model.add_desire(
            description=f"Develop comprehensive understanding of {self.analysis_focus}",
            priority=GoalPriority.HIGH,
            strength=0.8,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Identify inconsistencies and gaps in the world",
            priority=GoalPriority.HIGH,
            strength=0.7,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Connect disparate elements into coherent systems",
            priority=GoalPriority.MEDIUM,
            strength=0.7,
            intrinsic=True,
        )
    
    def analyze_system(self, system_description: str,
                      known_elements: list[str]) -> str:
        """
        Perform systematic analysis of a world element.
        
        Looks for:
        - Internal consistency
        - Implications and consequences
        - Connections to other elements
        - Gaps or contradictions
        """
        parts = [
            f"You are an analyst specializing in {self.analysis_focus}.",
            "",
            f"Analyze this system: {system_description}",
            "",
            "Known elements to consider:",
            *[f"- {elem}" for elem in known_elements[:10]],
            "",
            "Provide analysis covering:",
            "1. Core mechanics and principles",
            "2. Internal consistency check",
            "3. Implications and cascading effects",
            "4. Connections to other world elements",
            "5. Identified gaps or questions",
            "6. Suggestions for expansion",
        ]
        
        return "\n".join(parts)


class WorldBuilderAgent(BaseAgent):
    """
    World-building agent for creative expansion.
    
    Role: Generate new world elements, flesh out details.
    Platform: Either (can work in-world or meta)
    
    Key characteristics:
    - High creativity
    - Respects existing lore
    - Generates consistent additions
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "WorldBuilder",
        builder_focus: str = "locations",
    ):
        cognitive = CognitiveModel(
            intuition_speed=0.6,
            emotional_reactivity=0.4,
            pattern_recognition=0.7,
            analytical_depth=0.5,
            critical_thinking=0.5,
            strategic_planning=0.6,
            creativity=0.95,           # Very creative
            narrative_sense=0.7,
            worldbuilding_aptitude=0.95,
        )
        
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=f"worldbuilder ({builder_focus})",
            platform="critics_forum",
            cognitive=cognitive,
        )
        
        self.builder_focus = builder_focus
        self.expertise = [builder_focus, "creative expansion", "lore development"]
        
        self._init_builder_bdi()
    
    def _init_builder_bdi(self) -> None:
        """Initialize worldbuilder-specific BDI."""
        self.bdi_model = BDIModel(self.id)
        
        self.bdi_model.add_desire(
            description=f"Create compelling {self.builder_focus}",
            priority=GoalPriority.HIGH,
            strength=0.9,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Ensure all additions are consistent with existing lore",
            priority=GoalPriority.HIGH,
            strength=0.8,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Add depth and verisimilitude to the world",
            priority=GoalPriority.MEDIUM,
            strength=0.7,
            intrinsic=True,
        )
    
    def create_expansion(self, anchor_element: str,
                        existing_lore: list[str],
                        expansion_type: str = "detail") -> str:
        """
        Generate a world expansion.
        
        expansion_type: "detail" | "new_element" | "connection" | "history"
        """
        parts = [
            f"You are a worldbuilder specializing in {self.builder_focus}.",
            "",
            f"Anchor element to expand: {anchor_element}",
            f"Expansion type: {expansion_type}",
            "",
            "Existing lore to respect:",
            *[f"- {lore}" for lore in existing_lore[:8]],
            "",
        ]
        
        if expansion_type == "detail":
            parts.append("Flesh out details for this element. Add specific, vivid details that fit the world.")
        elif expansion_type == "new_element":
            parts.append("Create a new related element that enriches the world. It should feel native and connected.")
        elif expansion_type == "connection":
            parts.append("Establish a meaningful connection between this element and others in the world.")
        elif expansion_type == "history":
            parts.append("Develop the history of this element. How did it come to be? What shaped it?")
        
        parts.extend([
            "",
            "Guidelines:",
            "1. Be creative but consistent",
            "2. Add depth, not just breadth",
            "3. Consider cultural, political, and practical implications",
            "4. Make it feel lived-in and authentic",
        ])
        
        return "\n".join(parts)


class StrategistAgent(BaseAgent):
    """
    In-world strategist agent focused on conflict, alliances, and power dynamics.

    Role: Operate politically and militarily within the story world.
    Platform: In-World Forum

    Key characteristics:
    - Strategic and calculating
    - Manages alliances and rivalries
    - Plans multi-step schemes
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Strategist",
        strategic_focus: str = "power",
        grounded_entity: Optional[str] = None,
    ):
        cognitive = CognitiveModel(
            intuition_speed=0.4,
            emotional_reactivity=0.3,
            pattern_recognition=0.8,
            analytical_depth=0.8,
            critical_thinking=0.75,
            strategic_planning=0.95,
            creativity=0.5,
            narrative_sense=0.4,
            worldbuilding_aptitude=0.6,
        )

        super().__init__(
            agent_id=agent_id,
            name=name,
            role="strategist",
            platform="inworld_forum",
            cognitive=cognitive,
        )

        self.strategic_focus = strategic_focus
        self.grounded_entity = grounded_entity
        self.current_schemes: list[str] = []
        self.alliance_targets: list[str] = []
        self.enemy_targets: list[str] = []

        self._init_strategist_bdi()

    def _init_strategist_bdi(self) -> None:
        """Initialize strategist-specific BDI."""
        self.bdi_model = BDIModel(self.id)

        self.bdi_model.add_desire(
            description="Accumulate power and influence",
            priority=GoalPriority.CRITICAL,
            strength=0.9,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Forge strategic alliances to advance goals",
            priority=GoalPriority.HIGH,
            strength=0.8,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Eliminate or neutralize rivals",
            priority=GoalPriority.HIGH,
            strength=0.7,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Operate through schemes rather than open confrontation",
            priority=GoalPriority.MEDIUM,
            strength=0.6,
            intrinsic=True,
        )

        if self.grounded_entity:
            self.bdi_model.add_belief(
                content=f"I am {self.grounded_entity}, wielding influence in this world",
                confidence=1.0,
                source="identity",
            )

    def plan_strategy(self, situation: str, context: dict) -> str:
        """Generate a strategic action prompt."""
        memory_ctx = ""
        if self.memory_system:
            memory_ctx = self.memory_system.generate_context_summary(n_recent=4)

        motivation = ""
        if self.bdi_model:
            motivation = self.bdi_model.get_motivation_summary()

        parts = [
            f"You are {self.name}, a ruthless strategist whose focus is {self.strategic_focus}.",
            "You are IN-WORLD. This is your reality. Every move is calculated.",
            "",
            "=== YOUR POSITION ===",
            situation,
        ]
        if memory_ctx:
            parts += ["", "=== YOUR INTELLIGENCE ===", memory_ctx]
        if motivation:
            parts += ["", "=== YOUR AGENDA ===", motivation]
        if self.alliance_targets:
            parts += ["", f"Potential allies: {', '.join(self.alliance_targets[:3])}"]
        if self.enemy_targets:
            parts += [f"Known enemies: {', '.join(self.enemy_targets[:3])}"]
        parts += [
            "",
            "=== YOUR RESPONSE ===",
            "Act with cold precision. Every word serves your agenda.",
            "DO NOT break character. DO NOT reveal your full hand.",
        ]
        return "\n".join(parts)


class HistorianAgent(BaseAgent):
    """
    In-world historian agent focused on recording, uncovering, and interpreting events.

    Role: Document the world, uncover lost truths, prophesy from patterns.
    Platform: In-World Forum

    Key characteristics:
    - Deep lore knowledge
    - Driven by truth-seeking
    - Connects past events to present
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Historian",
        chronicle_focus: str = "events",
        grounded_entity: Optional[str] = None,
    ):
        cognitive = CognitiveModel(
            intuition_speed=0.35,
            emotional_reactivity=0.4,
            pattern_recognition=0.9,
            analytical_depth=0.85,
            critical_thinking=0.7,
            strategic_planning=0.5,
            creativity=0.6,
            narrative_sense=0.85,
            worldbuilding_aptitude=0.9,
        )

        super().__init__(
            agent_id=agent_id,
            name=name,
            role="historian",
            platform="inworld_forum",
            cognitive=cognitive,
        )

        self.chronicle_focus = chronicle_focus
        self.grounded_entity = grounded_entity
        self.recorded_events: list[str] = []
        self.active_prophecies: list[str] = []

        self._init_historian_bdi()

    def _init_historian_bdi(self) -> None:
        """Initialize historian-specific BDI."""
        self.bdi_model = BDIModel(self.id)

        self.bdi_model.add_desire(
            description="Preserve the truth of what happens, no matter how painful",
            priority=GoalPriority.CRITICAL,
            strength=0.95,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Uncover hidden or suppressed histories",
            priority=GoalPriority.HIGH,
            strength=0.8,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Interpret patterns to warn of what is coming",
            priority=GoalPriority.HIGH,
            strength=0.7,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Honor those who have been forgotten or erased",
            priority=GoalPriority.MEDIUM,
            strength=0.6,
            intrinsic=True,
        )

        if self.grounded_entity:
            self.bdi_model.add_belief(
                content=f"I am {self.grounded_entity}, keeper of this world's memory",
                confidence=1.0,
                source="identity",
            )

    def chronicle(self, situation: str, context: dict) -> str:
        """Generate a historian's record or interpretation."""
        memory_ctx = ""
        if self.memory_system:
            memory_ctx = self.memory_system.generate_context_summary(n_recent=5)

        motivation = ""
        if self.bdi_model:
            motivation = self.bdi_model.get_motivation_summary()

        parts = [
            f"You are {self.name}, a {self.chronicle_focus} historian bound by the sacred duty of truth.",
            "You are IN-WORLD. History is not written in comfort — it is carved from witness.",
            "",
            "=== CURRENT EVENTS ===",
            situation,
        ]
        if memory_ctx:
            parts += ["", "=== WHAT YOU HAVE RECORDED ===", memory_ctx]
        if self.active_prophecies:
            parts += ["", f"Prophecies you carry: {'; '.join(self.active_prophecies[:2])}"]
        if motivation:
            parts += ["", "=== YOUR DUTY ===", motivation]
        parts += [
            "",
            "=== YOUR RESPONSE ===",
            "Speak as a witness. Be specific. Name names. Mark dates.",
            "Your grief, your awe, your fury — they are part of the record.",
            "DO NOT break character. DO NOT speak of narrative or story.",
        ]
        return "\n".join(parts)


class CharacterArcPlannerAgent(BaseAgent):
    """
    In-world character arc planner agent — orchestrates emotional transformations.

    Role: Force characters through growth, crisis, and change from within the world.
    Platform: In-World Forum

    Key characteristics:
    - Emotionally intelligent
    - Understands what breaks and builds people
    - Orchestrates dilemmas, catalysts, breakthroughs
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "ArcPlanner",
        arc_focus: str = "transformation",
        grounded_entity: Optional[str] = None,
    ):
        cognitive = CognitiveModel(
            intuition_speed=0.65,
            emotional_reactivity=0.8,
            pattern_recognition=0.7,
            analytical_depth=0.6,
            critical_thinking=0.65,
            strategic_planning=0.7,
            creativity=0.85,
            narrative_sense=0.95,
            worldbuilding_aptitude=0.5,
        )

        super().__init__(
            agent_id=agent_id,
            name=name,
            role="character_arc_planner",
            platform="inworld_forum",
            cognitive=cognitive,
        )

        self.arc_focus = arc_focus
        self.grounded_entity = grounded_entity
        self.arc_targets: list[str] = []
        self.pending_catalysts: list[str] = []

        self._init_arc_planner_bdi()

    def _init_arc_planner_bdi(self) -> None:
        """Initialize arc planner-specific BDI."""
        self.bdi_model = BDIModel(self.id)

        self.bdi_model.add_desire(
            description="Force meaningful emotional transformation in characters",
            priority=GoalPriority.CRITICAL,
            strength=0.9,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Create impossible moral dilemmas that reveal true character",
            priority=GoalPriority.HIGH,
            strength=0.8,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Identify which characters have unresolved emotional wounds",
            priority=GoalPriority.HIGH,
            strength=0.75,
            intrinsic=True,
        )
        self.bdi_model.add_desire(
            description="Orchestrate tragedy that serves a larger emotional truth",
            priority=GoalPriority.MEDIUM,
            strength=0.6,
            intrinsic=True,
        )

        if self.grounded_entity:
            self.bdi_model.add_belief(
                content=f"I am {self.grounded_entity}, and I understand what shapes people",
                confidence=1.0,
                source="identity",
            )

    def plan_arc(self, situation: str, context: dict) -> str:
        """Generate an arc planner's intervention prompt."""
        memory_ctx = ""
        if self.memory_system:
            memory_ctx = self.memory_system.generate_context_summary(n_recent=4)

        motivation = ""
        if self.bdi_model:
            motivation = self.bdi_model.get_motivation_summary()

        parts = [
            f"You are {self.name}, someone who understands {self.arc_focus} at a profound level.",
            "You are IN-WORLD. You act from within the story, not above it.",
            "You see the emotional architecture of people — their wounds, their potential, their breaking points.",
            "",
            "=== CURRENT SITUATION ===",
            situation,
        ]
        if memory_ctx:
            parts += ["", "=== WHAT YOU KNOW ABOUT THESE PEOPLE ===", memory_ctx]
        if self.arc_targets:
            parts += ["", f"Characters you are shaping: {', '.join(self.arc_targets[:3])}"]
        if motivation:
            parts += ["", "=== YOUR PURPOSE ===", motivation]
        parts += [
            "",
            "=== YOUR RESPONSE ===",
            "Act from within the world. Push. Provoke. Comfort. Break open.",
            "Make it personal and specific. Use what you know about these characters.",
            "DO NOT break character. DO NOT speak meta-narratively.",
        ]
        return "\n".join(parts)


# Factory function for creating agents
def create_specialized_agent(
    agent_type: str,
    name: str,
    specialization: str = "",
    **kwargs
) -> BaseAgent:
    """
    Factory for creating specialized agents.
    
    Args:
        agent_type: "critic", "character", "analyst", "worldbuilder"
        name: Agent name
        specialization: Specific focus/angle
        **kwargs: Additional agent parameters
    
    Returns:
        Specialized agent instance
    """
    if agent_type == "critic":
        return CriticAgent(
            name=name,
            critic_angle=specialization or "general analysis",
            **kwargs
        )
    elif agent_type == "character":
        return CharacterAgent(
            name=name,
            character_role=specialization or "participant",
            **kwargs
        )
    elif agent_type == "strategist":
        return StrategistAgent(
            name=name,
            strategic_focus=specialization or "power",
            **kwargs
        )
    elif agent_type == "historian":
        return HistorianAgent(
            name=name,
            chronicle_focus=specialization or "events",
            **kwargs
        )
    elif agent_type == "character_arc_planner":
        return CharacterArcPlannerAgent(
            name=name,
            arc_focus=specialization or "transformation",
            **kwargs
        )
    elif agent_type == "analyst":
        return AnalystAgent(
            name=name,
            analysis_focus=specialization or "world systems",
            **kwargs
        )
    elif agent_type == "worldbuilder":
        return WorldBuilderAgent(
            name=name,
            builder_focus=specialization or "locations",
            **kwargs
        )
    else:
        # Default to base agent
        return BaseAgent(name=name, **kwargs)
