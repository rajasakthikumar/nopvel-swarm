"""Flask application factory."""
import os
import logging
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Load .env from multiple possible locations
for env_path in [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"),
]:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

logger = logging.getLogger("novelswarm")


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object("app.config.Config")

    # Configure logging (force=True overrides any handlers set by Flask/werkzeug before this point)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )

    # Ensure dirs
    upload_dir = app.config["UPLOAD_DIR"]
    for sub in ["projects", "simulations", "reports"]:
        os.makedirs(os.path.join(upload_dir, sub), exist_ok=True)

    # Initialize Neo4j (graceful — works without it)
    from app.services.graph_builder import GraphBuilder
    try:
        gb = GraphBuilder(
            uri=app.config["NEO4J_URI"],
            user=app.config["NEO4J_USER"],
            password=app.config["NEO4J_PASSWORD"],
        )
        # Only verify connectivity if not optional
        if not app.config.get("NEO4J_OPTIONAL", True):
            gb.driver  # Forces connection check
        app.extensions["graph_builder"] = gb
        logger.info("Neo4j graph builder initialized (lazy connection)")
    except Exception as e:
        logger.warning(f"Neo4j unavailable: {e}. Running without graph database.")
        app.extensions["graph_builder"] = None

    # Vector memory config
    app.config["CHROMA_PERSIST_DIR"] = app.config.get(
        "CHROMA_PERSIST_DIR",
        os.path.join(upload_dir, "chroma_data"),
    )

    # Register blueprints
    from app.api.projects import projects_bp
    from app.api.graph import graph_bp
    from app.api.simulation import simulation_bp
    from app.api.report import report_bp
    from app.api.worldgen import worldgen_bp
    from app.api.pipeline_api import pipeline_bp
    from app.api.enhanced import enhanced_bp
    from app.api.snowflake_api import snowflake_bp

    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(graph_bp, url_prefix="/api/graph")
    app.register_blueprint(simulation_bp, url_prefix="/api/simulation")
    app.register_blueprint(report_bp, url_prefix="/api/report")
    app.register_blueprint(worldgen_bp, url_prefix="/api/worldgen")
    app.register_blueprint(pipeline_bp, url_prefix="/api/pipeline")
    app.register_blueprint(enhanced_bp)
    app.register_blueprint(snowflake_bp, url_prefix="/api/snowflake")

    @app.route("/api/health")
    def health():
        gb = app.extensions.get("graph_builder")
        neo4j_ok = False
        if gb:
            try:
                neo4j_ok = gb.driver is not None
            except Exception:
                pass
        return {
            "status": "ok",
            "engine": "novel-swarm-v3",
            "neo4j": neo4j_ok,
            "neo4j_optional": app.config.get("NEO4J_OPTIONAL", True),
        }

    return app
