"""Project management endpoints."""
import os, json, time, uuid
from flask import Blueprint, request, jsonify, current_app
from app.models.schemas import Project

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/", methods=["POST"])
def create_project():
    data = request.json
    project = Project(
        name=data.get("name", "Untitled"),
        mode=data.get("mode", "lore"),
        lore_text=data.get("lore_text", ""),
        outline_text=data.get("outline_text", ""),
    )
    proj_dir = os.path.join(current_app.config["UPLOAD_DIR"], "projects", project.id)
    os.makedirs(proj_dir, exist_ok=True)

    with open(os.path.join(proj_dir, "project.json"), "w") as f:
        json.dump(project.model_dump(), f, indent=2)

    # Save lore as file
    if project.lore_text:
        with open(os.path.join(proj_dir, "lore.txt"), "w") as f:
            f.write(project.lore_text)

    return jsonify(project.model_dump())


@projects_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
    proj_path = os.path.join(current_app.config["UPLOAD_DIR"], "projects", project_id, "project.json")
    if not os.path.exists(proj_path):
        return jsonify({"error": "Not found"}), 404
    with open(proj_path) as f:
        return jsonify(json.load(f))


@projects_bp.route("/<project_id>/lore", methods=["PUT"])
def update_lore(project_id):
    proj_dir = os.path.join(current_app.config["UPLOAD_DIR"], "projects", project_id)
    if not os.path.exists(proj_dir):
        return jsonify({"error": "Not found"}), 404

    data = request.json
    lore = data.get("lore_text", "")

    with open(os.path.join(proj_dir, "lore.txt"), "w") as f:
        f.write(lore)

    # Update project.json
    proj_path = os.path.join(proj_dir, "project.json")
    with open(proj_path) as f:
        project = json.load(f)
    project["lore_text"] = lore
    with open(proj_path, "w") as f:
        json.dump(project, f, indent=2)

    return jsonify({"status": "updated"})


@projects_bp.route("/", methods=["GET"])
def list_projects():
    proj_root = os.path.join(current_app.config["UPLOAD_DIR"], "projects")
    projects = []
    if os.path.exists(proj_root):
        for pid in os.listdir(proj_root):
            pf = os.path.join(proj_root, pid, "project.json")
            if os.path.exists(pf):
                with open(pf) as f:
                    projects.append(json.load(f))
    projects.sort(key=lambda p: p.get("created_at", 0), reverse=True)
    return jsonify(projects)
