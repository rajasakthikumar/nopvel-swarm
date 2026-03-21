"""Simulation control endpoints — start, pause, stop, inject, SSE events.

Includes input validation and proper agent persona reconstruction.
"""
import json
import logging
import threading
import os
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app.models.schemas import (
    SimulationSession, SimulationConfig, SimulationState,
    KnowledgeGraph, Entity, Relationship, EntityType,
    AgentPersona, Platform, Stance, CognitiveProfile, LifeExperience,
)
from app.services.persona_generator import generate_personas
from app.services.simulation_engine import SimulationEngine
from app.config import Config

logger = logging.getLogger("novelswarm.api.simulation")
simulation_bp = Blueprint("simulation", __name__)

# Global state for active simulation
_active_engine: SimulationEngine | None = None
_active_thread: threading.Thread | None = None

# Validation limits — driven by config so they match .env settings
MAX_AGENTS = Config.MAX_AGENT_COUNT
MAX_ROUNDS = Config.MAX_ROUNDS


def _load_kg(project_id: str) -> KnowledgeGraph:
    """Load knowledge graph from disk."""
    upload_dir = os.getenv("UPLOAD_DIR", "uploads")
    for base in [upload_dir, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), upload_dir)]:
        kg_path = os.path.join(base, "projects", project_id, "knowledge_graph.json")
        if os.path.exists(kg_path):
            with open(kg_path) as f:
                data = json.load(f)
            return KnowledgeGraph(
                entities=[Entity(name=e["name"], type=EntityType(e.get("type", "concept")),
                                 description=e.get("description", ""), properties=e.get("properties", {}))
                          for e in data.get("entities", [])],
                relationships=[Relationship(source=r["source"], target=r["target"],
                                            type=r.get("type", "related_to"), description=r.get("description", ""))
                               for r in data.get("relationships", [])],
            )
    # Also check from app config
    try:
        app_upload = current_app.config["UPLOAD_DIR"]
        kg_path = os.path.join(app_upload, "projects", project_id, "knowledge_graph.json")
        if os.path.exists(kg_path):
            with open(kg_path) as f:
                data = json.load(f)
            return KnowledgeGraph(
                entities=[Entity(name=e["name"], type=EntityType(e.get("type", "concept")),
                                 description=e.get("description", ""), properties=e.get("properties", {}))
                          for e in data.get("entities", [])],
                relationships=[Relationship(source=r["source"], target=r["target"],
                                            type=r.get("type", "related_to"), description=r.get("description", ""))
                               for r in data.get("relationships", [])],
            )
    except Exception:
        pass
    return KnowledgeGraph()


def _reconstruct_agent(a: dict) -> AgentPersona:
    """Reconstruct a full AgentPersona from dict, preserving ALL deep characterization fields."""
    cog_data = a.get("cognitive", {})
    life_data = a.get("life", {})

    return AgentPersona(
        id=a.get("id", ""),
        name=a.get("name", "Unknown"),
        avatar=a.get("avatar", "🧙"),
        age=a.get("age", 30),
        race=a.get("race", "human"),
        gender=a.get("gender", "unknown"),
        role=a.get("role", "general"),
        platform=Platform(a.get("platform", "critics_forum")),
        personality_traits=a.get("personality_traits", []),
        personality_summary=a.get("personality_summary", ""),
        backstory=a.get("backstory", ""),
        expertise=a.get("expertise", []),
        speech_pattern=a.get("speech_pattern", ""),
        catchphrase=a.get("catchphrase", ""),
        quirks=a.get("quirks", []),
        cognitive=CognitiveProfile(
            intelligence=cog_data.get("intelligence", 100),
            education_level=cog_data.get("education_level", "average"),
            worldly_exposure=cog_data.get("worldly_exposure", "local"),
            reasoning_style=cog_data.get("reasoning_style", "balanced"),
            attention_span=cog_data.get("attention_span", "normal"),
            communication_style=cog_data.get("communication_style", "plain"),
            literacy=cog_data.get("literacy", True),
            speaks_in=cog_data.get("speaks_in", ""),
            cognitive_biases=cog_data.get("cognitive_biases", []),
            blind_spots=cog_data.get("blind_spots", []),
        ),
        life=LifeExperience(
            formative_event=life_data.get("formative_event", ""),
            greatest_achievement=life_data.get("greatest_achievement", ""),
            deepest_wound=life_data.get("deepest_wound", ""),
            social_class_origin=life_data.get("social_class_origin", "common"),
            current_social_position=life_data.get("current_social_position", ""),
            has_killed=life_data.get("has_killed", False),
            has_been_betrayed=life_data.get("has_been_betrayed", False),
            has_loved_and_lost=life_data.get("has_loved_and_lost", False),
            years_of_experience=life_data.get("years_of_experience", 0),
            traveled_places=life_data.get("traveled_places", []),
            languages_spoken=life_data.get("languages_spoken", []),
            mentors=life_data.get("mentors", []),
            enemies_made=life_data.get("enemies_made", []),
        ),
        grounded_entity=a.get("grounded_entity"),
        known_allies=a.get("known_allies", []),
        known_enemies=a.get("known_enemies", []),
        known_locations=a.get("known_locations", []),
        known_artifacts=a.get("known_artifacts", []),
        faction_membership=a.get("faction_membership"),
        graph_context_summary=a.get("graph_context_summary", ""),
        influence_level=a.get("influence_level", 0.5),
        reaction_speed=a.get("reaction_speed", 0.5),
        susceptibility=a.get("susceptibility", 0.3),
        creativity=a.get("creativity", 0.5),
        contentiousness=a.get("contentiousness", 0.3),
        stance=Stance(a.get("stance", "neutral")),
    )


@simulation_bp.route("/prepare", methods=["POST"])
def prepare():
    """Stage 2: Generate agent personas from knowledge graph."""
    data = request.json or {}
    project_id = data.get("project_id")
    if not project_id:
        return jsonify({"error": "project_id required"}), 400

    agent_count = min(int(data.get("agent_count", 12)), MAX_AGENTS)
    critics_ratio = max(0.1, min(0.9, float(data.get("critics_ratio", 0.5))))

    kg = _load_kg(project_id)
    gb = current_app.extensions.get("graph_builder") if current_app else None

    agents = generate_personas(kg, count=agent_count, critics_ratio=critics_ratio,
                               graph_builder=gb, project_id=project_id)

    return jsonify({
        "agents": [a.model_dump() for a in agents],
        "count": len(agents),
        "critics": len([a for a in agents if a.platform.value == "critics_forum"]),
        "inworld": len([a for a in agents if a.platform.value == "inworld_forum"]),
    })


@simulation_bp.route("/start", methods=["POST"])
def start():
    """Stage 3: Start the simulation with full persona reconstruction."""
    global _active_engine, _active_thread

    if _active_engine and _active_engine.session.state == SimulationState.RUNNING:
        return jsonify({"error": "Simulation already running"}), 409

    data = request.json or {}
    project_id = data.get("project_id")
    if not project_id:
        return jsonify({"error": "project_id required"}), 400

    mode = data.get("mode", "lore")
    rounds = min(int(data.get("rounds", 20)), MAX_ROUNDS)
    lore_text = data.get("lore_text", "")
    agents_data = data.get("agents", [])

    if not agents_data:
        return jsonify({"error": "No agents provided"}), 400
    if len(agents_data) > MAX_AGENTS:
        return jsonify({"error": f"Max {MAX_AGENTS} agents allowed"}), 400

    # Reconstruct full AgentPersona objects with ALL fields
    agents = [_reconstruct_agent(a) for a in agents_data]
    logger.info(f"Reconstructed {len(agents)} agents with full characterization")

    config = SimulationConfig(
        project_id=project_id,
        agent_count=len(agents),
        rounds=rounds,
        mode=mode,
        prediction_requirement=lore_text,
    )

    kg = _load_kg(project_id)
    session = SimulationSession(
        project_id=project_id,
        config=config,
        agents=agents,
        knowledge_graph=kg,
    )

    upload_dir = current_app.config["UPLOAD_DIR"]
    gb = current_app.extensions.get("graph_builder")

    _active_engine = SimulationEngine(session, upload_dir, graph_builder=gb)
    _active_thread = threading.Thread(target=_active_engine.run, daemon=True)
    _active_thread.start()

    return jsonify({
        "status": "started",
        "session_id": session.id,
        "agents": len(agents),
        "rounds": rounds,
    })


@simulation_bp.route("/events")
def events():
    """SSE endpoint — streams simulation events to frontend in real-time."""
    global _active_engine

    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404

    engine = _active_engine

    def generate():
        while True:
            try:
                event = engine.event_queue.get(timeout=30)
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") == "sim_end":
                    break
            except Exception:
                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@simulation_bp.route("/inject", methods=["POST"])
def inject():
    """God's Eye — inject a variable into the running simulation."""
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404
    text = (request.json or {}).get("text", "")
    if not text.strip():
        return jsonify({"error": "Empty injection text"}), 400
    if len(text) > 2000:
        return jsonify({"error": "Injection text too long (max 2000 chars)"}), 400
    _active_engine.inject(text)
    return jsonify({"status": "injected"})


@simulation_bp.route("/pause", methods=["POST"])
def pause():
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404
    paused = _active_engine.pause()
    return jsonify({"paused": paused})


@simulation_bp.route("/stop", methods=["POST"])
def stop():
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404
    _active_engine.stop()
    return jsonify({"status": "stopping"})


@simulation_bp.route("/state", methods=["GET"])
def state():
    """Get current simulation state."""
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404
    s = _active_engine.session
    return jsonify({
        "state": s.state.value,
        "current_round": s.current_round,
        "total_posts": len(s.posts),
        "agents": [a.model_dump() for a in s.agents],
        "token_usage": __import__("app.services.llm_client", fromlist=["get_token_usage"]).get_token_usage(),
    })


@simulation_bp.route("/spawn-agent", methods=["POST"])
def spawn_agent():
    """Dynamically spawn a new agent mid-simulation."""
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404

    data = request.json or {}
    if len(_active_engine.session.agents) >= MAX_AGENTS:
        return jsonify({"error": f"Max {MAX_AGENTS} agents reached"}), 400

    # Generate a new agent from the knowledge graph
    kg = _active_engine.session.knowledge_graph or KnowledgeGraph()
    gb = current_app.extensions.get("graph_builder")

    agents = generate_personas(
        kg, count=1,
        critics_ratio=1.0 if data.get("platform") == "critics_forum" else 0.0,
        graph_builder=gb, project_id=_active_engine.session.project_id,
    )

    if agents:
        new_agent = agents[0]
        _active_engine.session.agents.append(new_agent)
        from app.services.simulation_engine import AgentMemory
        db_path = os.path.join(_active_engine.sim_dir, "agent_memory.db")
        _active_engine.memories[new_agent.id] = AgentMemory(db_path, new_agent.id)
        _active_engine.emit("agent_spawned", {"agent": new_agent.model_dump()})
        logger.info(f"Dynamically spawned agent: {new_agent.name}")
        return jsonify({"status": "spawned", "agent": new_agent.model_dump()})

    return jsonify({"error": "Failed to generate agent"}), 500


@simulation_bp.route("/edit-post", methods=["POST"])
def edit_post():
    """Edit a post's text mid-simulation."""
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404
    data = request.json or {}
    post_id = data.get("post_id")
    new_text = data.get("text", "")
    if not post_id or not new_text:
        return jsonify({"error": "post_id and text required"}), 400
    for p in _active_engine.session.posts:
        if p.id == post_id:
            p.text = new_text
            _active_engine.emit("post_edited", {"post_id": post_id, "text": new_text})
            return jsonify({"status": "edited"})
    return jsonify({"error": "Post not found"}), 404


@simulation_bp.route("/edit-agent", methods=["POST"])
def edit_agent():
    """Edit agent parameters mid-simulation."""
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404
    data = request.json or {}
    agent_id = data.get("agent_id")
    updates = data.get("updates", {})
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400
    for a in _active_engine.session.agents:
        if a.id == agent_id:
            for key, val in updates.items():
                if hasattr(a, key) and key not in ("id", "platform"):
                    setattr(a, key, val)
            _active_engine.emit("agent_edited", {"agent_id": agent_id, "updates": updates})
            return jsonify({"status": "edited"})
    return jsonify({"error": "Agent not found"}), 404


@simulation_bp.route("/export", methods=["GET"])
def export_simulation():
    """Export simulation data as JSON."""
    global _active_engine
    if not _active_engine:
        return jsonify({"error": "No simulation"}), 404

    s = _active_engine.session
    export_data = {
        "session_id": s.id,
        "project_id": s.project_id,
        "state": s.state.value,
        "config": s.config.model_dump(),
        "agents": [a.model_dump() for a in s.agents],
        "posts": [p.model_dump() for p in s.posts],
        "emergent_entities": [e.model_dump() for e in s.emergent_entities],
        "character_promotions": [p.model_dump() for p in s.character_promotions],
        "token_usage": __import__("app.services.llm_client", fromlist=["get_token_usage"]).get_token_usage(),
    }

    return Response(
        json.dumps(export_data, indent=2, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=simulation_{s.id}.json"},
    )


@simulation_bp.route("/branch", methods=["POST"])
def branch():
    """Branch an existing project into a new alternate timeline project."""
    data = request.json or {}
    old_pid = data.get("project_id")
    if not old_pid:
        return jsonify({"error": "project_id required"}), 400

    import uuid, shutil, os
    new_pid = f"proj_{uuid.uuid4().hex[:8]}"

    # Copy Uploads Directory
    upload_dir = current_app.config["UPLOAD_DIR"]
    old_dir = os.path.join(upload_dir, "projects", old_pid)
    new_dir = os.path.join(upload_dir, "projects", new_pid)
    
    if os.path.exists(old_dir):
        try:
            shutil.copytree(old_dir, new_dir)
        except Exception as e:
            return jsonify({"error": f"Failed to copy project files: {e}"}), 500

    # Copy Neo4j Graph
    gb = current_app.extensions.get("graph_builder")
    if gb:
        gb.branch_project(old_pid, new_pid)

    # Copy Vector Memory
    from app.services.vector_memory import VectorMemory
    from app.config import Config
    VectorMemory.branch_project(old_pid, new_pid, Config.CHROMA_PERSIST_DIR)

    return jsonify({
        "status": "branched",
        "old_project_id": old_pid,
        "new_project_id": new_pid
    })

@simulation_bp.route("/heatmap/<project_id>", methods=["GET"])
def get_heatmap(project_id):
    """Return relationship graph for interactive heatmap."""
    if not _active_engine:
        return jsonify({"nodes": [], "links": []})
    
    nodes = []
    links = []
    
    # Agents as nodes
    for a in _active_engine.session.agents:
        nodes.append({"id": a.id, "name": a.name, "avatar": a.avatar, "group": a.role})
        
        # Check relationships
        rels = _active_engine.memories[a.id].get_relationships()
        for r in rels:
            links.append({
                "source": a.id,
                "target": r["other_id"],
                "value": abs(r["sentiment"]) * 10,
                "sentiment": r["sentiment"]
            })
            
    return jsonify({"nodes": nodes, "links": links})

@simulation_bp.route("/world-insert", methods=["POST"])
def world_insert():
    """Live insertion of world entities (Kingdom, Religion, Fauna, etc.) during simulation."""
    data = request.json
    project_id = data.get("project_id")
    entity_type = data.get("type")
    name = data.get("name")
    description = data.get("description", "")
    
    if not _active_engine:
        return jsonify({"error": "No active simulation"}), 400
        
    entity_data = {"name": name, "description": description, "type": entity_type}
    _active_engine.world_db.save_entity(project_id, entity_type, name, entity_data)
    
    # Broadcast to agents via global injection
    _active_engine.inject(f"[WORLD EVENT]: A new {entity_type} named '{name}' has emerged: {description}")
    
    return jsonify({"status": "entity_inserted", "id": name})
