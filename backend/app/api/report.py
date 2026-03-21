"""Report generation and deep interaction endpoints (Stage 4 & 5)."""
import json, os
from flask import Blueprint, request, jsonify, current_app

report_bp = Blueprint("report", __name__)


@report_bp.route("/synthesize", methods=["POST"])
def synthesize():
    """Generate a report using the ReACT ReportAgent."""
    from app.api.simulation import _active_engine
    from app.services.report_agent import ReportAgent

    if not _active_engine:
        return jsonify({"error": "No simulation data"}), 404

    gb = current_app.extensions.get("graph_builder")
    agent = ReportAgent(_active_engine.session, graph_builder=gb)
    report = agent.generate_report()

    # Save report
    sim_dir = _active_engine.sim_dir
    reports_dir = os.path.join(sim_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    with open(os.path.join(reports_dir, "full_report.md"), "w") as f:
        f.write(report)

    with open(os.path.join(reports_dir, "agent_log.jsonl"), "w") as f:
        for entry in agent.tool_log:
            f.write(json.dumps(entry) + "\n")

    # Store for chat follow-up
    current_app.extensions["report_agent"] = agent

    return jsonify({
        "report": report,
        "sections": [s["title"] for s in agent.sections],
        "tool_calls": len(agent.tool_log),
    })


@report_bp.route("/chat", methods=["POST"])
def chat():
    """Chat with the ReportAgent about its findings."""
    agent = current_app.extensions.get("report_agent")
    if not agent:
        return jsonify({"error": "No report generated yet"}), 404

    data = request.json
    message = data.get("message", "")
    history = data.get("history", [])

    response = agent.chat(message, history)
    return jsonify({"response": response})


@report_bp.route("/interview", methods=["POST"])
def interview():
    """Interview a specific simulated agent."""
    agent = current_app.extensions.get("report_agent")
    if not agent:
        return jsonify({"error": "No report generated yet"}), 404

    data = request.json
    agent_id = data.get("agent_id", "")
    question = data.get("question", "What was your reasoning during the simulation?")

    response = agent.interview_agent(agent_id, question)
    return jsonify({"response": response, "agent_id": agent_id})
