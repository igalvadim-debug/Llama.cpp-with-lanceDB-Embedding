#!/usr/bin/env python3
"""
ClaudeAgent Coder - Alles-in-einem-Start (Python-Version)

Startet:
  1. LanceDB-Indexierung (lokaler Vektor-Speicher)
  2. Filesystem-MCP-Proxy   → Port 8001
  3. RepoMapper-MCP         → Port 8002
  4. LanceDB-MCP            → Port 8003
  5. llama-server           → Port 8484

Alle vier Server laufen als TABS in EINEM Windows-Terminal-Fenster
(statt vier Einzelfenster).

Modell 4 ist Qwen3.8-2B-BF16.gguf mit 32K Kontext.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Pfade anpassen falls nötig
# ---------------------------------------------------------------------------
ROOT = Path(r"D:\claudeAgent\Coder")
SERVER_EXE = Path(r"D:\Unsloth\C-claude\llama.cpp\llama-server.exe")
PROJECT_DIR = ROOT / "projects" / "QwenProject"
REPOMAPPER_DIR = ROOT / "RepoMapper"
VENV_PYTHON = REPOMAPPER_DIR / "venv" / "Scripts" / "python.exe"
HELPER_DIR = ROOT / "_start_helpers"
LANCEDB_MCP_DIR = ROOT / "lancedb_mcp"
LANCEDB_DB_PATH = ROOT / "lancedb_context"
WT_EXE = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WindowsApps" / "wt.exe"

MODELS = {
    "1": ROOT / "models" / "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "2": ROOT / "models" / "Qwopus3.5-4B-Coder-MTP-Q8_0.gguf",
    "3": ROOT / "models" / "gemma-4-E4B-it-heretic-Q4_K_M.gguf",
    "4": ROOT / "models" / "Qwen3.8-2B-BF16.gguf",
}

PORTS = (8001, 8002, 8003, 8484)


def banner() -> None:
    print()
    print("==========================================================")
    print("ClaudeAgent Coder - Alles in einem Start (Python)")
    print("==========================================================")
    print()


def choose_model() -> Path:
    print("Verfuegbare Modelle:")
    for key, path in MODELS.items():
        print(f"[{key}] {path.name}")
    print()

    while True:
        choice = input(f"Modell waehlen (1-{len(MODELS)}): ").strip()
        if choice in MODELS:
            model_path = MODELS[choice]
            break
        print("Ungueltige Auswahl. Bitte erneut versuchen.")

    print()
    print("Gewaehltes Modell:")
    print(model_path)
    print()
    return model_path


def check_prerequisites(model_path: Path) -> None:
    checks = [
        (SERVER_EXE, "llama-server.exe nicht gefunden"),
        (model_path, "Modelldatei nicht gefunden"),
        (VENV_PYTHON, "RepoMapper Python nicht gefunden"),
        (PROJECT_DIR, "Projektverzeichnis nicht gefunden"),
        (LANCEDB_MCP_DIR / "server.py", "LanceDB-MCP server.py nicht gefunden"),
        (WT_EXE, "Windows Terminal (wt.exe) nicht gefunden"),
    ]

    for path, message in checks:
        if not path.exists():
            print(f"[ERROR] {message}:")
            print(path)
            input("Enter zum Beenden druecken...")
            sys.exit(1)

    print("[OK] llama-server.exe")
    print("[OK] Modell")
    print("[OK] RepoMapper Python")
    print("[OK] Projektverzeichnis")
    print("[OK] LanceDB-MCP server.py")
    print("[OK] Windows Terminal")
    print()


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def find_pids_on_ports(ports: tuple[int, ...]) -> set[int]:
    """Findet lauschende Prozesse ALLER Ports in EINEM PowerShell-Aufruf.

    Ein einzelner Prozess-Start statt N Stueck spart mehrere Sekunden
    (PowerShell-Kaltstart ist der teure Teil); unabhaengig von der Windows-Sprache.
    """
    pids: set[int] = set()
    try:
        port_list = ",".join(str(p) for p in ports)
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-NetTCPConnection -LocalPort {{{port_list}}} -State Listen "
                f"-ErrorAction SilentlyContinue).OwningProcess",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        for line in result.stdout.splitlines():
            if line.strip().isdigit():
                pids.add(int(line.strip()))
    except Exception:
        pass
    return pids


def kill_old_processes() -> None:
    print(f"Beende alte Prozesse auf den Ports {', '.join(map(str, PORTS))}...")
    pids = sorted(find_pids_on_ports(PORTS))
    if not pids:
        print("[OK] Keine alten Prozesse gefunden.")
        print()
        return
    # taskkill kann mehrere /PID-Argumente in einem Aufruf verarbeiten
    cmd = ["taskkill", "/F"]
    for pid in pids:
        cmd += ["/PID", str(pid)]
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
    except Exception:
        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                pass
    print()


def code_in_lancedb_indexieren() -> None:
    """Zerlegt Python-Dateien in kleine Häppchen und speichert sie in LanceDB."""
    print("==========================================================")
    print("[LanceDB] Indexiere Projektverzeichnis...")
    print("==========================================================")

    try:
        import lancedb
        from lancedb.embeddings import get_registry
        from lancedb.pydantic import LanceModel, Vector

        db = lancedb.connect(str(LANCEDB_DB_PATH))

        # Korrektes Sentence-Transformers Embedding (kein get_with_image!)
        embedding_func = get_registry().get("sentence-transformers").create(
            name="BAAI/bge-small-en-v1.5"
        )

        class CodeChunk(LanceModel):
            text: str = embedding_func.SourceField()
            vector: Vector(embedding_func.ndims()) = embedding_func.VectorField()
            filename: str
            rel_path: str
            line_start: int

        table = db.create_table("project_code", schema=CodeChunk, mode="overwrite")

        chunks = []
        for root_dir, _, files in os.walk(str(PROJECT_DIR)):
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = Path(root_dir) / file
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    # 30-Zeilen-Blöcke halten den Kontext klein
                    for i in range(0, len(lines), 30):
                        chunk_text = "".join(lines[i : i + 30]).strip()
                        if not chunk_text:
                            continue
                        rel = str(file_path.relative_to(PROJECT_DIR))
                        chunks.append(
                            {
                                "text": chunk_text,
                                "filename": file,
                                "rel_path": rel,
                                "line_start": i + 1,
                            }
                        )
                except Exception as e:
                    print(f"[WARN] Fehler beim Lesen von {file}: {e}")

        if chunks:
            table.add(chunks)
            print(f"[OK] {len(chunks)} Code-Blöcke erfolgreich in LanceDB indexiert!")
            print(f"     DB-Pfad: {LANCEDB_DB_PATH}")
        else:
            print("[WARN] Keine .py Dateien im Projektverzeichnis gefunden.")
    except Exception as e:
        print(f"[ERROR] LanceDB-Indexierung fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
    print()


def wait_for_port(port: int, max_tries: int = 40) -> bool:
    """Wartet auf einen offenen Port; Poll-Intervall steigt von 0.25s bis 1s an.

    So sind schnell startende Server sofort erkannt, ohne dass bei langsamen
    Servern unnaetig viel abgefragt wird.
    """
    delay = 0.25
    for _ in range(max_tries):
        if port_is_open(port):
            return True
        time.sleep(delay)
        if delay < 1.0:
            delay = min(1.0, delay * 2)
    return False


def wait_for_ports_parallel(ports: dict[int, str], max_tries: int = 40) -> None:
    """Ueberwacht mehrere Ports gleichzeitig in eigenen Threads.

    Die MCP-Server starten parallel in ihren WT-Tabs - sequentielles Warten
    addiert die Wartezeiten. Mit Threads ist die Gesamtzeit maximal so lang
    wie der langsamste Dienst.
    """
    import threading

    lock = threading.Lock()

    def _wait_one(port: int, name: str) -> None:
        ok = wait_for_port(port, max_tries=max_tries)
        with lock:
            if ok:
                print(f"[OK] {name} auf Port {port}")
            else:
                print(f"[WARN] {name} (Port {port}) noch nicht erreichbar - "
                      f"bitte den passenden Tab pruefen.")

    threads = [
        threading.Thread(target=_wait_one, args=(port, name), daemon=True)
        for port, name in ports.items()
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def write_helper_bat(command: str, cwd: Path, title: str, helper_name: str) -> Path:
    """Schreibt einen Befehl in eine BAT-Datei (für einen Tab)."""
    HELPER_DIR.mkdir(parents=True, exist_ok=True)
    helper_path = HELPER_DIR / f"run_{helper_name}.bat"

    content = (
        "@echo off\r\n"
        f"title {title}\r\n"
        f'cd /d "{cwd}"\r\n'
        f"{command}\r\n"
    )
    helper_path.write_text(content, encoding="utf-8")
    return helper_path


def open_wt_tabs(tabs: list[tuple[str, Path]]) -> None:
    """Oeffnet EIN Windows-Terminal-Fenster mit je einem Tab pro Eintrag."""
    args: list[str] = [str(WT_EXE)]
    for i, (title, bat_path) in enumerate(tabs):
        if i > 0:
            args.append(";")
        args += ["new-tab", "--title", title, "cmd.exe", "/k", str(bat_path)]
    subprocess.Popen(args)


def main() -> None:
    banner()
    model_path = choose_model()
    check_prerequisites(model_path)
    kill_old_processes()

    # 0. Lokaler KI-Langzeitspeicher wird vor den Servern gebaut
    code_in_lancedb_indexieren()

    # ------------------------------------------------------------------
    # Bat-Helper fuer alle 4 Dienste vorbereiten
    # ------------------------------------------------------------------
    fs_cmd = (
        'npx.cmd -y mcp-proxy@latest --port 8001 --stateless --server stream '
        f'--shell npx.cmd @modelcontextprotocol/server-filesystem "{PROJECT_DIR}"'
    )
    fs_bat = write_helper_bat(fs_cmd, cwd=ROOT, title="MCP Filesystem 8001", helper_name="fs")

    repomapper_cmd = f'"{VENV_PYTHON}" http_repomapper.py'
    repomapper_bat = write_helper_bat(
        repomapper_cmd, cwd=REPOMAPPER_DIR, title="MCP RepoMapper 8002", helper_name="repomapper"
    )

    # Nutzt denselben venv wie RepoMapper (dort sind lancedb + sentence-transformers)
    lancedb_cmd = f'"{VENV_PYTHON}" server.py'
    lancedb_bat = write_helper_bat(
        lancedb_cmd, cwd=LANCEDB_MCP_DIR, title="MCP LanceDB 8003", helper_name="lancedb"
    )

    llama_cmd = " ".join(
        [
            f'"{SERVER_EXE}"',
            "-m", f'"{model_path}"',
            "-c", "140000",
            "-np", "1",
            "-ngl", "99",
            "-fa", "on",
            "--jinja",
            "--reasoning", "off",
            "--host", "127.0.0.1",
            "--port", "8484",
            "-ub", "512",
            "--temp", "0.7",
            "--top-p", "0.9",
            "--top-k", "40",
            "--ui-mcp-proxy",
        ]
    )
    llama_bat = write_helper_bat(
        llama_cmd, cwd=ROOT, title="llama-server 8484", helper_name="llama"
    )

    # ------------------------------------------------------------------
    # EIN Windows-Terminal-Fenster mit 4 Tabs oeffnen
    # ------------------------------------------------------------------
    print("Oeffne EIN Windows-Terminal-Fenster mit 4 Tabs "
          "(Filesystem, RepoMapper, LanceDB, llama-server)...")
    open_wt_tabs(
        [
            ("MCP Filesystem 8001", fs_bat),
            ("MCP RepoMapper 8002", repomapper_bat),
            ("MCP LanceDB 8003", lancedb_bat),
            ("llama-server 8484", llama_bat),
        ]
    )
    print()

    print("Warte parallel auf Filesystem MCP (8001), RepoMapper MCP (8002), LanceDB MCP (8003)...")
    wait_for_ports_parallel(
        {8001: "Filesystem MCP", 8002: "RepoMapper MCP", 8003: "LanceDB MCP"},
        max_tries=40,
    )
    print()

    print("Warte auf llama-server (8484) - Modell wird geladen, kann dauern...")
    if wait_for_port(8484, max_tries=180):
        print("[OK] llama-server auf Port 8484")
    else:
        print("[WARN] llama-server (Port 8484) noch nicht erreichbar - bitte den llama-server-Tab pruefen.")

    print()
    print("==========================================================")
    print("Web UI:")
    print("  http://127.0.0.1:8484")
    print()
    print("MCP URLs:")
    print("  Filesystem : http://127.0.0.1:8001/mcp")
    print("  RepoMapper : http://127.0.0.1:8002/mcp")
    print("  LanceDB    : http://127.0.0.1:8003/mcp")
    print()
    print("Alle 4 Dienste laufen als Tabs im selben Windows-Terminal-Fenster.")
    print("Dieses Startfenster kann jetzt geschlossen werden.")
    print("==========================================================")
    input("Enter zum Beenden druecken...")


if __name__ == "__main__":
    main()
