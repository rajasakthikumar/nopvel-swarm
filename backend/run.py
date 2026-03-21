"""NovelSwarm backend entry point."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5001))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"NovelSwarm Engine starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
