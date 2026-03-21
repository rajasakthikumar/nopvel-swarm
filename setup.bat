@echo off
chcp 65001 >nul 2>&1
title NovelSwarm Setup

echo.
echo ═══════════════════════════════════════════════
echo   NovelSwarm — Windows Setup
echo   Swarm Intelligence Novel Engine
echo ═══════════════════════════════════════════════
echo.

REM ─── CHECK PYTHON ───
echo [*] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python not found. Install from https://www.python.org/downloads/
    echo     IMPORTANT: Check "Add Python to PATH" during install
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] Python %PYVER%

REM ─── CHECK NODE ───
echo [*] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [X] Node.js not found. Install from https://nodejs.org/
    pause
    exit /b 1
)
for /f %%i in ('node --version') do set NODEVER=%%i
echo [OK] Node.js %NODEVER%

REM ─── CHECK OLLAMA ───
echo [*] Checking Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [!] Ollama not found. Install from https://ollama.com/download/windows
    echo     After installing, come back and run this script again.
    pause
    exit /b 1
)
echo [OK] Ollama installed

REM ─── CHECK DOCKER (optional) ───
echo [*] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [!] Docker not found — Neo4j won't auto-start.
    echo     Install Docker Desktop: https://www.docker.com/products/docker-desktop/
    echo     Or install Neo4j Desktop: https://neo4j.com/download/
    echo     Continuing without Neo4j graph DB ^(vector DB still works^)...
    set NO_DOCKER=1
) else (
    echo [OK] Docker found
    set NO_DOCKER=0
)

echo.

REM ─── CREATE .env ───
if not exist .env (
    echo [*] Creating .env from template...
    copy .env.example .env >nul
    echo [OK] Created .env
) else (
    echo [OK] .env already exists
)

echo.

REM ─── PULL OLLAMA MODELS ───
echo [*] Pulling Ollama models ^(this takes a while first time^)...
echo     LLM: qwen2.5:14b ^(~10GB, best for RTX 5060 Ti^)
echo     Embeddings: nomic-embed-text ^(~300MB^)
echo.

ollama pull nomic-embed-text
if errorlevel 1 (
    echo [!] Failed to pull nomic-embed-text. Make sure Ollama is running.
    echo     Start Ollama from the system tray or run: ollama serve
    pause
    exit /b 1
)
echo [OK] Embedding model ready

echo.
echo [*] Pulling LLM model ^(this is the big one^)...
ollama pull qwen2.5:14b
if errorlevel 1 (
    echo [!] Failed to pull qwen2.5:14b. Trying smaller model...
    ollama pull qwen2.5:7b
    if errorlevel 1 (
        echo [X] Cannot pull any model. Check Ollama is running and you have internet.
        pause
        exit /b 1
    )
    echo [!] Using qwen2.5:7b instead. Update LLM_MODEL_NAME in .env
)
echo [OK] LLM model ready

echo.

REM ─── START NEO4J ───
if "%NO_DOCKER%"=="0" (
    echo [*] Starting Neo4j via Docker...
    docker compose up -d neo4j 2>nul
    if errorlevel 1 (
        docker-compose up -d neo4j 2>nul
    )
    echo [*] Waiting for Neo4j...
    timeout /t 10 /nobreak >nul
    echo [OK] Neo4j starting at http://localhost:7474 ^(neo4j/novelswarm^)
) else (
    echo [!] Skipping Neo4j ^(no Docker^). Graph features disabled, vector DB still works.
)

echo.

REM ─── INSTALL BACKEND ───
echo [*] Setting up Python backend...
cd backend

if not exist .venv (
    echo [*] Creating virtual environment...
    py -3.11 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)

echo [*] Activating venv and installing dependencies...
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip -q
pip install -e . -q
if errorlevel 1 (
    echo [X] Backend install failed. Check Python version ^(need 3.11 or 3.12^)
    pause
    exit /b 1
)
echo [OK] Backend dependencies installed

cd ..

echo.

REM ─── INSTALL FRONTEND ───
echo [*] Setting up frontend...
call npm install --silent 2>nul
cd frontend
call npm install --silent 2>nul
cd ..
echo [OK] Frontend dependencies installed

echo.

REM ─── VERIFY ───
echo [*] Verifying setup...
cd backend
call .venv\Scripts\activate.bat
python -c "from app import create_app; app = create_app(); print('[OK] Backend imports work')" 2>nul
if errorlevel 1 (
    echo [!] Backend import has warnings ^(may still work^)
)
cd ..

echo.
echo ═══════════════════════════════════════════════
echo   Setup complete!
echo ═══════════════════════════════════════════════
echo.
echo   To start everything, run:
echo     start-novelswarm.bat
echo.
echo   Or start separately:
echo     Terminal 1: cd backend ^& .venv\Scripts\activate ^& python run.py
echo     Terminal 2: cd frontend ^& npm run dev
echo.
echo   URLs:
echo     Frontend:  http://localhost:3000
echo     Backend:   http://localhost:5001
echo     Neo4j:     http://localhost:7474 ^(neo4j/novelswarm^)
echo.
echo   First run:
echo     1. Go to http://localhost:3000
echo     2. Enter a seed: "A disabled prince discovers forbidden ash magic"
echo     3. Hit Spawn Swarm and watch
echo.
pause
