@echo off
echo ============================================
echo  NovelSwarm Setup (Windows)
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+ from nodejs.org
    pause
    exit /b 1
)

REM Copy .env if not exists
if not exist ".env" (
    echo [1/5] Creating .env from .env.example...
    copy .env.example .env >nul
    echo       Done. Edit .env if you need to change settings.
) else (
    echo [1/5] .env already exists, skipping...
)

REM Create Python virtual environment
echo [2/5] Creating Python virtual environment...
cd backend
if not exist ".venv" (
    py -3.11 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)
echo       Done.

REM Install Python dependencies
echo [3/5] Installing Python dependencies...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -e .
echo       Done.

cd ..

REM Install Node dependencies (frontend)
echo [4/5] Installing frontend dependencies...
cd frontend
call npm install --silent
cd ..

REM Install root Node dependencies
echo [5/5] Installing root dependencies...
call npm install --silent

echo.
echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo  To start NovelSwarm:
echo    npm run dev
echo.
echo  Frontend: http://localhost:3000
echo  Backend:  http://localhost:5001
echo.
echo  Optional: Start Neo4j (requires Docker):
echo    npm run neo4j
echo.
pause
