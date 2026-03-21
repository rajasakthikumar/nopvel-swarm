@echo off
chcp 65001 >nul 2>&1
title NovelSwarm

echo.
echo   Starting NovelSwarm...
echo.

REM Start Neo4j if Docker is available
docker compose up -d neo4j 2>nul

REM Start backend in a new window
start "NovelSwarm Backend" cmd /k "cd backend && .venv\Scripts\activate && python run.py"

REM Wait for backend to start
echo   Waiting for backend to start...
timeout /t 3 /nobreak >nul

REM Start frontend in a new window
start "NovelSwarm Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo   Backend:   http://localhost:5001
echo   Frontend:  http://localhost:3000
echo   Neo4j:     http://localhost:7474
echo.
echo   Both services starting in separate windows.
echo   Close this window whenever you want.
echo.
timeout /t 5 /nobreak >nul
start http://localhost:3000
