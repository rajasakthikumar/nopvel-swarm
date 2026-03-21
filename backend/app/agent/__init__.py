"""
Enhanced Agent Architecture for NovelSwarm.

This module provides a comprehensive agent system with:
- Base agent class with cognitive modeling
- Multi-layer memory system (episodic, semantic, procedural)
- Goal-oriented behavior (BDI model)
- Planning and intention system
- Specialized agent types for different roles
- Adapter for integration with existing simulation
"""

from .base import BaseAgent, AgentState, CognitiveModel, EmotionalState
from .memory import MemorySystem, EpisodicMemory, SemanticMemory, ProceduralMemory, MemoryFragment
from .goals import Goal, Intention, Desire, Belief, BDIModel, GoalPriority, GoalStatus
from .planning import Plan, Action, Planner, PlanStatus, ActionStatus
from .specialized import CriticAgent, CharacterAgent, AnalystAgent, WorldBuilderAgent, create_specialized_agent
from .adapter import AgentAdapter, EnhancedAgentRegistry

__all__ = [
    # Base
    "BaseAgent",
    "AgentState", 
    "CognitiveModel",
    "EmotionalState",
    # Memory
    "MemorySystem",
    "EpisodicMemory",
    "SemanticMemory", 
    "ProceduralMemory",
    "MemoryFragment",
    # Goals
    "Goal",
    "Intention",
    "Desire",
    "Belief",
    "BDIModel",
    "GoalPriority",
    "GoalStatus",
    # Planning
    "Plan",
    "Action",
    "Planner",
    "PlanStatus",
    "ActionStatus",
    # Specialized
    "CriticAgent",
    "CharacterAgent",
    "AnalystAgent",
    "WorldBuilderAgent",
    "create_specialized_agent",
    # Adapter
    "AgentAdapter",
    "EnhancedAgentRegistry",
]
