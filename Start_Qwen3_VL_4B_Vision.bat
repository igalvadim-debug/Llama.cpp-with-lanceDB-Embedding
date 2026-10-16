@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "LLAMA_SERVER=D:\Unsloth\C-claude\llama.cpp\llama-server.exe"
set "MAIN_MODEL=D:\ComfyUiVid\models\LLM\Qwen3-VL-4B-Instruct-abliterated.Q8_0.gguf"
set "MMPROJ=D:\ComfyUiVid\models\LLM\mmproj-F16.gguf"
set "PORT=8080"

set "PROJECT_DIR=D:\claudeAgent\Coder\projects\MyPythonScripts"
set "REPOMAPPER_DIR=D:\claudeAgent\Coder\RepoMapper"
set "REPOMAPPER_PY=%REPOMAPPER_DIR%\venv\Scripts\python.exe"

if not exist "%LLAMA_SERVER%" (
    echo [ERROR] llama-server.exe nicht gefunden: %LLAMA_SERVER%
    pause
    exit /b 1
)
if not exist "%MAIN_MODEL%" (
    echo [ERROR] Modell nicht gefunden: %MAIN_MODEL%
    pause
    exit /b 1
)
if not exist "%MMPROJ%" (
    echo [ERROR] mmproj nicht gefunden: %MMPROJ%
    pause
    exit /b 1
)
if not exist "%REPOMAPPER_PY%" (
    echo [ERROR] RepoMapper venv nicht gefunden: %REPOMAPPER_PY%
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   Qwen3-VL-4B (VISION) - llama-server + RepoMapper
echo   Port %PORT%  -  Context 65536 (q8_0 KV)  -  all layers GPU
echo ==================================================
echo.
echo Main model : %MAIN_MODEL%
echo MMProj     : %MMPROJ%
echo.

echo [1/3] Starte Filesystem MCP Proxy auf Port 8001...
start "MCP - Filesystem :8001" cmd /k "cd /d "%PROJECT_DIR%" && npx -y mcp-proxy@latest --port 8001 --stateless --server stream --shell npx.cmd @modelcontextprotocol/server-filesystem "%PROJECT_DIR%""
timeout /t 3 /nobreak >nul

echo [2/3] Starte RepoMapper MCP Proxy auf Port 8002...
start "MCP - RepoMapper :8002" cmd /k "cd /d "%REPOMAPPER_DIR%" && npx -y mcp-proxy@latest --port 8002 --stateless --server stream --shell "%REPOMAPPER_PY%" repomap_server.py"
timeout /t 3 /nobreak >nul

echo [3/3] Starte llama-server (Vision)...
echo.
echo Web UI: http://127.0.0.1:%PORT%
echo MCP URLs im llama.cpp Web UI:
echo   Filesystem: http://127.0.0.1:8001/mcp
echo   RepoMapper: http://127.0.0.1:8002/mcp
echo Fuer beide MCP Server: Authorization OFF, "Use llama-server proxy" ON
echo.

:: -ngl 99            : offload all LLM layers to GPU
:: --mmproj-offload   : also offload the vision encoder to GPU
:: --mmproj ...       : vision projector (projection_dim 2560 matches
::                      Qwen3-VL-4B embedding length - verified)
:: -c 65536           : erhoehter Kontext dank q8_0 KV-Cache.
::                      Q8_0-Gewichte + mmproj belegen bereits ~5.5-6.5GB
::                      auf der 8GB Karte, daher kein volles 131k/256k.
::                      Bei OOM auf -c 32768 zurueckgehen.
:: --cache-type-k/v q8_0 : halbiert KV-Cache-Speicherbedarf ggue. fp16
:: --port %PORT%      : OpenAI-compatible API -> http://localhost:%PORT%/v1
:: NOTE: same port as the Gemma bat - run only ONE server at a time,
::       or change PORT here.
"%LLAMA_SERVER%" -m "%MAIN_MODEL%" --mmproj "%MMPROJ%" --mmproj-offload -ngl 99 -c 65536 --cache-type-k q8_0 --cache-type-v q8_0 --port %PORT% --ui-mcp-proxy

echo.
echo Server stopped.
echo Schliesse auch die beiden MCP-Proxy-Fenster.
pause
endlocal
