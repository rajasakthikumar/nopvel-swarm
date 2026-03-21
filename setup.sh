#!/usr/bin/env bash
set -e

# ═══════════════════════════════════════════════════════════
# NovelSwarm Setup Script
# Tested on: Ubuntu 22.04+, Debian 12+, Fedora 39+, macOS 14+
# Hardware target: Ryzen 7 9700X + RTX 5060 Ti 16GB + 32GB DDR5
# ═══════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo "═══════════════════════════════════════════════"
echo "  🐟 NovelSwarm — Setup"
echo "  Swarm Intelligence Novel Engine"
echo "═══════════════════════════════════════════════"
echo ""

# ─── CHECK PREREQUISITES ───

info "Checking prerequisites..."

# Python
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
    PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
    PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)
    if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 11 ] && [ "$PY_MINOR" -le 12 ]; then
        ok "Python $PY_VERSION"
    else
        fail "Python 3.11 or 3.12 required (found $PY_VERSION). Use pyenv: pyenv install 3.12"
    fi
else
    fail "Python3 not found. Install: sudo apt install python3"
fi

# Node.js
if command -v node &>/dev/null; then
    NODE_VERSION=$(node -v | grep -oP '\d+' | head -1)
    if [ "$NODE_VERSION" -ge 18 ]; then
        ok "Node.js $(node -v)"
    else
        fail "Node.js 18+ required. Use nvm: nvm install 20"
    fi
else
    fail "Node.js not found. Install: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash && nvm install 20"
fi

# Docker
if command -v docker &>/dev/null; then
    ok "Docker $(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)"
else
    warn "Docker not found — Neo4j won't auto-start. Install: https://docs.docker.com/get-docker/"
fi

# Ollama
if command -v ollama &>/dev/null; then
    ok "Ollama installed"
else
    warn "Ollama not found — install: curl -fsSL https://ollama.com/install.sh | sh"
fi

echo ""

# ─── CONFIGURE ───

if [ ! -f .env ]; then
    info "Creating .env from template..."
    cp .env.example .env
    ok "Created .env — edit it if you need to change defaults"
else
    ok ".env already exists"
fi

echo ""

# ─── INSTALL OLLAMA MODELS ───

info "Checking Ollama models..."
if command -v ollama &>/dev/null; then
    # Check if LLM model is available
    MODEL=$(grep LLM_MODEL_NAME .env | cut -d= -f2 | tr -d ' "'"'"'')
    if [ -z "$MODEL" ]; then MODEL="qwen2.5:14b"; fi

    if ollama list 2>/dev/null | grep -q "$MODEL"; then
        ok "LLM model: $MODEL"
    else
        info "Pulling LLM model: $MODEL (this may take a while)..."
        ollama pull "$MODEL" || warn "Failed to pull $MODEL — pull manually: ollama pull $MODEL"
    fi

    # Check embedding model
    EMB_MODEL=$(grep EMBEDDING_MODEL .env | cut -d= -f2 | tr -d ' "'"'"'')
    if [ -z "$EMB_MODEL" ]; then EMB_MODEL="nomic-embed-text"; fi

    if ollama list 2>/dev/null | grep -q "$EMB_MODEL"; then
        ok "Embedding model: $EMB_MODEL"
    else
        info "Pulling embedding model: $EMB_MODEL..."
        ollama pull "$EMB_MODEL" || warn "Failed to pull $EMB_MODEL — pull manually: ollama pull $EMB_MODEL"
    fi
else
    warn "Ollama not available — skipping model setup"
fi

echo ""

# ─── START NEO4J ───

if command -v docker &>/dev/null; then
    info "Starting Neo4j via Docker..."
    docker compose up -d neo4j 2>/dev/null || docker-compose up -d neo4j 2>/dev/null || warn "Failed to start Neo4j"
    
    # Wait for Neo4j to be ready
    info "Waiting for Neo4j to be ready..."
    for i in $(seq 1 30); do
        if curl -s http://localhost:7474 &>/dev/null; then
            ok "Neo4j ready at http://localhost:7474"
            break
        fi
        sleep 2
        if [ $i -eq 30 ]; then
            warn "Neo4j not ready after 60s — check: docker logs novelswarm-neo4j"
        fi
    done
else
    warn "Skipping Neo4j (no Docker) — graph features will be disabled"
fi

echo ""

# ─── INSTALL BACKEND DEPENDENCIES ───

info "Setting up Python backend..."
cd backend

if [ ! -d .venv ]; then
    python3 -m venv .venv
    ok "Created virtual environment"
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q
ok "Backend dependencies installed"
cd ..

echo ""

# ─── INSTALL FRONTEND DEPENDENCIES ───

info "Setting up frontend..."
npm install --silent 2>/dev/null
cd frontend && npm install --silent 2>/dev/null && cd ..
ok "Frontend dependencies installed"

echo ""

# ─── VERIFY ───

info "Running verification..."

# Test backend starts
cd backend
source .venv/bin/activate
timeout 5 python3 -c "from app import create_app; app = create_app(); print('Flask OK')" 2>/dev/null && ok "Backend imports OK" || warn "Backend import issues"
cd ..

# Test Ollama connectivity
if command -v ollama &>/dev/null; then
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        ok "Ollama API reachable"
    else
        warn "Ollama API not reachable — start with: ollama serve"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  🐟 Setup complete!"
echo "═══════════════════════════════════════════════"
echo ""
echo "  To start everything:"
echo "    ${GREEN}npm run dev${NC}"
echo ""
echo "  Or start separately:"
echo "    ${CYAN}Terminal 1:${NC} cd backend && source .venv/bin/activate && python run.py"
echo "    ${CYAN}Terminal 2:${NC} cd frontend && npm run dev"
echo ""
echo "  URLs:"
echo "    Frontend:  ${GREEN}http://localhost:3000${NC}"
echo "    Backend:   ${GREEN}http://localhost:5001${NC}"
echo "    Neo4j:     ${GREEN}http://localhost:7474${NC} (neo4j/novelswarm)"
echo ""
echo "  First run:"
echo "    1. Go to http://localhost:3000"
echo "    2. Enter a seed like: 'A disabled prince discovers forbidden ash magic'"
echo "    3. Hit 'Spawn Swarm' and watch the magic"
echo ""
echo "  Hardware tips (RTX 5060 Ti 16GB):"
echo "    qwen2.5:14b  — best balance (~10GB VRAM, recommended)"
echo "    llama3.1:8b   — faster (~6GB VRAM)"
echo "    qwen2.5:7b    — lightest (~5GB VRAM)"
echo ""
