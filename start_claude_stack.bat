@echo off
setlocal
title ClaudeAgent Coder - Start

rem ============================================================
rem  Startreihenfolge:  1) cc-switch   2) MCP + llama-server   3) Claude Code
rem ============================================================

set "CCSWITCH=D:\claudeAgent\cc-switch\cc-switch.exe"
set "STARTPY=D:\claudeAgent\Coder\start.py"
set "PYTHON=D:\claudeAgent\Coder\RepoMapper\venv\Scripts\python.exe"
set "CLAUDE=C:\Users\Startklar\.local\bin\claude.exe"

echo ============================================================
echo   ClaudeAgent Coder
echo   1) cc-switch   2) MCP + llama-server   3) Claude Code
echo ============================================================
echo.
echo Modelle (start.py):
echo   [1] Qwen2.5-Coder-7B-Instruct-Q4_K_M
echo   [2] Qwopus3.5-4B-Coder-MTP-Q8_0
echo   [3] gemma-4-E4B-it-heretic-Q4_K_M
echo   [4] Qwen3.8-2B-BF16
echo   [5] Gemma-4-E2B-Uncensored-HauhauCS-Aggressive-Q6_K_P
echo   [6] Qwopus-MoE-35B-A3B-APEX-I-Mini
echo   [7] Qwen3.6-35B-A3B-abliterated.IQ4_XS
echo.
set "MODEL="
set /p "MODEL=Modellnummer (1-7, Enter = 1): "
if "%MODEL%"=="" set "MODEL=1"

echo.
echo [1/3] cc-switch starten...
start "" "%CCSWITCH%"
timeout /t 3 /nobreak >nul

echo [2/3] Embedding (8512) + MCP (8001/8002/8003) + llama-server (8484) starten...
"%PYTHON%" "%STARTPY%" %MODEL%
if errorlevel 1 (
  echo [FEHLER] start.py ist fehlgeschlagen.
  pause
  exit /b 1
)

echo.
echo [3/3] Claude Code starten...
set "CLAUDE_CONFIG_DIR=D:\claudeAgent\claude-local"
"%CLAUDE%"

echo.
echo Claude Code beendet.
pause
