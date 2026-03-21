"""
Enhanced Simulation Engine v4 with new agent architecture integration.

This integrates:
- Enhanced agent architecture (cognitive modeling, BDI, planning)
- Multi-layer memory systems
- Real-time analytics tracking
- Dashboard-compatible event streaming
"""

import random
import time
import json
import os
import logging
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Any
from dataclasses import dataclass, field

from app.services import llm_client
from app.config import Config
from app.models.schemas import (
    AgentPersona, SimPost, SocialAction, Platform, Stance,
    KnowledgeGraph, SimulationSession, SimulationState,
    LivingMemory, MemoryType, CharacterPromotion, ROLE_LADDER,
)
from app.agent.adapter import AgentAdapter, EnhancedAgentRegistry
from app.services.simulation_engine import select_action as _base_select_action

logger = logging.getLogger("novelswarm.simulation.enhanced")


@dataclass
class RoundMetrics:
    """Metrics for a single simulation round."""
    round_num: int
    agent_actions: dict[str, list[dict]] = field(default_factory=dict)
    emotional_states: dict[str, str] = field(default_factory=dict)
    topic_shifts: list[str] = field(default_factory=list)
    interaction_graph: dict[str, list[str]] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "round": self.round_num,
            "total_actions": sum(len(a) for a in self.agent_actions.values()),
            "emotional_distribution": self._count_emotions(),
            "topics": self.topic_shifts,
        }
    
    def _count_emotions(self) -> dict:
        counts = {}
        for mood in self.emotional_states.values():
            counts[mood] = counts.get(mood, 0) + 1
        return counts


@dataclass
class NarrativeArcPoint:
    """A single measurement of narrative tension and tone."""
    round_num: int
    tension_score: float       # 0.0 (calm) to 1.0 (crisis)
    conflict_count: int        # hostile actions this round
    resolution_count: int      # resolving/positive actions this round
    dominant_emotion: str      # most common emotional state
    arc_phase: str             # "rising", "climax", "falling", "resolution"

    def to_dict(self) -> dict:
        return {
            "round": self.round_num,
            "tension": round(self.tension_score, 3),
            "conflicts": self.conflict_count,
            "resolutions": self.resolution_count,
            "emotion": self.dominant_emotion,
            "phase": self.arc_phase,
        }


@dataclass
class SimulationAnalytics:
    """Analytics tracking for the entire simulation."""
    round_metrics: list[RoundMetrics] = field(default_factory=list)
    agent_lifecycles: dict[str, list[dict]] = field(default_factory=dict)
    topic_evolution: list[dict] = field(default_factory=list)
    relationship_changes: list[dict] = field(default_factory=list)
    token_usage_by_round: list[tuple[int, int]] = field(default_factory=list)
    narrative_arc: list[NarrativeArcPoint] = field(default_factory=list)

    # Tension thresholds for phase detection
    _HIGH_TENSION = 0.65
    _LOW_TENSION = 0.30

    def add_round(self, metrics: RoundMetrics) -> None:
        self.round_metrics.append(metrics)
        self._update_narrative_arc(metrics)

    # Hostile actions that raise tension
    _HOSTILE = {
        "conflict", "challenge", "disagree", "attack", "kill", "betray",
        "assassinate", "wage_war", "sabotage", "initiate_conflict",
        "leak_secret", "criticize_action", "orchestrate_tragedy",
        "create_dilemma", "flee", "structural_shift",
    }
    # Positive/resolving actions that lower tension
    _RESOLVE = {
        "agree", "resolve", "synthesize", "form_alliance", "negotiate",
        "hug", "kiss", "appreciate", "praise", "celebrate_triumph",
        "praise_development", "bond", "callback", "theme",
    }

    def _update_narrative_arc(self, metrics: RoundMetrics) -> None:
        """Compute tension and arc phase for the completed round."""
        all_actions = [
            a["action"]
            for actions in metrics.agent_actions.values()
            for a in actions
        ]
        total = max(len(all_actions), 1)
        conflict_n = sum(1 for a in all_actions if a in self._HOSTILE)
        resolve_n = sum(1 for a in all_actions if a in self._RESOLVE)

        # Tension: ratio of hostile vs total, smoothed with prior
        raw_tension = conflict_n / total
        prior_tension = self.narrative_arc[-1].tension_score if self.narrative_arc else 0.3
        tension = prior_tension * 0.4 + raw_tension * 0.6  # EMA smoothing

        # Dominant emotion
        emotions = list(metrics.emotional_states.values())
        dominant = max(set(emotions), key=emotions.count) if emotions else "neutral"

        # Arc phase detection using tension trajectory
        phase = "rising"
        if len(self.narrative_arc) >= 2:
            prev = self.narrative_arc[-1].tension_score
            if tension >= self._HIGH_TENSION and tension >= prev:
                phase = "climax"
            elif tension >= self._HIGH_TENSION and tension < prev:
                phase = "falling"
            elif tension < self._LOW_TENSION:
                phase = "resolution"
            elif tension > prev:
                phase = "rising"
            else:
                phase = "falling"
        elif tension >= self._HIGH_TENSION:
            phase = "climax"

        point = NarrativeArcPoint(
            round_num=metrics.round_num,
            tension_score=round(tension, 4),
            conflict_count=conflict_n,
            resolution_count=resolve_n,
            dominant_emotion=dominant,
            arc_phase=phase,
        )
        self.narrative_arc.append(point)

    def get_arc_summary(self) -> dict:
        """Return narrative arc data for dashboard."""
        if not self.narrative_arc:
            return {}
        latest = self.narrative_arc[-1]
        peak = max(self.narrative_arc, key=lambda p: p.tension_score)
        return {
            "current_phase": latest.arc_phase,
            "current_tension": latest.tension_score,
            "peak_tension_round": peak.round_num,
            "peak_tension": peak.tension_score,
            "arc_timeline": [p.to_dict() for p in self.narrative_arc],
        }

    def get_summary(self) -> dict:
        """Generate simulation summary statistics."""
        if not self.round_metrics:
            return {}

        total_actions = sum(
            sum(len(a) for a in r.agent_actions.values())
            for r in self.round_metrics
        )

        return {
            "total_rounds": len(self.round_metrics),
            "total_actions": total_actions,
            "avg_actions_per_round": total_actions / len(self.round_metrics),
            "topic_count": len(self.topic_evolution),
            "relationship_events": len(self.relationship_changes),
            "narrative_arc": self.get_arc_summary(),
        }


class EnhancedSimulationEngine:
    """
    Enhanced simulation engine with new agent architecture.
    
    Key improvements:
    - Uses AgentAdapter for enhanced cognitive capabilities
    - Real-time analytics tracking
    - Dashboard-compatible event streaming
    - Memory system integration
    - BDI goal tracking
    """
    
    def __init__(self, session, upload_dir, graph_builder=None, use_enhanced=True):
        self.session = session
        self.upload_dir = upload_dir
        self.graph_builder = graph_builder
        self.event_queue = queue.Queue()
        self._stop = self._pause = False
        self._lock = threading.Lock()
        
        # Enhanced agent registry
        self.use_enhanced = use_enhanced
        self.agent_registry = EnhancedAgentRegistry() if use_enhanced else None
        
        # Analytics
        self.analytics = SimulationAnalytics()
        self.current_round_metrics: Optional[RoundMetrics] = None
        
        # Simulation directory
        sim_dir = os.path.join(upload_dir, "simulations", session.id)
        os.makedirs(sim_dir, exist_ok=True)
        self.sim_dir = sim_dir
        self.action_log_path = os.path.join(sim_dir, "actions.jsonl")
        
        # Initialize enhanced agents if enabled
        if use_enhanced and self.agent_registry:
            for agent in session.agents:
                self.agent_registry.register(agent)
            logger.info(f"Enhanced simulation initialized with {len(session.agents)} agents")
    
    def emit(self, event_type: str, data: dict) -> None:
        """Emit event to queue with timestamp."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        self.event_queue.put(event)
    
    def log_action(self, post: SimPost) -> None:
        """Log action to file."""
        with open(self.action_log_path, "a") as f:
            f.write(json.dumps(post.model_dump(), default=str) + "\n")
    
    def inject(self, text: str) -> None:
        """Inject author message into simulation."""
        p = SimPost(
            author_id="god",
            author_name="Author (God's Eye)",
            platform=Platform.CRITICS_FORUM,
            action=SocialAction.POST,
            text=text,
            round=-1,
            is_injection=True,
        )
        self.session.posts.append(p)
        self.emit("injection", p.model_dump())
    
    def pause(self) -> bool:
        """Toggle pause state."""
        self._pause = not self._pause
        return self._pause
    
    def stop(self) -> None:
        """Stop simulation."""
        self._stop = True
    
    def _build_agent_prompt_enhanced(self, agent: AgentPersona, action: SocialAction,
                                     recent_posts: list[SimPost], injection: str = "") -> tuple[str, str]:
        """Build prompt using enhanced agent architecture."""
        if not self.agent_registry:
            return "", ""
        
        adapter = self.agent_registry.get(agent.id)
        if not adapter:
            return "", ""
        
        # Get decision context
        context = adapter.get_decision_context(
            topic=self._get_current_topic(),
            available_actions=list(SocialAction),
        )
        
        # Get target post for replies
        target_post = self._select_target_post(agent, action, recent_posts)
        if target_post:
            context["target_post"] = {
                "author": target_post.author_name,
                "text": target_post.text[:200],
            }
        
        # Generate enhanced prompt
        topic = self._get_current_topic()
        system_prompt = adapter.generate_response_prompt(action, topic, context)
        user_prompt = f"Perform action: {action.value}\nContext: {self._format_recent_posts(recent_posts[-6:])}"
        
        if injection:
            user_prompt += f"\n\n⚡ AUTHOR INJECTION: {injection}"
        
        return system_prompt, user_prompt
    
    def _get_current_topic(self) -> str:
        """Extract current topic from recent posts."""
        if not self.session.posts:
            return "general discussion"
        
        recent_text = " ".join(p.text[:100] for p in self.session.posts[-5:])
        # Simple keyword extraction - could be enhanced
        words = [w for w in recent_text.split() if len(w) > 5]
        if words:
            return max(set(words), key=words.count)
        return "general discussion"
    
    def _select_target_post(self, agent: AgentPersona, action: SocialAction,
                           recent_posts: list[SimPost]) -> Optional[SimPost]:
        """Select a post to reply to."""
        if action not in [SocialAction.REPLY, SocialAction.AGREE, SocialAction.DISAGREE,
                         SocialAction.CHALLENGE, SocialAction.EXPAND]:
            return None
        
        # Filter posts from same platform or public
        candidates = [
            p for p in recent_posts
            if p.platform == agent.platform and p.author_id != agent.id
        ]
        
        if not candidates:
            return None
        
        # Prefer posts that mention agent or are recent
        for post in reversed(candidates):
            if agent.name in post.text:
                return post
        
        return candidates[-1] if candidates else None
    
    def _format_recent_posts(self, posts: list[SimPost]) -> str:
        """Format recent posts for context."""
        lines = []
        for p in posts:
            lines.append(f"[{p.author_name}|{p.action.value}]: {p.text[:150]}")
        return "\n".join(lines)
    
    def _process_agent_enhanced(self, agent: AgentPersona, round_num: int,
                               injection: str) -> Optional[SimPost]:
        """Process a single agent with enhanced capabilities."""
        # Select action
        action = self._select_action(agent, round_num)
        target_post = self._select_target_post(agent, action, self.session.posts[-12:])
        
        # Emit start event
        self.emit("agent_start", {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "action": action.value,
            "round": round_num,
        })
        
        # Build prompts
        if self.use_enhanced and self.agent_registry:
            system_prompt, user_prompt = self._build_agent_prompt_enhanced(
                agent, action, self.session.posts[-12:], injection
            )
        else:
            # Fallback to basic prompts
            system_prompt = f"You are {agent.name}, {agent.role}"
            user_prompt = f"Action: {action.value}"
        
        try:
            # Call LLM
            response = llm_client.chat(
                [{"role": "user", "content": user_prompt}],
                system=system_prompt,
                temperature=0.7 + (agent.creativity * 0.2 if agent.creativity else 0.1),
            )
            
            # Create post
            post = SimPost(
                author_id=agent.id,
                author_name=agent.name,
                platform=agent.platform,
                action=action,
                text=response,
                round=round_num,
                reply_to=target_post.id if target_post else None,
            )
            
            # Process through enhanced architecture
            if self.agent_registry:
                self.agent_registry.process_action(agent.id, action, post, round_num)
            
            # Update session
            with self._lock:
                self.session.posts.append(post)
                self.log_action(post)
            
            # Update round metrics
            if self.current_round_metrics:
                if agent.id not in self.current_round_metrics.agent_actions:
                    self.current_round_metrics.agent_actions[agent.id] = []
                self.current_round_metrics.agent_actions[agent.id].append({
                    "action": action.value,
                    "text": response[:100],
                })
                
                # Track emotional state
                if self.agent_registry:
                    adapter = self.agent_registry.get(agent.id)
                    if adapter and adapter.enhanced_agent:
                        self.current_round_metrics.emotional_states[agent.id] = \
                            adapter.enhanced_agent.emotional_state.get_mood_label()
            
            # Emit completion
            self.emit("agent_post", {
                "post": post.model_dump(),
                "agent_update": {
                    "id": agent.id,
                    "action_count": sum(
                        1 for a in self.current_round_metrics.agent_actions.get(agent.id, [])
                    ) if self.current_round_metrics else 0,
                },
            })
            
            return post
            
        except Exception as e:
            logger.error(f"Agent {agent.name} error: {e}")
            self.emit("agent_error", {"agent_id": agent.id, "error": str(e)})
            return None
    
    def _select_action(self, agent: AgentPersona, round_num: int) -> SocialAction:
        """Select action using the full role- and platform-aware logic from the base engine."""
        return _base_select_action(agent, self.session.posts, round_num)
    
    def _spotlight_select(self, agents: list, round_num: int) -> list:
        """Select agents to act this round."""
        cap = getattr(self.session.config, 'max_active_per_round', 30)
        
        if len(agents) <= cap:
            return agents
        
        # Score by reaction speed and living memories
        def score(agent):
            base = agent.reaction_speed if hasattr(agent, 'reaction_speed') else 0.5
            if self.agent_registry:
                adapter = self.agent_registry.get(agent.id)
                if adapter and adapter.enhanced_agent:
                    # Boost by emotional arousal
                    base += adapter.enhanced_agent.emotional_state.arousal * 0.3
            return base + random.random() * 0.2
        
        scored = sorted(agents, key=score, reverse=True)
        return scored[:cap]
    
    def run(self):
        """Run the simulation."""
        self.session.state = SimulationState.RUNNING
        config = self.session.config
        
        self.emit("sim_start", {
            "rounds": config.rounds,
            "agents": len(self.session.agents),
            "enhanced": self.use_enhanced,
        })
        
        for round_num in range(config.rounds):
            if self._stop:
                break
            
            self.session.current_round = round_num
            
            # Initialize round metrics
            self.current_round_metrics = RoundMetrics(round_num=round_num)
            
            self.emit("round_start", {
                "round": round_num,
                "total": config.rounds,
            })
            
            # Select agents to act
            agents_to_act = self._spotlight_select(list(self.session.agents), round_num)
            
            # Get injection if any
            injection = ""
            with self._lock:
                # (Injection handling would go here)
                pass
            
            # Process agents in parallel
            with ThreadPoolExecutor(max_workers=Config.MAX_CONCURRENT_AGENTS) as executor:
                futures = {
                    executor.submit(self._process_agent_enhanced, agent, round_num, injection): agent
                    for agent in agents_to_act
                }
                
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        agent = futures[future]
                        logger.error(f"Thread error for {agent.name}: {e}")
            
            # Save round metrics + narrative arc update
            self.analytics.add_round(self.current_round_metrics)

            # Track token usage
            usage = llm_client.get_token_usage()
            self.analytics.token_usage_by_round.append((round_num, usage.get("total_tokens", 0)))

            # Emit round end with arc data
            arc_point = (
                self.analytics.narrative_arc[-1].to_dict()
                if self.analytics.narrative_arc else {}
            )
            self.emit("round_end", {
                "round": round_num,
                "metrics": self.current_round_metrics.to_dict(),
                "narrative_arc": arc_point,
            })

            # Emit a dedicated arc event when phase changes or tension spikes
            if len(self.analytics.narrative_arc) >= 2:
                prev_phase = self.analytics.narrative_arc[-2].arc_phase
                curr_phase = arc_point.get("phase", "")
                if prev_phase != curr_phase:
                    self.emit("arc_phase_change", {
                        "round": round_num,
                        "previous_phase": prev_phase,
                        "new_phase": curr_phase,
                        "tension": arc_point.get("tension", 0),
                    })

            # Consolidate agent memories every 3 rounds
            if (round_num + 1) % 3 == 0 and self.agent_registry:
                self.agent_registry.consolidate_all_memories()
                logger.info(f"Memory consolidation done at round {round_num}")

            # Save checkpoint every 5 rounds
            if (round_num + 1) % 5 == 0:
                self._save_checkpoint(round_num)
        
        # Simulation complete
        self.session.state = SimulationState.COMPLETED
        self._save_checkpoint(self.session.current_round)
        
        # Final analytics
        self.emit("sim_end", {
            "total_posts": len(self.session.posts),
            "analytics": self.analytics.get_summary(),
        })
    
    def _save_checkpoint(self, round_num: int) -> None:
        """Save simulation checkpoint."""
        checkpoint = {
            "round": round_num,
            "session": self.session.model_dump(),
            "analytics": self.analytics.get_summary(),
            "enhanced_stats": self._get_enhanced_stats() if self.agent_registry else {},
        }
        
        cp_path = os.path.join(self.sim_dir, "checkpoint.json")
        with open(cp_path, "w") as f:
            json.dump(checkpoint, f, default=str, indent=2)
        
        logger.info(f"Checkpoint saved at round {round_num}")
    
    def _get_enhanced_stats(self) -> dict:
        """Get enhanced agent statistics."""
        if not self.agent_registry:
            return {}
        
        return self.agent_registry.get_statistics()
    
    def get_agent_dashboard_data(self, agent_id: str) -> dict:
        """Get data for agent dashboard."""
        adapter = self.agent_registry.get(agent_id) if self.agent_registry else None
        if not adapter:
            return {"error": "Agent not found"}
        
        # Access private attributes directly since they exist
        persona_data = {}
        if hasattr(adapter, 'persona'):
            persona = adapter.persona
            persona_data = {
                "id": persona.id,
                "name": persona.name,
                "role": persona.role,
                "platform": persona.platform.value if hasattr(persona.platform, 'value') else str(persona.platform),
            }
        
        memory_summary = ""
        if hasattr(adapter, '_memory_system') and adapter._memory_system:
            memory_summary = adapter._memory_system.generate_context_summary()
        
        motivation = ""
        if hasattr(adapter, '_bdi_model') and adapter._bdi_model:
            motivation = adapter._bdi_model.get_motivation_summary()
        
        return {
            "persona": persona_data,
            "enhanced": adapter.to_dict(),
            "memory_summary": memory_summary,
            "motivation": motivation,
            "relationships": [
                adapter.get_relationship_with(other.id)
                for other in self.session.agents
                if other.id != agent_id
            ],
        }
    
    def get_analytics_data(self) -> dict:
        """Get full analytics data for dashboard."""
        return {
            "summary": self.analytics.get_summary(),
            "rounds": [r.to_dict() for r in self.analytics.round_metrics],
            "emotional_timeline": [
                {
                    "round": r.round_num,
                    "emotions": r.emotional_states,
                }
                for r in self.analytics.round_metrics
            ],
            "agent_participation": {
                agent.id: sum(
                    len(r.agent_actions.get(agent.id, []))
                    for r in self.analytics.round_metrics
                )
                for agent in self.session.agents
            },
            "narrative_arc": self.analytics.get_arc_summary(),
            "enhanced_agent_stats": self._get_enhanced_stats() if self.agent_registry else {},
        }
