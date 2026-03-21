"""
Enhanced Memory System with Episodic, Semantic, and Procedural memory layers.

Based on human memory models for more realistic agent behavior.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from enum import Enum
import time
import uuid
import heapq


class MemoryType(Enum):
    """Types of memory storage."""
    EPISODIC = "episodic"  # Events, experiences
    SEMANTIC = "semantic"  # Facts, knowledge
    PROCEDURAL = "procedural"  # Skills, how-to
    EMOTIONAL = "emotional"  # Emotional associations
    SOCIAL = "social"  # Relationship knowledge


@dataclass
class MemoryFragment:
    """
    A single memory unit with metadata for retrieval.
    
    Memories have:
    - Content: The actual information
    - Context: When/where/who was present
    - Emotional valence: How the agent felt
    - Importance: How significant (affects retention)
    - Access patterns: For retrieval prioritization
    """
    id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:8]}")
    memory_type: MemoryType = MemoryType.EPISODIC
    content: str = ""
    context: dict = field(default_factory=dict)
    
    # Temporal
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    
    # Affective
    emotional_valence: float = 0.0  # -1 (negative) to 1 (positive)
    emotional_arousal: float = 0.0  # 0 (calm) to 1 (intense)
    
    # Significance
    importance: float = 0.5  # 0-1, affects decay rate
    relevance_tags: list[str] = field(default_factory=list)
    
    # Associations
    associated_agents: list[str] = field(default_factory=list)
    associated_entities: list[str] = field(default_factory=list)
    related_memory_ids: list[str] = field(default_factory=list)
    
    # Access tracking
    access_count: int = 0
    
    def get_strength(self, current_time: Optional[float] = None) -> float:
        """
        Calculate memory strength based on:
        - Importance (base weight)
        - Recency (decay over time)
        - Access frequency (rehearsal)
        - Emotional intensity (flashbulb effect)
        """
        if current_time is None:
            current_time = time.time()
        
        # Base importance
        strength = self.importance
        
        # Decay based on time elapsed (higher importance = slower decay)
        age_hours = (current_time - self.created_at) / 3600
        decay_rate = 0.1 * (1.1 - self.importance)  # 0.01 to 0.1
        recency_factor = max(0.1, 1 - (age_hours * decay_rate))
        strength *= recency_factor
        
        # Boost from access (rehearsal strengthens memory)
        rehearsal_boost = min(0.3, self.access_count * 0.05)
        strength += rehearsal_boost
        
        # Emotional flashbulb effect
        if self.emotional_arousal > 0.7:
            strength += 0.2
        
        return min(1.0, strength)
    
    def access(self) -> None:
        """Mark memory as accessed (retrieval strengthens it)."""
        self.last_accessed = time.time()
        self.access_count += 1
    
    def matches_query(self, query: str, tags: Optional[list[str]] = None) -> float:
        """Calculate match score for a query."""
        score = 0.0
        query_lower = query.lower()
        
        # Content match
        if query_lower in self.content.lower():
            score += 0.5
        
        # Tag match
        if tags:
            matching_tags = set(self.relevance_tags) & set(tags)
            score += len(matching_tags) * 0.3
        
        # Context match
        for key, val in self.context.items():
            if isinstance(val, str) and query_lower in val.lower():
                score += 0.2
        
        return min(1.0, score)


class EpisodicMemory:
    """
    Event-based memory - 'what happened when'.
    
    Stores specific experiences with temporal ordering.
    Enables agents to recall specific conversations, decisions, outcomes.
    """
    
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.memories: dict[str, MemoryFragment] = {}
        self.chronological_order: list[str] = []
    
    def store(self, event_description: str, round_num: int,
              emotional_valence: float = 0.0,
              emotional_arousal: float = 0.0,
              importance: float = 0.5,
              associated_agents: Optional[list[str]] = None,
              associated_entities: Optional[list[str]] = None,
              context: Optional[dict] = None) -> MemoryFragment:
        """Store a new episodic memory."""
        memory = MemoryFragment(
            memory_type=MemoryType.EPISODIC,
            content=event_description,
            context=context or {"round": round_num},
            emotional_valence=emotional_valence,
            emotional_arousal=emotional_arousal,
            importance=importance,
            associated_agents=associated_agents or [],
            associated_entities=associated_entities or [],
        )
        
        self.memories[memory.id] = memory
        self.chronological_order.append(memory.id)
        
        # Enforce capacity with forgetting
        if len(self.memories) > self.capacity:
            self._forget_weakest()
        
        return memory
    
    def _forget_weakest(self) -> None:
        """Remove the weakest memory when at capacity."""
        if not self.memories:
            return
        
        # Find weakest
        weakest_id = min(
            self.memories.keys(),
            key=lambda mid: self.memories[mid].get_strength()
        )
        
        # Remove
        del self.memories[weakest_id]
        if weakest_id in self.chronological_order:
            self.chronological_order.remove(weakest_id)
    
    def recall_recent(self, n: int = 5, memory_type: Optional[MemoryType] = None) -> list[MemoryFragment]:
        """Recall N most recent memories."""
        ids = self.chronological_order[-n:]
        memories = [self.memories[mid] for mid in ids if mid in self.memories]
        
        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]
        
        # Mark as accessed
        for m in memories:
            m.access()
        
        return memories
    
    def recall_by_emotion(self, min_arousal: float = 0.5,
                          valence_range: Optional[tuple[float, float]] = None,
                          n: int = 5) -> list[MemoryFragment]:
        """Recall emotionally significant memories."""
        candidates = [
            m for m in self.memories.values()
            if m.emotional_arousal >= min_arousal
        ]
        
        if valence_range:
            min_v, max_v = valence_range
            candidates = [
                m for m in candidates
                if min_v <= m.emotional_valence <= max_v
            ]
        
        # Sort by strength
        candidates.sort(key=lambda m: m.get_strength(), reverse=True)
        
        result = candidates[:n]
        for m in result:
            m.access()
        
        return result
    
    def search(self, query: str, n: int = 5) -> list[MemoryFragment]:
        """Search memories by content similarity."""
        scored = [
            (m.matches_query(query), m)
            for m in self.memories.values()
        ]
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        result = [m for score, m in scored if score > 0][:n]
        for m in result:
            m.access()
        
        return result


class SemanticMemory:
    """
    Fact-based memory - 'what is true'.
    
    Stores general knowledge about the world, entities, relationships.
    Structured as a knowledge graph in the agent's mind.
    """
    
    def __init__(self):
        self.facts: dict[str, MemoryFragment] = {}
        self.entity_knowledge: dict[str, dict] = {}  # entity_name -> attributes
        self.category_index: dict[str, list[str]] = {}  # category -> memory_ids
    
    def store_fact(self, fact: str, category: str = "general",
                   confidence: float = 0.8,
                   source: Optional[str] = None,
                   associated_entities: Optional[list[str]] = None) -> MemoryFragment:
        """Store a semantic fact."""
        memory = MemoryFragment(
            memory_type=MemoryType.SEMANTIC,
            content=fact,
            context={
                "category": category,
                "confidence": confidence,
                "source": source,
            },
            importance=confidence,  # Higher confidence = more important
            relevance_tags=[category],
            associated_entities=associated_entities or [],
        )
        
        self.facts[memory.id] = memory
        
        # Index by category
        if category not in self.category_index:
            self.category_index[category] = []
        self.category_index[category].append(memory.id)
        
        return memory
    
    def learn_entity(self, entity_name: str, attributes: dict) -> None:
        """Learn about an entity, merging with existing knowledge."""
        if entity_name not in self.entity_knowledge:
            self.entity_knowledge[entity_name] = {}
        
        # Merge attributes
        self.entity_knowledge[entity_name].update(attributes)
    
    def recall_entity(self, entity_name: str) -> dict:
        """Recall all known information about an entity."""
        return self.entity_knowledge.get(entity_name, {})
    
    def query(self, category: Optional[str] = None,
              entity: Optional[str] = None,
              n: int = 5) -> list[MemoryFragment]:
        """Query semantic memory."""
        candidates = list(self.facts.values())
        
        if category:
            ids = self.category_index.get(category, [])
            candidates = [self.facts[mid] for mid in ids if mid in self.facts]
        
        if entity:
            candidates = [
                m for m in candidates
                if entity in m.associated_entities
            ]
        
        # Sort by strength
        candidates.sort(key=lambda m: m.get_strength(), reverse=True)
        
        result = candidates[:n]
        for m in result:
            m.access()
        
        return result


class ProceduralMemory:
    """
    Skill-based memory - 'how to do things'.
    
    Stores learned procedures, strategies, successful patterns.
    Enables agents to develop expertise over time.
    """
    
    def __init__(self):
        self.skills: dict[str, dict] = {}  # skill_name -> metadata
        self.strategies: list[MemoryFragment] = []
        self.success_patterns: list[dict] = []
    
    def learn_skill(self, skill_name: str, proficiency: float = 0.0,
                   description: str = "") -> None:
        """Learn or improve a skill."""
        if skill_name not in self.skills:
            self.skills[skill_name] = {
                "proficiency": proficiency,
                "description": description,
                "uses": 0,
                "successes": 0,
                "learned_at": time.time(),
            }
        else:
            # Improve existing
            current = self.skills[skill_name]["proficiency"]
            self.skills[skill_name]["proficiency"] = min(1.0, current + (proficiency * 0.1))
    
    def use_skill(self, skill_name: str, success: bool) -> float:
        """Use a skill, tracking success rate."""
        if skill_name not in self.skills:
            return 0.0
        
        self.skills[skill_name]["uses"] += 1
        if success:
            self.skills[skill_name]["successes"] += 1
        
        # Calculate current effectiveness
        skill = self.skills[skill_name]
        success_rate = skill["successes"] / skill["uses"] if skill["uses"] > 0 else 0
        proficiency = skill["proficiency"]
        
        return (proficiency * 0.7) + (success_rate * 0.3)
    
    def store_strategy(self, strategy_name: str, description: str,
                      context: str, success_rating: float) -> None:
        """Store a learned strategy."""
        memory = MemoryFragment(
            memory_type=MemoryType.PROCEDURAL,
            content=description,
            context={
                "strategy_name": strategy_name,
                "context": context,
                "success_rating": success_rating,
            },
            importance=success_rating,
            relevance_tags=["strategy", strategy_name, context],
        )
        
        self.strategies.append(memory)
    
    def get_best_strategy(self, context: str) -> Optional[MemoryFragment]:
        """Get the best strategy for a given context."""
        relevant = [
            m for m in self.strategies
            if context.lower() in m.context.get("context", "").lower()
        ]
        
        if not relevant:
            return None
        
        # Sort by success rating
        relevant.sort(
            key=lambda m: m.context.get("success_rating", 0),
            reverse=True
        )
        
        best = relevant[0]
        best.access()
        return best
    
    def get_skill_proficiency(self, skill_name: str) -> float:
        """Get current proficiency in a skill."""
        if skill_name not in self.skills:
            return 0.0
        return self.skills[skill_name]["proficiency"]


class MemorySystem:
    """
    Unified memory system combining all memory types.
    
    Provides:
    - Coordinated storage across memory types
    - Cross-memory retrieval
    - Consolidation (moving important episodic -> semantic)
    - Integration with emotional state
    """
    
    def __init__(self, agent_id: str, episodic_capacity: int = 100):
        self.agent_id = agent_id
        self.episodic = EpisodicMemory(capacity=episodic_capacity)
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.emotional_memories: list[MemoryFragment] = []
        
        # Working memory (very limited, currently active thoughts)
        self.working_memory_limit = 7
        self.working_memory: list[str] = []
    
    def store_experience(self, description: str, round_num: int,
                        emotional_valence: float = 0.0,
                        emotional_arousal: float = 0.0,
                        importance: float = 0.5,
                        associated_agents: Optional[list[str]] = None,
                        associated_entities: Optional[list[str]] = None,
                        tags: Optional[list[str]] = None) -> MemoryFragment:
        """Store a new experience (episodic memory)."""
        memory = self.episodic.store(
            event_description=description,
            round_num=round_num,
            emotional_valence=emotional_valence,
            emotional_arousal=emotional_arousal,
            importance=importance,
            associated_agents=associated_agents,
            associated_entities=associated_entities,
            context={"tags": tags or [], "round": round_num},
        )
        
        # If very emotional, also store in emotional memory
        if abs(emotional_valence) > 0.5 or emotional_arousal > 0.6:
            self.emotional_memories.append(memory)
            # Keep only most significant emotional memories
            if len(self.emotional_memories) > 20:
                self.emotional_memories.sort(
                    key=lambda m: abs(m.emotional_valence) + m.emotional_arousal,
                    reverse=True
                )
                self.emotional_memories = self.emotional_memories[:20]
        
        return memory
    
    def consolidate(self, memory_id: Optional[str] = None,
                   threshold: float = 0.8) -> None:
        """
        Consolidate episodic memories into semantic memory.
        
        Important/often-accessed episodic memories become general facts.
        """
        candidates = []
        
        if memory_id:
            if memory_id in self.episodic.memories:
                candidates.append(self.episodic.memories[memory_id])
        else:
            # Find high-strength episodic memories
            for mem in self.episodic.memories.values():
                if mem.get_strength() > threshold and mem.access_count > 2:
                    candidates.append(mem)
        
        for mem in candidates:
            # Extract general fact from specific experience
            fact = f"Learned from experience: {mem.content[:100]}..."
            self.semantic.store_fact(
                fact=fact,
                category="learned_experience",
                confidence=mem.importance,
                associated_entities=mem.associated_entities,
            )
    
    def recall_for_decision(self, current_topic: str,
                           associated_agents: Optional[list[str]] = None,
                           n_memories: int = 5) -> dict:
        """
        Comprehensive recall to inform a decision.
        
        Returns relevant memories from all types.
        """
        results = {
            "episodic": [],
            "semantic": [],
            "emotional": [],
            "strategic": [],
        }
        
        # Search episodic by topic and agents
        episodic_results = self.episodic.search(current_topic, n=n_memories)
        if associated_agents:
            for agent in associated_agents:
                agent_memories = [
                    m for m in self.episodic.memories.values()
                    if agent in m.associated_agents
                ]
                episodic_results.extend(agent_memories[:3])
        
        results["episodic"] = episodic_results[:n_memories]
        
        # Query semantic knowledge
        results["semantic"] = self.semantic.query(
            entity=current_topic if len(current_topic) < 50 else None,
            n=n_memories
        )
        
        # Get emotionally relevant memories
        results["emotional"] = self.episodic.recall_by_emotion(
            min_arousal=0.3,
            n=3
        )
        
        # Get relevant strategy
        strategy = self.procedural.get_best_strategy(current_topic)
        if strategy:
            results["strategic"] = [strategy]
        
        return results
    
    def add_to_working_memory(self, content: str) -> None:
        """Add item to working memory (limited capacity)."""
        self.working_memory.append(content)
        if len(self.working_memory) > self.working_memory_limit:
            self.working_memory.pop(0)
    
    def get_working_memory(self) -> list[str]:
        """Get current working memory contents."""
        return self.working_memory.copy()
    
    def generate_context_summary(self, n_recent: int = 3) -> str:
        """Generate a summary of relevant memories for prompting."""
        parts = []
        
        # Recent experiences
        recent = self.episodic.recall_recent(n_recent)
        if recent:
            parts.append("RECENT EXPERIENCES:")
            for mem in recent:
                parts.append(f"- Round {mem.context.get('round', '?')}: {mem.content[:100]}")
        
        # Strong emotional memories that might be coloring judgment
        emotional = self.episodic.recall_by_emotion(min_arousal=0.7, n=2)
        if emotional:
            parts.append("\nSIGNIFICANT EMOTIONAL MEMORIES:")
            for mem in emotional:
                valence = "positive" if mem.emotional_valence > 0 else "negative"
                parts.append(f"- [{valence}, intense]: {mem.content[:80]}...")
        
        # Known facts about relevant entities
        if self.semantic.entity_knowledge:
            parts.append("\nENTITY KNOWLEDGE:")
            for entity, attrs in list(self.semantic.entity_knowledge.items())[:3]:
                parts.append(f"- {entity}: {str(attrs)[:80]}")
        
        return "\n".join(parts)
