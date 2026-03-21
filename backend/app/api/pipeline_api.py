"""Pipeline API — single endpoint to run the full Seed → World → Outline pipeline.

Includes export endpoints for downloading results as Markdown or JSON.
"""
import json
import logging
import os
import threading
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app.services.pipeline import StoryPipeline

logger = logging.getLogger("novelswarm.api.pipeline")
pipeline_bp = Blueprint("pipeline", __name__)
_active_pipeline: StoryPipeline | None = None


@pipeline_bp.route("/start", methods=["POST"])
def start():
    """Start the full pipeline from a seed."""
    global _active_pipeline
    data = request.json or {}
    seed = data.get("seed", "")
    project_id = data.get("project_id", "default")
    agent_count = min(int(data.get("agent_count", 0)), 50)  # 0 = dynamic
    debate_rounds = min(int(data.get("debate_rounds", 15)), 100)

    chapter_count = data.get("chapter_count", 35)
    actual_ending = data.get("actual_ending", "")
    genres = data.get("genres", "")
    pacing = data.get("pacing", "balanced")
    mood = data.get("mood", "neutral")
    god_mode = data.get("god_mode", False)

    if not seed.strip():
        return jsonify({"error": "No seed provided"}), 400
    if len(seed) > 100000:
        return jsonify({"error": "Seed text too long (max 100K chars)"}), 400

    gb = current_app.extensions.get("graph_builder")
    upload_dir = current_app.config["UPLOAD_DIR"]

    _active_pipeline = StoryPipeline(
        seed=seed, graph_builder=gb, project_id=project_id,
        upload_dir=upload_dir, agent_count=agent_count, debate_rounds=debate_rounds,
        chapter_count=chapter_count, actual_ending=actual_ending, genres=genres,
        pacing=pacing, mood=mood, god_mode=god_mode
    )
    _active_pipeline.run_async()

    return jsonify({"status": "started", "project_id": project_id})


@pipeline_bp.route("/inject", methods=["POST"])
def inject():
    """Inject a god-mode event into the active simulation or queue it."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"error": "No pipeline running"}), 404
    
    text = (request.json or {}).get("text", "")
    if not text.strip():
        return jsonify({"error": "No text provided"}), 400
        
    _active_pipeline.inject_event(text)
    return jsonify({"status": "injected", "text": text})


@pipeline_bp.route("/pause", methods=["POST"])
def pause():
    """Pause the active pipeline generation."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"error": "No pipeline running"}), 404
    _active_pipeline.pause()
    return jsonify({"status": "paused"})


@pipeline_bp.route("/resume", methods=["POST"])
def resume():
    """Resume a paused pipeline."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"error": "No pipeline running"}), 404
    _active_pipeline.resume()
    return jsonify({"status": "resumed"})


@pipeline_bp.route("/god-mode", methods=["POST"])
def toggle_god_mode():
    """Toggle God Mode (auto-pause between layers)."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"error": "No pipeline running"}), 404
    
    enabled = request.json.get("enabled", False)
    _active_pipeline.is_god_mode = enabled
    return jsonify({"status": "god_mode_updated", "enabled": enabled})


@pipeline_bp.route("/approve", methods=["POST"])
def approve():
    """Approve or edit the story spine to resume the pipeline."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"error": "No active pipeline"}), 404
        
    data = request.json or {}
    approved_spine = data.get("spine")
    if not approved_spine:
        return jsonify({"error": "No spine data provided"}), 400

    if _active_pipeline.state != "waiting_for_review":
        return jsonify({"error": "Pipeline is not in a waiting state"}), 400

    # Run resume in a background thread — generating the full outline takes minutes
    def _resume():
        try:
            _active_pipeline.resume_after_review(approved_spine)
        except Exception as e:
            logger.exception(f"Error in resume_after_review: {e}")

    threading.Thread(target=_resume, daemon=True).start()
    return jsonify({"status": "resuming"})


@pipeline_bp.route("/snapshot", methods=["POST"])
def snapshot():
    """Create a snapshot of the current pipeline state for later forking."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"error": "No pipeline running"}), 404
    label = (request.json or {}).get("label", "")
    snap = _active_pipeline.create_snapshot(label)
    return jsonify({"status": "snapshot_created", "label": snap["label"]})


@pipeline_bp.route("/fork", methods=["POST"])
def fork():
    """Fork a new alternate timeline from a snapshot."""
    global _active_pipeline
    data = request.json or {}
    snapshot_label = data.get("snapshot_label", "")
    new_project_id = data.get("project_id", f"fork_{int(__import__('time').time())}")

    if not _active_pipeline:
        return jsonify({"error": "No pipeline available"}), 404

    snap_path = _active_pipeline.snapshots.get(snapshot_label)
    if not snap_path:
        return jsonify({"error": f"Snapshot '{snapshot_label}' not found"}), 404

    gb = current_app.extensions.get("graph_builder")
    upload_dir = current_app.config["UPLOAD_DIR"]
    forked = StoryPipeline.fork_from_snapshot(snap_path, new_project_id, gb, upload_dir)

    return jsonify({
        "status": "forked",
        "new_project_id": new_project_id,
        "parent_project": forked.parent_project_id,
        "world_layers": len(forked.world_data),
        "agents": len(forked.agents),
    })


@pipeline_bp.route("/snapshots")
def list_snapshots():
    """List available snapshots for the active pipeline."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify([])
    return jsonify([{"label": k, "path": v} for k, v in _active_pipeline.snapshots.items()])



@pipeline_bp.route("/events")
def events():
    """SSE stream of all pipeline events — each client gets its own broadcast queue."""
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"error": "No pipeline running"}), 404

    pipe = _active_pipeline
    client_queue = pipe.subscribe()

    def generate():
        try:
            while True:
                try:
                    event = client_queue.get(timeout=30)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                    if event.get("type") in ("pipeline_complete", "pipeline_error"):
                        break
                except Exception:
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                    if pipe.state in ("completed", "error"):
                        break
        finally:
            pipe.unsubscribe(client_queue)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@pipeline_bp.route("/status")
def status():
    global _active_pipeline
    if not _active_pipeline:
        return jsonify({"state": "idle"})
    return jsonify({
        "state": _active_pipeline.state,
        "error": _active_pipeline.error,
        "world_layers": len(_active_pipeline.world_data),
        "debate_posts": len(_active_pipeline.debate_posts),
        "has_outline": bool(_active_pipeline.outline_markdown),
        "spine": _active_pipeline.outline_data.get("spine") if _active_pipeline.state == "waiting_for_review" else None,
        "token_usage": __import__("app.services.llm_client", fromlist=["get_token_usage"]).get_token_usage(),
    })


@pipeline_bp.route("/results/<project_id>")
def results(project_id):
    """Get all pipeline results."""
    upload_dir = current_app.config["UPLOAD_DIR"]
    proj_dir = os.path.join(upload_dir, "projects", project_id)

    result = {}
    for fname, key in [("expanded_seed.md", "expanded_seed"), ("world_data.json", "world"),
                        ("outline.md", "outline"), ("pipeline_result.json", "meta")]:
        path = os.path.join(proj_dir, fname)
        if os.path.exists(path):
            with open(path) as f:
                result[key] = json.load(f) if fname.endswith(".json") else f.read()
    return jsonify(result)


@pipeline_bp.route("/export/<project_id>/markdown")
def export_markdown(project_id):
    """Export the outline as a downloadable Markdown file."""
    upload_dir = current_app.config["UPLOAD_DIR"]
    outline_path = os.path.join(upload_dir, "projects", project_id, "outline.md")

    if not os.path.exists(outline_path):
        return jsonify({"error": "No outline found for this project"}), 404

    with open(outline_path) as f:
        content = f.read()

    return Response(
        content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=novel_outline_{project_id}.md"},
    )


@pipeline_bp.route("/export/<project_id>/json")
def export_json(project_id):
    """Export all pipeline data as a downloadable JSON file."""
    upload_dir = current_app.config["UPLOAD_DIR"]
    proj_dir = os.path.join(upload_dir, "projects", project_id)

    if not os.path.exists(proj_dir):
        return jsonify({"error": "Project not found"}), 404

    export_data = {"project_id": project_id}
    for fname, key in [("expanded_seed.md", "expanded_seed"), ("world_data.json", "world"),
                        ("outline.md", "outline"), ("pipeline_result.json", "meta"),
                        ("knowledge_graph.json", "knowledge_graph")]:
        path = os.path.join(proj_dir, fname)
        if os.path.exists(path):
            with open(path) as f:
                export_data[key] = json.load(f) if fname.endswith(".json") else f.read()

    return Response(
        json.dumps(export_data, indent=2, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=novelswarm_{project_id}.json"},
    )
