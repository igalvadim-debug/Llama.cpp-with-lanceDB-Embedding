@echo off
setlocal EnableExtensions
chcp 65001 >nul
title ClaudeAgent Coder - Start alles in einem Fenster mit Tabs

rem ============================================================
rem  start_all.bat - EIN Fenster (Windows Terminal) mit Tabs:
rem    1) MCP Filesystem :8001
rem    2) MCP RepoMapper :8002
rem    3) MCP LanceDB    :8003
rem    4) llama-server   :8484
rem    + Agenten-Tabs: Claude Code / opencode / Hermes Agent
rem
rem  Aufruf:
rem    start_all.bat                      -> interaktiv (Modell + Agenten waehlen)
rem    start_all.bat 1                    -> Modell 1, alle 3 Agenten
rem    start_all.bat 2 claude             -> Modell 2, nur Claude Code
rem    start_all.bat 3 claude,opencode    -> Modell 3, Claude + opencode
rem    start_all.bat 4 hermes             -> Modell 4, nur Hermes
rem    start_all.bat 5 none               -> Modell 5, ohne Agenten
rem ============================================================

set "CODER=D:\claudeAgent\Coder"
set "PYTHON=%CODER%\RepoMapper\venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

rem --- Pfade der Agenten (bei Bedarf an eigene Installation anpassen) ---
rem Claude Code:
if not defined CLAUDE_CMD   set "CLAUDE_CMD=C:\Users\Startklar\.local\bin\claude.exe"
rem Hermes Agent (hermes-agent): Pfad zur hermes.exe ODER Name im PATH:
if not defined HERMES_CMD   set "HERMES_CMD=hermes"
rem opencode liegt normal im PATH - nichts zu setzen.
rem Eigene Claude-Konfiguration (MCP/MCP-URLs etc.):
if not defined CLAUDE_CONFIG_DIR set "CLAUDE_CONFIG_DIR=D:\claudeAgent\claude-local"

if not exist "%CODER%\start.py" (
    echo [FEHLER] %CODER%\start.py nicht gefunden.
    pause
    exit /b 1
)

echo ============================================================
echo   ClaudeAgent Coder - Alles in EINEM Fenster mit Tabs
echo   Dienste: Filesystem^|RepoMapper^|LanceDB^|llama-server
echo   Agenten: Claude Code ^+ opencode ^+ Hermes
echo ============================================================
echo.

rem --- Modell auswaehlen (Parameter 1 oder interaktiv) ---
set "MODEL=%~1"
if "%MODEL%"=="" (
    echo Modelle:
    echo   [1] Qwen2.5-Coder-7B-Instruct-Q4_K_M
    echo   [2] Qwopus3.5-4B-Coder-MTP-Q8_0
    echo   [3] gemma-4-E4B-it-heretic-Q4_K_M
    echo   [4] Qwen3.8-2B-BF16
    echo   [5] Gemma-4-E2B-Uncensored-HauhauCS-Aggressive-Q6_K_P
    echo   [6] Qwopus-MoE-35B-A3B-APEX-I-Mini
    echo   [7] Qwen3.6-35B-A3B-abliterated.IQ4_XS
    set /p "MODEL=Modellnummer (1-7, Enter = 1): "
    if "%MODEL%"=="" set "MODEL=1"
)

rem --- Agenten auswaehlen (Parameter 2 oder interaktiv) ---
set "AGENTS=%~2"
if "%AGENTS%"=="" (
    echo.
    echo Agenten-Tabs:
    echo   [a] alle drei: claude,opencode,hermes   (Standard)
    echo   [c] nur Claude Code
    echo   [o] nur opencode
    echo   [h] nur Hermes Agent
    echo   [n] keine Agenten
    set "WAHL="
    set /p "WAHL=Auswahl (a/c/o/h/n, Enter = a): "
    if "%WAHL%"=="a" set "AGENTS=claude,opencode,hermes"
    if "%WAHL%"=="c" set "AGENTS=claude"
    if "%WAHL%"=="o" set "AGENTS=opencode"
    if "%WAHL%"=="h" set "AGENTS=hermes"
    if "%WAHL%"=="n" set "AGENTS=none"
    if "%AGENTS%"=="" set "AGENTS=claude,opencode,hermes"
)
if /i "%AGENTS%"=="all" set "AGENTS=claude,opencode,hermes"

rem --- opencode: lokale Konfiguration (API 8484 + MCP 8001/8002/8003) anlegen ---
if not exist "%USERPROFILE%\.config\opencode" mkdir "%USERPROFILE%\.config\opencode"
copy /y "%CODER%\opencode.json" "%USERPROFILE%\.config\opencode\opencode.json" >nul 2>&1

echo.
echo [START] Modell %MODEL%, Agenten: %AGENTS%
echo         (Embedding-Server 8512, Index-Pruefung, dann Windows-Terminal-Fenster)
"%PYTHON%" "%CODER%\start.py" %MODEL% %AGENTS%
if errorlevel 1 (
    echo.
    echo [FEHLER] start.py ist fehlgeschlagen - bitte Ausgabe oben pruefen.
    pause
    exit /b 1
)

echo.
echo Fertig. Das Windows-Terminal-Fenster enthaelt jetzt alle Tabs.
endlocal
exit /b 0
