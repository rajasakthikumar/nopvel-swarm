# 🐟 NovelSwarm — MiroFish-Style Swarm Intelligence for Novel Writing

A multi-agent simulation engine adapted from the MiroFish architecture for **novel writing, lore enhancement, and outline generation**. Instead of simulating social media platforms, NovelSwarm simulates **writer's room discussions** and **in-world character debates** across dual platforms (a Critics' Forum and an In-World Forum).

## Architecture

```
NovelSwarm/
├── .env                          # Your config (Ollama, Neo4j, etc.)
├── .env.example                  # Template
├── docker-compose.yml            # Neo4j + app services
├── package.json                  # Root orchestration
│
├── backend/
│   ├── run.py                    # Entry point (Flask on :5001)
│   ├── pyproject.toml            # Python dependencies
│   ├── app/
│   │   ├── __init__.py           # Flask app factory
│   │   ├── config.py             # Config loader
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── projects.py       # Project CRUD + file upload
│   │   │   ├── graph.py          # Knowledge graph endpoints
│   │   │   ├── simulation.py     # Simulation control endpoints
│   │   │   └── report.py         # Report + deep interaction
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py     # Ollama / OpenAI-compat client
│   │   │   ├── entity_extractor.py  # LLM-based NER from lore
│   │   │   ├── graph_builder.py  # Neo4j knowledge graph pipeline
│   │   │   ├── ontology_generator.py # Novel-specific ontology
│   │   │   ├── persona_generator.py  # Agent persona creation
│   │   │   ├── simulation_engine.py  # Core swarm simulation loop
│   │   │   ├── report_agent.py   # ReACT report synthesis
│   │   │   └── neo4j_tools.py    # Graph query tools for agents
│   │   ├── simulation/
│   │   │   ├── __init__.py
│   │   │   ├── platforms.py      # Dual-platform definitions
│   │   │   ├── social_actions.py # 15 novel-specific social actions
│   │   │   ├── agent.py          # Agent class with memory
│   │   │   └── memory.py         # Per-agent persistent memory
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py        # Pydantic data models
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py
│   ├── uploads/                  # Project data persisted here
│   └── scripts/
│       └── run_simulation.py     # Standalone simulation runner
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue
        ├── views/
        │   ├── Home.vue          # Upload lore + start
        │   ├── GraphView.vue     # Knowledge graph visualization
        │   ├── SimulationView.vue # Live simulation monitor
        │   ├── ReportView.vue    # Generated report
        │   └── InteractionView.vue # Chat with agents
        ├── components/
        │   ├── AgentCard.vue
        │   ├── PostBubble.vue
        │   ├── GraphVisualization.vue
        │   └── InjectionBar.vue
        └── services/
            ├── api.js
            └── sse.js
```

## Key Differences from MiroFish

| MiroFish | NovelSwarm |
|----------|------------|
| Simulates Twitter + Reddit | Simulates **Critics' Forum** + **In-World Forum** |
| Agents are public opinion personas | Agents are **story characters** + **narrative critics** |
| Predicts social events | Generates **lore enhancements** + **chapter outlines** |
| Zep Cloud for memory | **Neo4j** local graph + **SQLite** for agent memory |
| OASIS framework (1M agents) | Custom simulation engine optimized for **narrative coherence** |
| DashScope/Qwen API | **Ollama** local inference (your RTX 5060 Ti 16GB) |
| Generic ontology | **Novel-specific ontology** (characters, factions, magic systems, arcs) |

## Dual-Platform Simulation

### Critics' Forum (Meta-narrative)
Agents debate the story from an **outside perspective** — plot structure, pacing, themes, character arcs, genre conventions. Think of it as a professional writer's room.

### In-World Forum (Diegetic)
Agents roleplay **as characters within the story world** — they debate events, form alliances, argue politics, spread rumors. This produces emergent world-building and reveals character relationships.

## 15 Novel-Specific Social Actions

```
POST       → Introduce a new narrative idea / lore element
REPLY      → Respond to another agent's point
AGREE      → Support with additional evidence from the lore
DISAGREE   → Challenge with counter-argument
EXPAND     → Deepen an idea with world-building details
CHALLENGE  → Devil's advocate — find the plot hole
SYNTHESIZE → Merge multiple threads into a coherent proposal
FORESHADOW → Plant a seed for future narrative payoff
CALLBACK   → Reference an earlier discussion point
WORLDBUILD → Add geography, culture, or system detail
CHARACTERIZE → Deepen a character's motivation or backstory
CONFLICT   → Introduce or escalate tension
RESOLVE    → Propose resolution to a narrative problem
THEME      → Draw thematic connections
OUTLINE    → Propose chapter/arc structure
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (for Neo4j) OR Neo4j Desktop
- Ollama with a model installed (recommended: `qwen2.5:14b` or `llama3.1:8b`)

### Setup

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your settings

# 2. Start Neo4j
docker compose up -d neo4j

# 3. Install dependencies
npm run setup:all

# 4. Start everything
npm run dev
```

Frontend: http://localhost:3000
Backend: http://localhost:5001

## Hardware Notes (for your build)

Your Ryzen 7 9700X + RTX 5060 Ti 16GB can comfortably run:
- **qwen2.5:14b** (best quality/speed balance) — ~10GB VRAM
- **llama3.1:8b** — ~6GB VRAM, faster, still good
- **qwen2.5:32b** via Q4 quantization — ~18GB, tight but possible with offloading

For 20-agent simulations with 30 rounds, expect:
- ~600 LLM calls per simulation
- ~15-30 minutes depending on model size
- ~4-8GB RAM for Neo4j + simulation state

## License

AGPL-3.0 (same as MiroFish)
