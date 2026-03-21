"""
Enhanced simulation API endpoints for agent dashboard and analytics.

Provides:
- Agent state monitoring
- Real-time analytics
- Memory and goal visualization
- Relationship networks
"""

import json
import logging
from flask import Blueprint, jsonify, current_app
from app.services.enhanced_simulation_engine import EnhancedSimulationEngine

logger = logging.getLogger("novelswarm.api.enhanced")
enhanced_bp = Blueprint("enhanced", __name__)

# Reference to active enhanced engine (set by simulation start)
_active_enhanced_engine: EnhancedSimulationEngine | None = None


def set_active_enhanced_engine(engine: EnhancedSimulationEngine | None) -> None:
    """Set the active enhanced engine for API access."""
    global _active_enhanced_engine
    _active_enhanced_engine = engine


@enhanced_bp.route("/api/enhanced/agents/<agent_id>/dashboard", methods=["GET"])
def get_agent_dashboard(agent_id: str):
    """Get comprehensive dashboard data for an agent."""
    try:
        from app.api.pipeline_api import _active_pipeline
    except ImportError:
        _active_pipeline = None

    if not _active_enhanced_engine and not _active_pipeline:
        return jsonify({"error": "No active simulation"}), 404
    
    try:
        if _active_enhanced_engine:
            data = _active_enhanced_engine.get_agent_dashboard_data(agent_id)
            return jsonify(data)
        elif _active_pipeline:
            agent = next((a for a in _active_pipeline.agents if getattr(a, "id", getattr(a, "name", "")) == agent_id), None)
            if not agent:
                return jsonify({"error": "Agent not found"}), 404
            
            return jsonify({
                "persona": {
                    "id": getattr(agent, "id", getattr(agent, "name", "")),
                    "name": getattr(agent, "name", "Unknown"),
                    "role": getattr(agent, "role", "general"),
                    "platform": getattr(getattr(agent, "platform", ""), "value", str(getattr(agent, "platform", "critics_forum"))),
                },
                "enhanced": {
                    "state": "active",
                    "emotional_state": "Neutral",
                    "action_count": getattr(agent, "posts_count", 0),
                },
                "memory_summary": getattr(agent, "personality_summary", ""),
                "motivation": getattr(agent, "backstory", ""),
                "relationships": []
            })
    except Exception as e:
        logger.error(f"Error getting agent dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@enhanced_bp.route("/api/enhanced/agents", methods=["GET"])
def get_all_agents():
    """Get all agents with their enhanced states."""
    try:
        from app.api.pipeline_api import _active_pipeline
    except ImportError:
        _active_pipeline = None

    if not _active_enhanced_engine and not _active_pipeline:
        return jsonify({"error": "No active simulation"}), 404
    
    try:
        agents = []
        
        # If enhanced engine is running
        if _active_enhanced_engine:
            for agent in _active_enhanced_engine.session.agents:
                agent_data = {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "platform": agent.platform.value if hasattr(agent.platform, 'value') else str(agent.platform),
                    "stance": agent.stance.value if hasattr(agent.stance, 'value') else str(agent.stance),
                    "posts_count": agent.posts_count,
                    "replies_count": agent.replies_count,
                    "health": agent.health,
                    "location_id": agent.location_id,
                    "current_goal": agent.current_goal,
                    "inventory": agent.inventory,
                    "status_effects": agent.status_effects,
                }
                
                # Add enhanced data if available
                if _active_enhanced_engine.agent_registry:
                    adapter = _active_enhanced_engine.agent_registry.get(agent.id)
                    if adapter and adapter.enhanced_agent:
                        enhanced = adapter.enhanced_agent
                        agent_data["enhanced"] = {
                            "state": enhanced.state.value if hasattr(enhanced.state, 'value') else str(enhanced.state),
                            "emotional_state": enhanced.emotional_state.get_mood_label(),
                            "action_count": enhanced.action_count,
                        }
                
                agents.append(agent_data)
        
        # Fallback to pipeline agents
        elif _active_pipeline:
            for agent in _active_pipeline.agents:
                agent_data = {
                    "id": getattr(agent, "id", agent.name),
                    "name": agent.name,
                    "role": agent.role,
                    "platform": agent.platform.value if hasattr(agent.platform, 'value') else str(agent.platform),
                    "stance": agent.stance.value if hasattr(agent.stance, 'value') else str(agent.stance),
                    "posts_count": getattr(agent, "posts_count", 0),
                    "replies_count": getattr(agent, "replies_count", 0),
                    "health": getattr(agent, "health", 100),
                    "location_id": getattr(agent, "location_id", "nexus"),
                    "current_goal": getattr(agent, "current_goal", ""),
                    "inventory": getattr(agent, "inventory", []),
                    "status_effects": getattr(agent, "status_effects", []),
                    "enhanced": {
                        "state": "active",
                        "emotional_state": "Neutral",
                        "action_count": getattr(agent, "posts_count", 0),
                    }
                }
                agents.append(agent_data)
                
        return jsonify({"agents": agents, "count": len(agents)})
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        return jsonify({"error": str(e)}), 500


@enhanced_bp.route("/api/enhanced/analytics", methods=["GET"])
def get_analytics():
    """Get simulation analytics data."""
    if not _active_enhanced_engine:
        return jsonify({"error": "No active enhanced simulation"}), 404
    
    try:
        data = _active_enhanced_engine.get_analytics_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({"error": str(e)}), 500


@enhanced_bp.route("/api/enhanced/stats", methods=["GET"])
def get_enhanced_stats():
    """Get enhanced architecture statistics."""
    if not _active_enhanced_engine:
        return jsonify({"error": "No active enhanced simulation"}), 404
    
    try:
        stats = _active_enhanced_engine.agent_registry.get_statistics() \
                if _active_enhanced_engine.agent_registry else {}
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting enhanced stats: {e}")
        return jsonify({"error": str(e)}), 500


@enhanced_bp.route("/api/enhanced/relationships", methods=["GET"])
def get_relationship_network():
    """Get agent relationship network."""
    if not _active_enhanced_engine:
        return jsonify({"error": "No active enhanced simulation"}), 404
    
    try:
        nodes = []
        edges = []
        
        for agent in _active_enhanced_engine.session.agents:
            nodes.append({
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "platform": agent.platform.value if hasattr(agent.platform, 'value') else str(agent.platform),
            })
            
            # Get relationships
            if _active_enhanced_engine.agent_registry:
                adapter = _active_enhanced_engine.agent_registry.get(agent.id)
                if adapter:
                    for other in _active_enhanced_engine.session.agents:
                        if other.id != agent.id:
                            rel = adapter.get_relationship_with(other.id)
                            if rel.get("interactions", 0) > 0:
                                edges.append({
                                    "source": agent.id,
                                    "target": other.id,
                                    "sentiment": rel.get("sentiment", 0),
                                    "interactions": rel.get("interactions", 0),
                                })
        
        return jsonify({"nodes": nodes, "edges": edges})
    except Exception as e:
        logger.error(f"Error getting relationships: {e}")
        return jsonify({"error": str(e)}), 500


@enhanced_bp.route("/api/enhanced/emotions/timeline", methods=["GET"])
def get_emotion_timeline():
    """Get emotional state timeline across rounds."""
    if not _active_enhanced_engine:
        return jsonify({"error": "No active enhanced simulation"}), 404
    
    try:
        timeline = []
        for round_metrics in _active_enhanced_engine.analytics.round_metrics:
            emotion_counts = {}
            for mood in round_metrics.emotional_states.values():
                emotion_counts[mood] = emotion_counts.get(mood, 0) + 1
            
            timeline.append({
                "round": round_metrics.round_num,
                "emotions": emotion_counts,
            })
        
        return jsonify({"timeline": timeline})
    except Exception as e:
        logger.error(f"Error getting emotion timeline: {e}")
        return jsonify({"error": str(e)}), 500


@enhanced_bp.route("/api/enhanced/health", methods=["GET"])
def health_check():
    """Check if enhanced systems are active."""
    return jsonify({
        "active": _active_enhanced_engine is not None,
        "session_id": _active_enhanced_engine.session.id if _active_enhanced_engine else None,
        "round": _active_enhanced_engine.session.current_round if _active_enhanced_engine else None,
        "state": _active_enhanced_engine.session.state.value if _active_enhanced_engine else None,
    })
