"""
Adapter to integrate the new agent architecture with the existing simulation engine.

This bridge allows:
1. Converting legacy AgentPersona to new BaseAgent subclasses
2. Using new memory and goal systems within existing simulation
3. Gradual migration without breaking existing code
"""

from __future__ import annotations
from typing import Optional, Any
import logging

from app.models.schemas import AgentPersona, SimPost, SocialAction, Platform
from app.agent.base import BaseAgent, CognitiveModel, AgentState, EmotionalState
from app.agent.memory import MemorySystem
from app.agent.goals import BDIModel, Goal, GoalPriority
from app.agent.planning import Planner, Plan
from app.agent.specialized import (
    CriticAgent, CharacterAgent, StrategistAgent, HistorianAgent,
    CharacterArcPlannerAgent, create_specialized_agent,
)

logger = logging.getLogger("novelswarm.agent_adapter")


class AgentAdapter:
    """
    Adapts between legacy AgentPersona and new BaseAgent architecture.
    
    Wraps an AgentPersona and provides access to new cognitive capabilities.
    """
    
    def __init__(self, persona: AgentPersona):
        self.persona = persona
        self._enhanced_agent: Optional[BaseAgent] = None
        self._memory_system: Optional[MemorySystem] = None
        self._bdi_model: Optional[BDIModel] = None
        self._planner: Optional[Planner] = None
        
        # Initialize enhanced agent
        self._initialize_enhanced_agent()
    
    def _initialize_enhanced_agent(self) -> None:
        """Create enhanced agent from persona data, using role-aware specialization."""
        role_key = (self.persona.role or "").lower().replace(" ", "_").replace("-", "_")

        if self.persona.platform == Platform.CRITICS_FORUM:
            self._enhanced_agent = CriticAgent(
                agent_id=self.persona.id,
                name=self.persona.name,
                critic_angle=self.persona.role or "general analysis",
            )
        elif role_key == "strategist":
            self._enhanced_agent = StrategistAgent(
                agent_id=self.persona.id,
                name=self.persona.name,
                strategic_focus=self.persona.role or "power",
                grounded_entity=self.persona.grounded_entity,
            )
        elif role_key == "historian":
            self._enhanced_agent = HistorianAgent(
                agent_id=self.persona.id,
                name=self.persona.name,
                chronicle_focus=self.persona.role or "events",
                grounded_entity=self.persona.grounded_entity,
            )
        elif role_key == "character_arc_planner":
            self._enhanced_agent = CharacterArcPlannerAgent(
                agent_id=self.persona.id,
                name=self.persona.name,
                arc_focus=self.persona.role or "transformation",
                grounded_entity=self.persona.grounded_entity,
            )
        else:
            self._enhanced_agent = CharacterAgent(
                agent_id=self.persona.id,
                name=self.persona.name,
                character_role=self.persona.role or "participant",
                grounded_entity=self.persona.grounded_entity,
            )
        
        # Copy over personality data
        enhanced = self._enhanced_agent
        enhanced.personality_traits = self.persona.personality_traits
        enhanced.personality_summary = self.persona.personality_summary
        enhanced.backstory = self.persona.backstory
        enhanced.expertise = self.persona.expertise
        
        # Copy cognitive profile if available
        if self.persona.cognitive:
            enhanced.cognitive = CognitiveModel(
                intuition_speed=0.7 if self.persona.cognitive.reasoning_style == "intuitive" else 0.4,
                emotional_reactivity=self.persona.susceptibility,
                pattern_recognition=0.6,
                analytical_depth=0.8 if "analytical" in self.persona.cognitive.reasoning_style else 0.5,
                critical_thinking=0.7,
                strategic_planning=0.6,
                creativity=self.persona.creativity,
                narrative_sense=0.6,
                worldbuilding_aptitude=0.5,
                biases={b: 0.7 for b in self.persona.cognitive.cognitive_biases},
                blind_spots=self.persona.cognitive.blind_spots,
            )
        
        # Copy behavioral parameters
        enhanced.influence_level = self.persona.influence_level
        enhanced.reaction_speed = self.persona.reaction_speed
        enhanced.susceptibility = self.persona.susceptibility
        
        # Initialize systems
        self._memory_system = MemorySystem(self.persona.id)
        self._bdi_model = BDIModel(self.persona.id)
        self._planner = Planner(self.persona.id)
        
        # Connect systems
        enhanced.memory_system = self._memory_system
        enhanced.bdi_model = self._bdi_model
        enhanced.planner = self._planner
        
        # Transfer living memories to episodic memory
        if self.persona.living_memories:
            for mem in self.persona.living_memories:
                self._memory_system.store_experience(
                    description=mem.description,
                    round_num=mem.source_round,
                    emotional_valence=1.0 if mem.type in ["scar", "grudge"] else 0.5,
                    emotional_arousal=mem.intensity,
                    importance=mem.intensity,
                    associated_entities=[mem.target] if mem.target else [],
                    tags=[mem.type.value],
                )
        
        # Create initial goals from stance/emotional state
        self._initialize_goals()
        
        logger.info(f"Enhanced agent initialized: {self.persona.name} ({type(enhanced).__name__})")
    
    def _initialize_goals(self) -> None:
        """Create initial goals based on persona state."""
        if not self._bdi_model:
            return
        
        # Goal based on stance
        stance_goals = {
            "strongly_positive": "Strongly support and promote the topic",
            "positive": "Support the topic when appropriate",
            "neutral": "Explore and understand multiple perspectives",
            "negative": "Critique and challenge the topic",
            "strongly_negative": "Oppose and undermine the topic",
        }
        
        stance_str = self.persona.stance.value if hasattr(self.persona.stance, 'value') else str(self.persona.stance)
        goal_desc = stance_goals.get(stance_str, "Engage with the topic")
        
        self._bdi_model.spawn_goal(
            desire_id=list(self._bdi_model.desires.keys())[0] if self._bdi_model.desires else "default",
            description=goal_desc,
            priority=GoalPriority.MEDIUM,
        )
    
    @property
    def enhanced_agent(self) -> Optional[BaseAgent]:
        """Access the enhanced agent."""
        return self._enhanced_agent
    
    # Comprehensive emotional valence for all 56 SocialActions
    _ACTION_VALENCE: dict[SocialAction, tuple[float, float]] = {
        # (valence, arousal)
        SocialAction.POST: (0.05, 0.3),
        SocialAction.REPLY: (0.05, 0.25),
        SocialAction.AGREE: (0.30, 0.2),
        SocialAction.DISAGREE: (-0.25, 0.4),
        SocialAction.EXPAND: (0.15, 0.3),
        SocialAction.CHALLENGE: (-0.20, 0.55),
        SocialAction.SYNTHESIZE: (0.20, 0.3),
        SocialAction.FORESHADOW: (0.05, 0.35),
        SocialAction.CALLBACK: (0.10, 0.2),
        SocialAction.WORLDBUILD: (0.15, 0.3),
        SocialAction.CHARACTERIZE: (0.10, 0.25),
        SocialAction.CONFLICT: (-0.35, 0.7),
        SocialAction.RESOLVE: (0.30, 0.3),
        SocialAction.THEME: (0.10, 0.2),
        SocialAction.OUTLINE: (0.05, 0.2),
        SocialAction.WHISPER: (0.15, 0.4),
        SocialAction.LEAK_SECRET: (-0.10, 0.6),
        # InWorld - Character
        SocialAction.MOVE: (0.00, 0.2),
        SocialAction.SPEAK: (0.05, 0.25),
        SocialAction.ACT: (0.05, 0.3),
        SocialAction.USE_ITEM: (0.05, 0.25),
        SocialAction.GATHER_INTEL: (0.10, 0.4),
        SocialAction.KISS: (0.50, 0.6),
        SocialAction.HUG: (0.35, 0.4),
        SocialAction.APPRECIATE: (0.25, 0.3),
        SocialAction.PRAISE: (0.20, 0.3),
        SocialAction.CRY: (-0.30, 0.7),
        SocialAction.FLEE: (-0.40, 0.8),
        # InWorld - Strategist
        SocialAction.INITIATE_CONFLICT: (-0.20, 0.7),
        SocialAction.FORM_ALLIANCE: (0.30, 0.4),
        SocialAction.SABOTAGE: (-0.15, 0.55),
        SocialAction.DEPLOY_RESOURCES: (0.05, 0.3),
        SocialAction.SCHEME: (-0.05, 0.5),
        SocialAction.WAGE_WAR: (-0.30, 0.8),
        SocialAction.ASSASSINATE: (-0.40, 0.75),
        SocialAction.NEGOTIATE: (0.20, 0.4),
        # InWorld - Historian
        SocialAction.RECORD_LORE: (0.10, 0.2),
        SocialAction.UNCOVER_SECRET: (0.15, 0.55),
        SocialAction.PROPHESY: (0.05, 0.5),
        SocialAction.CHRONICLE: (0.10, 0.2),
        SocialAction.MOURN_LOSS: (-0.40, 0.6),
        SocialAction.CELEBRATE_TRIUMPH: (0.40, 0.7),
        # InWorld - Critic
        SocialAction.AUDIT_NARRATIVE: (0.05, 0.3),
        SocialAction.THEMATIC_INTERVENTION: (0.10, 0.4),
        SocialAction.STRUCTURAL_SHIFT: (-0.05, 0.45),
        SocialAction.PRAISE_DEVELOPMENT: (0.25, 0.35),
        SocialAction.CRITICIZE_ACTION: (-0.20, 0.5),
        # InWorld - Character Arc Planner
        SocialAction.TRIGGER_TRANSFORMATION: (0.20, 0.6),
        SocialAction.CREATE_DILEMMA: (-0.15, 0.6),
        SocialAction.EMOTIONAL_CATALYST: (0.15, 0.7),
        SocialAction.FORCE_BREAKTHROUGH: (0.25, 0.65),
        SocialAction.ORCHESTRATE_TRAGEDY: (-0.30, 0.7),
        # Universal InWorld
        SocialAction.ATTACK: (-0.30, 0.85),
        SocialAction.KILL: (-0.50, 0.9),
        SocialAction.REACT: (0.00, 0.4),
        SocialAction.BETRAY: (-0.45, 0.8),
    }

    def process_action(self, action: SocialAction, post: SimPost,
                      round_num: int) -> None:
        """
        Process an action through the enhanced architecture.

        Records to episodic memory, updates emotional state, updates BDI beliefs.
        """
        if not self._memory_system or not self._enhanced_agent or not self._bdi_model:
            return

        valence, arousal = self._ACTION_VALENCE.get(action, (0.0, 0.3))

        # Store in episodic memory
        self._memory_system.store_experience(
            description=f"{action.value}: {post.text[:150]}",
            round_num=round_num,
            emotional_valence=valence,
            emotional_arousal=arousal,
            importance=min(1.0, abs(valence) * 1.5 + 0.3),
            associated_agents=[post.reply_to] if post.reply_to else [],
            tags=[action.value],
        )

        # Update emotional state
        self._enhanced_agent.emotional_state.update_from_event(
            event_valence=valence,
            event_arousal=arousal,
            description=f"Performed {action.value}",
        )

        # Update BDI beliefs from action context
        if post.text:
            snippet = post.text[:120]
            # High-arousal actions form stronger beliefs
            confidence = 0.6 + abs(valence) * 0.3
            self._bdi_model.add_belief(
                content=f"In round {round_num} I performed {action.value}: {snippet}",
                confidence=confidence,
                source="observation",
            )

        # Update action count
        self._enhanced_agent.action_count += 1
        self._enhanced_agent.last_action_time = post.timestamp

        # Update goal progress if relevant
        active_goal = self._bdi_model.select_active_goal()
        if active_goal:
            self._bdi_model.update_goal_progress(active_goal.id, {"action": action.value})
    
    def get_decision_context(self, topic: str,
                            available_actions: list[SocialAction]) -> dict[str, Any]:
        """
        Generate comprehensive context for action selection.
        
        Combines memory, goals, and emotional state.
        """
        if not self._memory_system or not self._bdi_model or not self._enhanced_agent:
            return {"agent_id": self.persona.id, "name": self.persona.name, "error": "Systems not initialized"}
        
        # Get memory context
        memory_context = self._memory_system.recall_for_decision(topic, n_memories=5)
        
        # Get motivation context
        motivation = self._bdi_model.get_motivation_summary()
        
        # Get emotional context
        emotional = self._enhanced_agent.emotional_state
        
        # Get cognitive state
        should_deliberate = self._enhanced_agent.should_deliberate(
            topic_importance=0.7  # Default for now
        )
        
        return {
            "agent_id": self.persona.id,
            "name": self.persona.name,
            "role": self.persona.role,
            "platform": self.persona.platform.value,
            "cognitive_mode": "analytical" if should_deliberate else "intuitive",
            "emotional_state": {
                "mood": emotional.get_mood_label(),
                "pleasure": emotional.pleasure,
                "arousal": emotional.arousal,
            },
            "memory_context": memory_context,
            "motivation": motivation,
            "available_actions": [a.value for a in available_actions],
            "persona_summary": self.persona.personality_summary,
        }
    
    def generate_response_prompt(self, action: SocialAction, topic: str,
                                 context: dict[str, Any]) -> str:
        """
        Generate an enhanced prompt for the LLM using new architecture.
        
        Incorporates cognitive state, memories, and goals.
        """
        # Get appropriate method based on agent type
        if isinstance(self._enhanced_agent, CriticAgent):
            base_prompt = self._enhanced_agent.analyze_topic(topic, context)
        elif isinstance(self._enhanced_agent, StrategistAgent):
            base_prompt = self._enhanced_agent.plan_strategy(topic, context)
        elif isinstance(self._enhanced_agent, HistorianAgent):
            base_prompt = self._enhanced_agent.chronicle(topic, context)
        elif isinstance(self._enhanced_agent, CharacterArcPlannerAgent):
            base_prompt = self._enhanced_agent.plan_arc(topic, context)
        elif isinstance(self._enhanced_agent, CharacterAgent):
            base_prompt = self._enhanced_agent.respond_in_character(topic, context)
        else:
            base_prompt = f"You are {self.persona.name}. {self.persona.personality_summary}"
        
        # Enhance with memory context
        memory_summary = self._memory_system.generate_context_summary() if self._memory_system else ""
        
        # Enhance with motivation
        motivation = self._bdi_model.get_motivation_summary() if self._bdi_model else ""
        
        prompt_parts = [
            base_prompt,
            "",
            "=== YOUR CURRENT STATE ===",
            f"Action to perform: {action.value}",
            f"Cognitive mode: {context.get('cognitive_mode', 'balanced')}",
            f"Emotional state: {context.get('emotional_state', {}).get('mood', 'neutral')}",
            "",
        ]
        
        if motivation:
            prompt_parts.extend([
                "=== YOUR MOTIVATIONS ===",
                motivation,
                "",
            ])
        
        if memory_summary:
            prompt_parts.extend([
                "=== YOUR MEMORIES ===",
                memory_summary,
                "",
            ])
        
        prompt_parts.append(
            "Respond in your authentic voice, considering your current state, "
            "motivations, and past experiences."
        )
        
        return "\n".join(prompt_parts)
    
    def update_relationship(self, other_agent_id: str, interaction_type: str,
                           sentiment: float) -> None:
        """Record and process an interaction with another agent."""
        if self._enhanced_agent:
            self._enhanced_agent.record_interaction(
            other_agent_id=other_agent_id,
            interaction_type=interaction_type,
            outcome="completed",
            sentiment=sentiment,
        )
    
    def get_relationship_with(self, other_agent_id: str) -> dict:
        """Get relationship data with another agent."""
        if self._enhanced_agent:
            return self._enhanced_agent.get_relationship_with(other_agent_id)
        return {"sentiment": 0.0, "interactions": 0, "last": None}
    
    def consolidate_memories(self) -> None:
        """Run memory consolidation."""
        if self._memory_system:
            self._memory_system.consolidate()
    
    def create_plan(self, goal_description: str) -> Optional[Plan]:
        """Create a plan for a goal."""
        if not self._bdi_model or not self._planner:
            return None
        
        # First create a BDI goal
        desire_id = list(self._bdi_model.desires.keys())[0] if self._bdi_model.desires else None
        if not desire_id:
            return None
        
        goal = self._bdi_model.spawn_goal(
            desire_id=desire_id,
            description=goal_description,
        )
        
        if not goal:
            return None
        
        # Create plan using planner
        plan = self._planner.plan_for_discussion_goal(
            goal_id=goal.id,
            goal_desc=goal_description,
            target_topic=goal_description,
            desired_outcome="engagement",
        )
        
        return plan
    
    def to_dict(self) -> dict:
        """Serialize adapter state."""
        enhanced_type = type(self._enhanced_agent).__name__ if self._enhanced_agent else "unknown"
        action_count = self._enhanced_agent.action_count if self._enhanced_agent else 0
        memory_count = len(self._memory_system.episodic.memories) if self._memory_system else 0
        active_goals = len([g for g in self._bdi_model.goals.values() 
                        if g.status.value == "active"]) if self._bdi_model else 0
        emotional_state = self._enhanced_agent.emotional_state.get_mood_label() if self._enhanced_agent else "unknown"
        return {
            "persona_id": self.persona.id,
            "enhanced_type": enhanced_type,
            "action_count": action_count,
            "memory_count": memory_count,
            "active_goals": active_goals,
            "emotional_state": emotional_state,
        }


class EnhancedAgentRegistry:
    """
    Registry for managing adapted agents in a simulation.
    
    Provides:
    - Agent lookup by ID
    - Batch operations on all adapted agents
    - Statistics and monitoring
    """
    
    def __init__(self):
        self.adapters: dict[str, AgentAdapter] = {}
    
    def register(self, persona: AgentPersona) -> AgentAdapter:
        """Register an agent and create its adapter."""
        adapter = AgentAdapter(persona)
        self.adapters[persona.id] = adapter
        return adapter
    
    def get(self, agent_id: str) -> Optional[AgentAdapter]:
        """Get adapter by agent ID."""
        return self.adapters.get(agent_id)
    
    def get_enhanced_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get enhanced agent by ID."""
        adapter = self.adapters.get(agent_id)
        if adapter:
            return adapter.enhanced_agent
        return None
    
    def process_action(self, agent_id: str, action: SocialAction,
                      post: SimPost, round_num: int) -> None:
        """Process an action for a specific agent."""
        adapter = self.adapters.get(agent_id)
        if adapter:
            adapter.process_action(action, post, round_num)
    
    def consolidate_all_memories(self) -> None:
        """Run memory consolidation for all agents."""
        for adapter in self.adapters.values():
            adapter.consolidate_memories()
    
    def get_all_contexts(self, topic: str,
                        available_actions: list[SocialAction]) -> dict[str, dict]:
        """Get decision contexts for all agents."""
        return {
            agent_id: adapter.get_decision_context(topic, available_actions)
            for agent_id, adapter in self.adapters.items()
        }
    
    def get_statistics(self) -> dict:
        """Get aggregate statistics."""
        stats = {
            "total_agents": len(self.adapters),
            "total_memories": 0,
            "total_actions": 0,
            "active_goals": 0,
            "emotional_distribution": {},
        }
        
        for adapter in self.adapters.values():
            data = adapter.to_dict()
            stats["total_memories"] += data.get("memory_count", 0)
            stats["total_actions"] += data.get("action_count", 0)
            stats["active_goals"] += data.get("active_goals", 0)
            
            mood = data.get("emotional_state", "unknown")
            stats["emotional_distribution"][mood] = \
                stats["emotional_distribution"].get(mood, 0) + 1
        
        return stats
    
    def clear(self) -> None:
        """Clear all adapters."""
        self.adapters.clear()
