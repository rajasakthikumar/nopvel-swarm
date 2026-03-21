"""Application configuration — lazy-loaded from environment."""
import os


class Config:
    """Configuration loaded from environment variables.
    All values are read lazily via properties or at access time."""

    # LLM
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen2.5:14b")
    LLM_BOOST_MODEL = os.getenv("LLM_BOOST_MODEL", os.getenv("LLM_MODEL_NAME", "qwen2.5:14b"))

    # Embeddings
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434")

    # Neo4j
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "novelswarm")
    NEO4J_OPTIONAL = os.getenv("NEO4J_OPTIONAL", "true").lower() == "true"

    # ChromaDB
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_data"
    ))

    # Paths
    UPLOAD_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        os.getenv("UPLOAD_DIR", "uploads"),
    )

    # Simulation
    DEFAULT_AGENT_COUNT = int(os.getenv("DEFAULT_AGENT_COUNT", "12"))
    DEFAULT_ROUNDS = int(os.getenv("DEFAULT_ROUNDS", "20"))
    MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "4"))
    MAX_ACTIVE_AGENTS_PER_ROUND = int(os.getenv("MAX_ACTIVE_AGENTS_PER_ROUND", "30"))

    # Limits (for input validation)
    MAX_AGENT_COUNT = int(os.getenv("MAX_AGENT_COUNT", "5000"))
    MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "500"))
    MAX_LORE_LENGTH = int(os.getenv("MAX_LORE_LENGTH", "100000"))
