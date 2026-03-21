"""World generation API — systematic layer-by-layer world building."""
import json, os, threading
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app.services.world_generator import WorldGenerator
from app.services.world_ontology import WorldLayer, LAYER_META, GENERATION_PHASES
from app.services.ontology_generator import OntologyGenerator

worldgen_bp = Blueprint("worldgen", __name__)

_active_generator: WorldGenerator | None = None
_gen_status = {"state": "idle", "current_layer": "", "progress": 0, "total": 0, "log": []}


@worldgen_bp.route("/layers", methods=["GET"])
def list_layers():
    """List all available world layers with their schemas."""
    layers = []
    for phase_idx, phase in enumerate(GENERATION_PHASES):
        for layer in phase:
            schema = LAYER_META[layer]
            layers.append({
                "id": layer.value,
                "phase": phase_idx,
                "fields": schema["fields"],
                "description": schema["prompt"],
            })
    return jsonify(layers)


@worldgen_bp.route("/generate", methods=["POST"])
def generate():
    """Generate world layers. Can select specific layers or generate all."""
    global _active_generator, _gen_status
    
    data = request.json
    project_id = data.get("project_id")
    lore = data.get("lore_text", "")
    selected_layers = data.get("layers", None)  # None = all, or list of layer IDs
    
    gb = current_app.extensions.get("graph_builder")
    _active_generator = WorldGenerator(graph_builder=gb, project_id=project_id)
    
    def progress(msg, current, total):
        _gen_status.update({"state": "generating", "current_layer": msg, "progress": current, "total": total})
    
    _gen_status = {"state": "starting", "current_layer": "", "progress": 0, "total": 0, "log": []}
    
    def run():
        try:
            if selected_layers:
                results = _active_generator.generate_selected(lore, selected_layers, progress)
            else:
                results = _active_generator.generate_all(lore, progress_callback=progress)
            
            # Save to disk
            upload_dir = current_app.config["UPLOAD_DIR"]
            proj_dir = os.path.join(upload_dir, "projects", project_id)
            os.makedirs(proj_dir, exist_ok=True)
            
            with open(os.path.join(proj_dir, "world_data.json"), "w") as f:
                json.dump(results, f, indent=2, default=str)
            
            # Also save the full knowledge graph
            kg = _active_generator.get_knowledge_graph()
            with open(os.path.join(proj_dir, "knowledge_graph.json"), "w") as f:
                json.dump(kg.model_dump(), f, indent=2, default=str)
            
            _gen_status.update({"state": "completed", "log": _active_generator.generation_log})
        except Exception as e:
            _gen_status.update({"state": "error", "error": str(e)})
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return jsonify({"status": "started", "layers": selected_layers or "all"})


@worldgen_bp.route("/status", methods=["GET"])
def status():
    """Get generation status."""
    return jsonify(_gen_status)


@worldgen_bp.route("/results/<project_id>", methods=["GET"])
def results(project_id):
    """Get generated world data."""
    upload_dir = current_app.config["UPLOAD_DIR"]
    path = os.path.join(upload_dir, "projects", project_id, "world_data.json")
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "No world data"}), 404


@worldgen_bp.route("/layer/<project_id>/<layer_id>", methods=["GET"])
def get_layer(project_id, layer_id):
    """Get data for a specific world layer."""
    upload_dir = current_app.config["UPLOAD_DIR"]
    path = os.path.join(upload_dir, "projects", project_id, "world_data.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return jsonify(data.get(layer_id, []))
    return jsonify([])


@worldgen_bp.route("/regenerate-layer", methods=["POST"])
def regenerate_layer():
    """Regenerate a single layer with new context from the swarm discussion."""
    global _active_generator
    data = request.json
    project_id = data.get("project_id")
    layer_id = data.get("layer_id")
    lore = data.get("lore_text", "")
    swarm_context = data.get("swarm_context", "")  # Injected from simulation discussion
    
    if not _active_generator:
        gb = current_app.extensions.get("graph_builder")
        _active_generator = WorldGenerator(graph_builder=gb, project_id=project_id)
        # Load existing world data
        upload_dir = current_app.config["UPLOAD_DIR"]
        path = os.path.join(upload_dir, "projects", project_id, "world_data.json")
        if os.path.exists(path):
            with open(path) as f:
                _active_generator.generated_layers = json.load(f)
    
    # Append swarm context to lore for richer generation
    enriched_lore = lore
    if swarm_context:
        enriched_lore += f"\n\nADDITIONAL CONTEXT FROM SWARM DISCUSSION:\n{swarm_context}"
    
    try:
        layer = WorldLayer(layer_id)
        result = _active_generator.generate_layer(layer, enriched_lore)
        
        # Update saved data
        upload_dir = current_app.config["UPLOAD_DIR"]
        path = os.path.join(upload_dir, "projects", project_id, "world_data.json")
        if os.path.exists(path):
            with open(path) as f:
                all_data = json.load(f)
        else:
            all_data = {}
        all_data[layer_id] = result
        with open(path, "w") as f:
            json.dump(all_data, f, indent=2, default=str)
        
        return jsonify({"layer": layer_id, "data": result, "count": len(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@worldgen_bp.route("/extract-ontology", methods=["POST"])
def extract_ontology():
    """Extract a simulation-ready ontology from lore or document text."""
    data = request.json or {}
    project_id = data.get("project_id")
    texts = data.get("texts", [])
    requirement = data.get("requirement", "Design an ontology for social media opinion simulation.")
    context = data.get("context", "")

    if not texts and project_id:
        # Load lore from project if no texts provided
        upload_dir = current_app.config["UPLOAD_DIR"]
        lore_path = os.path.join(upload_dir, "projects", project_id, "lore.txt")
        if os.path.exists(lore_path):
            with open(lore_path) as f:
                texts = [f.read()]

    if not texts:
        return jsonify({"error": "No text content provided for analysis"}), 400

    generator = OntologyGenerator()
    try:
        ontology = generator.generate(texts, requirement, context)
        
        # Optionally save the ontology to the project directory
        if project_id:
            upload_dir = current_app.config["UPLOAD_DIR"]
            proj_dir = os.path.join(upload_dir, "projects", project_id)
            os.makedirs(proj_dir, exist_ok=True)
            with open(os.path.join(proj_dir, "simulation_ontology.json"), "w") as f:
                json.dump(ontology, f, indent=2)

        return jsonify(ontology)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
