"""Knowledge graph endpoints — extraction, building, querying."""
import json, os
from flask import Blueprint, request, jsonify, current_app
from app.services.entity_extractor import extract_entities

graph_bp = Blueprint("graph", __name__)


@graph_bp.route("/extract", methods=["POST"])
def extract():
    """Extract entities from lore text (Stage 1 of MiroFish pipeline)."""
    data = request.json
    lore = data.get("lore_text", "")
    if not lore.strip():
        return jsonify({"error": "No lore provided"}), 400

    kg = extract_entities(lore)

    return jsonify({
        "entities": [e.model_dump() for e in kg.entities],
        "relationships": [r.model_dump() for r in kg.relationships],
        "entity_count": len(kg.entities),
        "relationship_count": len(kg.relationships),
    })


@graph_bp.route("/build", methods=["POST"])
def build():
    """Build Neo4j knowledge graph from extracted entities (Stage 1b)."""
    data = request.json
    project_id = data.get("project_id")
    entities = data.get("entities", [])
    relationships = data.get("relationships", [])

    if not project_id:
        return jsonify({"error": "project_id required"}), 400

    from app.models.schemas import KnowledgeGraph, Entity, Relationship, EntityType

    kg = KnowledgeGraph(
        entities=[Entity(
            name=e["name"],
            type=EntityType(e.get("type", "concept")),
            description=e.get("description", ""),
            properties=e.get("properties", {}),
        ) for e in entities],
        relationships=[Relationship(
            source=r["source"], target=r["target"],
            type=r.get("type", "related_to"),
            description=r.get("description", ""),
            weight=r.get("weight", 1.0),
        ) for r in relationships],
    )

    gb = current_app.extensions.get("graph_builder")
    if gb:
        result = gb.build_graph(project_id, kg)
    else:
        result = {"status": "neo4j_unavailable", "message": "Graph stored in memory only"}

    # Save to disk as fallback
    proj_dir = os.path.join(current_app.config["UPLOAD_DIR"], "projects", project_id)
    os.makedirs(proj_dir, exist_ok=True)
    with open(os.path.join(proj_dir, "knowledge_graph.json"), "w") as f:
        json.dump(kg.model_dump(), f, indent=2, default=str)

    return jsonify(result)


@graph_bp.route("/query/<project_id>", methods=["GET"])
def query(project_id):
    """Get the full knowledge graph for visualization."""
    gb = current_app.extensions.get("graph_builder")
    if gb and gb.driver:
        result = gb.get_full_graph(project_id)
        return jsonify(result)

    # Fallback to disk
    kg_path = os.path.join(current_app.config["UPLOAD_DIR"], "projects", project_id, "knowledge_graph.json")
    if os.path.exists(kg_path):
        with open(kg_path) as f:
            kg = json.load(f)
        return jsonify({
            "nodes": [{"name": e["name"], "type": e["type"], "description": e["description"]} for e in kg.get("entities", [])],
            "edges": [{"source": r["source"], "target": r["target"], "type": r["type"]} for r in kg.get("relationships", [])],
        })

    return jsonify({"nodes": [], "edges": []})


@graph_bp.route("/search/<project_id>", methods=["GET"])
def search(project_id):
    """Search entities in the knowledge graph."""
    q = request.args.get("q", "")
    gb = current_app.extensions.get("graph_builder")
    if gb and gb.driver:
        results = gb.search_entities(project_id, q)
        return jsonify(results)
    return jsonify([])


@graph_bp.route("/entity/<project_id>/<entity_name>", methods=["GET"])
def get_entity(project_id, entity_name):
    """Get a specific entity with relationships."""
    gb = current_app.extensions.get("graph_builder")
    if gb and gb.driver:
        result = gb.query_entity(project_id, entity_name)
        if result:
            return jsonify(result)
    return jsonify({"error": "Not found"}), 404


@graph_bp.route("/entity/<project_id>", methods=["POST"])
def add_entity(project_id):
    """Add a new entity to the knowledge graph."""
    data = request.json or {}
    name = data.get("name", "")
    entity_type = data.get("type", "concept")
    description = data.get("description", "")
    if not name.strip():
        return jsonify({"error": "name required"}), 400
    gb = current_app.extensions.get("graph_builder")
    if gb:
        gb.add_entity(project_id, name, entity_type, description)
    return jsonify({"status": "ok", "name": name})


@graph_bp.route("/entity/<project_id>/<entity_name>", methods=["DELETE"])
def delete_entity(project_id, entity_name):
    """Delete an entity and all its relationships."""
    gb = current_app.extensions.get("graph_builder")
    if gb:
        gb.delete_entity(project_id, entity_name)
    return jsonify({"status": "deleted", "name": entity_name})


@graph_bp.route("/relationship/<project_id>", methods=["POST"])
def add_relationship(project_id):
    """Add a relationship between two entities."""
    data = request.json or {}
    source = data.get("source", "")
    target = data.get("target", "")
    rel_type = data.get("type", "related_to")
    description = data.get("description", "")
    if not source.strip() or not target.strip():
        return jsonify({"error": "source and target required"}), 400
    gb = current_app.extensions.get("graph_builder")
    if gb:
        gb.add_relationship(project_id, source, target, rel_type, description)
    return jsonify({"status": "ok", "source": source, "target": target, "type": rel_type})


@graph_bp.route("/relationship/<project_id>", methods=["DELETE"])
def delete_relationship(project_id):
    """Delete a relationship between two entities."""
    data = request.json or {}
    source = data.get("source", "")
    target = data.get("target", "")
    rel_type = data.get("type", "")
    if not source or not target:
        return jsonify({"error": "source and target required"}), 400
    gb = current_app.extensions.get("graph_builder")
    if gb:
        gb.delete_relationship(project_id, source, target, rel_type)
    return jsonify({"status": "deleted", "source": source, "target": target})
