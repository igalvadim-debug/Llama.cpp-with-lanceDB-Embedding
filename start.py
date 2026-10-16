#!/usr/bin/env python3
"""
ClaudeAgent Coder - Alles-in-einem-Start (Python-Version)

Startet Filesystem-MCP-Proxy, RepoMapper-MCP, LanceDB-MCP und llama-server
als VIER TABS in EINEM Windows-Terminal-Fenster (statt vier Einzelfenster).
Modell 4 ist Qwen3.8-2B-BF16.gguf mit 32K Kontext.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# ROOT folgt dem tatsächlichen Checkout-Pfad des Skripts
ROOT = Path(__file__).resolve().parent
SERVER_EXE = Path(r"D:\Unsloth\C-claude\llama.cpp\llama-server.exe")
# embeddinggemma braucht ein neueres llama.cpp (Architektur gemma-embedding2) -> eigener CPU-Build
EMBED_EXE = Path(r"D:\Unsloth\C-claude\llama.cpp_embed\llama-server.exe")
EMBED_MODEL = ROOT / "models" / "embeddinggemma-2-Q8_0" / "embeddinggemma-2-Q8_0.gguf"
EMBED_PORT = 8512
EMBED_URL = f"http://127.0.0.1:{EMBED_PORT}/v1/embeddings"
LANCEDB_TABLE = "project_code_gemma"
PROJECT_DIR = ROOT / "projects"
SKIP_DIRS = {
    "__pycache__", "venv", ".venv", "env", ".env", "site-packages",
    "node_modules", ".git", "build", "dist", "out", "target",
    ".mypy_cache", ".pytest_cache", ".idea", ".vscode",
}
REPOMAPPER_DIR = ROOT / "RepoMapper"
LANCEDB_DIR = ROOT / "lancedb_mcp"
LANCEDB_DB_PATH = ROOT / "lancedb_context"
VENV_PYTHON = REPOMAPPER_DIR / "venv" / "Scripts" / "python.exe"
HELPER_DIR = ROOT / "_start_helpers"
WT_EXE = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WindowsApps" / "wt.exe"

# Agenten (Claude Code / opencode / Hermes) - Pfade per Umgebungsvariablen ueberschreibbar
CLAUDE_EXE = Path(os.environ.get("CLAUDE_CMD", r"C:\Users\Startklar\.local\bin\claude.exe"))
CLAUDE_CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR", str(ROOT.parent / "claude-local"))
HERMES_DEFAULT = os.environ.get("HERMES_CMD", "hermes")

MODELS = {
    "1": ROOT / "models" / "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "2": ROOT / "models" / "Qwopus3.5-4B-Coder-MTP-Q8_0.gguf",
    "3": ROOT / "models" / "gemma-4-E4B-it-heretic-Q4_K_M.gguf",
    "4": ROOT / "models" / "Qwen3.8-2B-BF16.gguf",
    "5": Path(r"D:\SillyTavernNeurogen\kobold\models\Gemma-4-E2B-Uncensored-HauhauCS-Aggressive-Q6_K_P.gguf"),
    "6": Path(r"C:\Users\Startklar\.lmstudio\models\lmstudio-community\Qwopus-MoE-35B-A3B-APEX-I-Mini\Qwopus-MoE-35B-A3B-APEX-I-Mini.gguf"),
    "7": Path(r"C:\Users\Startklar\.lmstudio\models\lmstudio-community\Qwen3.6-35B-A3B-abliterated.IQ4_XS\Qwen3.6-35B-A3B-abliterated.IQ4_XS.gguf"),
}

# Vision-Modelle starten IMMER zusammen mit ihrem mmproj
MMPROJ_BY_MODEL = {
    MODELS["5"]: Path(r"D:\SillyTavernNeurogen\kobold\models\mmproj-Gemma-4-E2B-Uncensored-HauhauCS-Aggressive-f16.gguf"),
}

# MoE-Modell (35B, 3B aktiv) passt nicht komplett in 8 GB VRAM: --fit verteilt Experten automatisch auf CPU/RAM
GPU_ARGS_BY_MODEL = {
    MODELS["6"]: ["--fit", "on", "-ctk", "q8_0", "-ctv", "q8_0", "--chat-template-file", r"D:\claudeAgent\Claude-Lokal\templates\qwopus-moe.patched.jinja"],
    MODELS["7"]: ["--fit", "on", "-ctk", "q8_0", "-ctv", "q8_0"],
}

PORTS = (8001, 8002, 8003, 8484, 8512)


def banner() -> None:
    print()
    print("==========================================================")
    print("ClaudeAgent Coder - Alles in einem Start (Python)")
    print("==========================================================")
    print()


def choose_model(arg_choice: str | None = None) -> Path:
    print("Verfuegbare Modelle:")
    for key, path in MODELS.items():
        print(f"[{key}] {path.name}")
    print()

    if arg_choice is not None:
        if arg_choice not in MODELS:
            print(f"[ERROR] Ungueltige Modell-Nummer als Argument: {arg_choice}")
            sys.exit(1)
        model_path = MODELS[arg_choice]
        print(f"Nicht-interaktiver Start - Modell {arg_choice} gewaehlt.")
    else:
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
        *(((MMPROJ_BY_MODEL[model_path], "mmproj-Datei nicht gefunden"),) if model_path in MMPROJ_BY_MODEL else ()),
        (VENV_PYTHON, "RepoMapper Python nicht gefunden"),
        (PROJECT_DIR, "Projektverzeichnis nicht gefunden"),
        (LANCEDB_DIR / "server_gemma.py", "LanceDB-MCP server_gemma.py nicht gefunden"),
        (EMBED_EXE, "llama-server.exe fuer Embedding nicht gefunden"),
        (EMBED_MODEL, "embeddinggemma-Modell nicht gefunden"),
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
    if model_path in MMPROJ_BY_MODEL:
        print("[OK] mmproj (Vision)")
    print("[OK] RepoMapper Python")
    print("[OK] Projektverzeichnis")
    print("[OK] Windows Terminal")
    print()


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def find_pids_on_ports(ports: tuple[int, ...]) -> set[int]:
    """Findet lauschende Prozesse ALLER Ports in EINEM PowerShell-Aufruf.

    Ein einzelner Prozess-Start statt N Stueck spart mehrere Sekunden
    (PowerShell-Kaltstart ist der teure Teil); die Abfrage ist
    unabhaengig von der Windows-Sprache.
    """
    pids: set[int] = set()
    try:
        port_list = ",".join(str(p) for p in ports)
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-NetTCPConnection -LocalPort @({port_list}) -State Listen "
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
        subprocess.check_call(cmd, capture_output=True, timeout=15)
    except Exception:
        # Fallback: einzeln beenden, falls der Sammel-Aufruf fehlschlaegt
        # (check_call wirft auch bei nonzero Exit-Code -> PID-Fallback laeuft)
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


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Holt Embeddings vom embeddinggemma-llama-server (OpenAI-kompatibel)."""
    import json
    import urllib.error
    import urllib.request

    payload = json.dumps({"input": texts, "model": "embeddinggemma"}).encode("utf-8")
    last_error: Exception | None = None
    for _ in range(30):
        try:
            req = urllib.request.Request(
                EMBED_URL, data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))["data"]
            data.sort(key=lambda d: d.get("index", 0))
            return [d["embedding"] for d in data]
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code != 503:  # 503 = Modell laedt noch
                break
        except OSError as e:
            last_error = e
        time.sleep(2)
    raise RuntimeError(f"Embedding-Server nicht nutzbar: {last_error}")


def start_embedding_server() -> bool:
    """Startet den embeddinggemma-Server (CPU) in eigenem Konsolenfenster."""
    print("==========================================================")
    print(f"[Embedding] Starte embeddinggemma-Server (Port {EMBED_PORT}, CPU)...")
    print("==========================================================")
    cmd = [
        str(EMBED_EXE),
        "-m", str(EMBED_MODEL),
        "--embedding",
        "-c", "4096", "-b", "2048", "-ub", "2048", "-np", "1",
        "--host", "127.0.0.1",
        "--port", str(EMBED_PORT),
    ]
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    if wait_for_port(EMBED_PORT, max_tries=90):
        print(f"[OK] Embedding-Server auf Port {EMBED_PORT}")
        print()
        return True
    print(f"[WARN] Embedding-Server (Port {EMBED_PORT}) nicht erreichbar - Indexierung wird uebersprungen.")
    print()
    return False


def code_in_lancedb_indexieren() -> None:
    """Zerlegt Python-Dateien in Haeppchen und speichert sie mit embeddinggemma-Vektoren.

    Unveraenderte Bloecke (gleicher Pfad + Text) kommen aus der bestehenden Tabelle,
    nur neue/geaenderte werden neu berechnet.
    """
    print("==========================================================")
    print("[LanceDB] Indexiere Projektverzeichnis (embeddinggemma)...")
    print("==========================================================")

    try:
        import hashlib

        import lancedb
        import pyarrow as pa

        if not port_is_open(EMBED_PORT):
            print("[WARN] Embedding-Server laeuft nicht - Indexierung uebersprungen.")
            print()
            return

        # Datei-Mtime + Groesse als schneller Vorab-Cache: unveraenderte Dateien
        # werden gar nicht erst gelesen und in Haeppchen zerlegt. Die Tabelle wird
        # dafuer VOR dem Datei-Scan gelesen: Mtime-Signaturen gelten nur, wenn die
        # zugehoerigen Zeilen auch wirklich in der Tabelle vorhanden und lesbar sind
        # (sonst wuerden geloeschte/fehlende Dateien für immer aus dem Index fehlen).
        file_meta_path = LANCEDB_DB_PATH / "file_meta.json"
        try:
            import json as _json

            old_meta = _json.loads(file_meta_path.read_text(encoding="utf-8"))
        except Exception:
            old_meta = {}

        db = lancedb.connect(str(LANCEDB_DB_PATH))

        def chunk_key(c: dict) -> str:
            return hashlib.sha1((c["rel_path"] + "\n" + c["text"]).encode("utf-8")).hexdigest()

        cache: dict[str, list[float]] = {}
        table_rows: list[dict] = []
        if LANCEDB_TABLE in db.table_names():
            try:
                table_rows = db.open_table(LANCEDB_TABLE).to_arrow().to_pylist()
            except Exception as e:
                print(f"[WARN] Cache nicht lesbar, rechne alles neu: {e}")
                table_rows = []
        for row in table_rows:
            cache[chunk_key(row)] = row["vector"]
        indexed_paths = {row["rel_path"] for row in table_rows}
        # Mtime-Skip nur fuer Dateien, deren Bloecke tatsaechlich in der Tabelle stecken
        old_meta = {k: v for k, v in old_meta.items() if k in indexed_paths}

        chunks = []
        new_meta: dict[str, list] = {}
        unchanged_files: set[str] = set()
        skipped_files = 0
        for root_dir, dirs, files in os.walk(str(PROJECT_DIR)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = Path(root_dir) / file
                rel = str(file_path.relative_to(PROJECT_DIR))
                try:
                    st = file_path.stat()
                    sig = [round(st.st_mtime, 6), st.st_size]
                    if old_meta.get(rel) == sig:
                        # Datei unveraendert -> alte Bloecke weiterverwenden
                        unchanged_files.add(rel)
                        skipped_files += 1
                        continue
                    new_meta[rel] = sig
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    for i in range(0, len(lines), 30):
                        chunk_text = "".join(lines[i : i + 30]).strip()
                        if not chunk_text:
                            continue
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

        chunk_paths = {c["rel_path"] for c in chunks}
        kept_rows = [row for row in table_rows
                     if row["rel_path"] in unchanged_files
                     and row["rel_path"] not in chunk_paths]  # Bloecke der unveraenderten Dateien
        if skipped_files:
            print(f"[LanceDB] {skipped_files} unveraenderte .py-Dateien schnell uebersprungen (Mtime-Check)")

        if not chunks and not kept_rows:
            print("[WARN] Keine .py Dateien im Projektverzeichnis gefunden.")
            print()
            return

        keys = [chunk_key(c) for c in chunks]
        todo = [i for i, k in enumerate(keys) if k not in cache]
        print(f"[LanceDB] {len(chunks)} geaenderte/neue Code-Bloecke, {len(chunks) - len(todo)} aus Cache, "
              f"{len(todo)} neu zu berechnen")

        batch = 8
        for start in range(0, len(todo), batch):
            idxs = todo[start : start + batch]
            texts = [
                f"title: {chunks[i]['filename']} | text: {chunks[i]['text'][:4000]}"
                for i in idxs
            ]
            vectors = embed_texts(texts)
            for i, vec in zip(idxs, vectors):
                cache[keys[i]] = vec
            done = min(start + batch, len(todo))
            if (start // batch) % 5 == 0 or done == len(todo):
                print(f"[LanceDB]   {done}/{len(todo)} berechnet", flush=True)

        first_vec = cache[keys[0]] if keys else (kept_rows[0]["vector"] if kept_rows else None)
        if first_vec is None:
            print("[WARN] Keine Vektoren verfuegbar - Tabelle bleibt unveraendert.")
            print()
            return
        dim = len(first_vec)
        schema = pa.schema(
            [
                pa.field("text", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dim)),
                pa.field("filename", pa.string()),
                pa.field("rel_path", pa.string()),
                pa.field("line_start", pa.int32()),
            ]
        )
        rows = kept_rows + [dict(c, vector=cache[k]) for c, k in zip(chunks, keys)]
        db.create_table(
            LANCEDB_TABLE, data=pa.Table.from_pylist(rows, schema=schema), mode="overwrite"
        )
        # Mtime-Metadaten fuer den naechsten Lauf speichern (nur Dateien, die in
        # diesem Lauf gelesen wurden oder deren Bloecke erhalten blieben)
        try:
            all_meta = {k: v for k, v in old_meta.items() if k in unchanged_files}
            all_meta.update(new_meta)
            LANCEDB_DB_PATH.mkdir(parents=True, exist_ok=True)
            file_meta_path.write_text(_json.dumps(all_meta), encoding="utf-8")
        except Exception as e:
            print(f"[WARN] Konnte file_meta.json nicht schreiben: {e}")
        print(f"[OK] {len(rows)} Code-Bloecke in '{LANCEDB_TABLE}' indexiert ({dim} Dimensionen)")
        print(f"     DB-Pfad: {LANCEDB_DB_PATH}")
    except Exception as e:
        print(f"[ERROR] LanceDB-Indexierung fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
    print()


def wait_for_port(port: int, max_tries: int = 30) -> bool:
    """Wartet auf einen offenen Port; Poll-Intervall steigt von 0.25s bis 1s an.

    So sind schnell startende Server sofort erkannt (kein 1-Sekunden-Takt),
    ohne dass bei langsamen Servern unnaetig viel abgefragt wird.
    Wartezeit ueber alle Versuche bleibt ca. erhalten (max_tries * ~0.8s im Mittel).
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
    (Port fuer Port) addiert die Wartezeiten. Mit Threads ist die Gesamtzeit
    maximal so lang wie der langsamste Dienst.
    """
    import threading

    results: dict[int, bool] = {}
    lock = threading.Lock()

    def _wait_one(port: int, name: str) -> None:
        ok = wait_for_port(port, max_tries=max_tries)
        with lock:
            results[port] = ok
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


def ensure_venv_runtime() -> None:
    """start.py braucht ``lancedb``/``pyarrow`` aus dem RepoMapper-venv.

    Wird es mit einem anderen Interpreter gestartet (System-Python per
    ``python start.py``), fehlt ``lancedb``. Dann mit dem venv-Python neu
    starten statt die LanceDB-Indexierung abzubrechen.
    """
    if not VENV_PYTHON.exists():
        return
    try:
        if Path(sys.executable).resolve() == VENV_PYTHON.resolve():
            return
    except OSError:
        return
    try:
        import lancedb  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    print(f"[INFO] 'lancedb' fehlt in {sys.executable} - Neustart mit venv-Python: {VENV_PYTHON}")
    result = subprocess.run([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise SystemExit(result.returncode)


def agent_cmd_for(kind: str, base_cmd: str) -> str | None:
    """Baut den Startbefehl fuer einen Agenten-Tab (claude / opencode / hermes).

    Fuer claude wird zusaetzlich ein lokaler llama.cpp-Helfer geschrieben, damit
    Claude Code gegen Port 8484 laeuft (ANTHROPIC_BASE_URL -> http://127.0.0.1:8484,
    Anthropic-kompatible /v1/messages von llama-server).
    """
    if kind == "claude":
        helper = write_claude_local_bat()
        return f'set "CLAUDE_CONFIG_DIR={CLAUDE_CONFIG_DIR}" && "{helper}"'
    if kind == "hermes":
        # HERMES_DEFAULT enthaelt den Wert aus HERMES_CMD (Modul-Init) - nicht
        # erneut einlesen; bare Befehlsnamen (laufen ueber PATH) unverändert lassen.
        if Path(HERMES_DEFAULT).exists():
            return f'"{HERMES_DEFAULT}"'
        return HERMES_DEFAULT
    # opencode: nutzt ~/.config/opencode/opencode.json (siehe start_all.bat);
    # keine projektlokale Config erzwingen - vorhandene Benutzerkonfiguration bleibt aktiv.
    return base_cmd


def write_claude_local_bat() -> Path:
    """Schreibt _start_helpers\\claude_local.bat mit lokaler API-Config."""
    HELPER_DIR.mkdir(parents=True, exist_ok=True)
    helper = HELPER_DIR / "claude_local.bat"
    lines = [
        "@echo off",
        'set "ANTHROPIC_BASE_URL=http://127.0.0.1:8484"',
        'set "ANTHROPIC_API_KEY=not-needed"',
        'set "API_TIMEOUT_MS=3000000"',
        'set "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"',
        f'"{CLAUDE_EXE}" %*',
        "",
    ]
    helper.write_text("\r\n".join(lines), encoding="utf-8")
    return helper


AGENT_TABS = {
    "claude":   ("Claude Code",     "claude"),
    "opencode": ("opencode",        "opencode"),
    "hermes":   ("Hermes Agent",    "hermes"),
}


def choose_agents(arg_agents: str | None) -> list[str]:
    """Agenten-Tabs aus Argument ('claude,opencode,hermes') oder interaktiv waehlen."""
    known = tuple(AGENT_TABS)
    default = list(known)
    if arg_agents is not None:
        kinds = [a.strip().lower() for a in arg_agents.split(",") if a.strip()]
        if not kinds or kinds[0] in ("none", "n", "keine"):
            return []
        if kinds[0] == "all":
            return default
        bad = [k for k in kinds if k not in known]
        if bad:
            print(f"[WARN] Unbekannte Agenten uebersprungen: {', '.join(bad)} "
                  f"(erlaubt: {', '.join(known)})")
        return [k for k in kinds if k in known]
    print()
    print("Agenten-Tabs: [a] alle drei (claude+opencode+hermes, Standard), "
          "[c] Claude, [o] opencode, [h] Hermes, [n] keine")
    wahl = input("Auswahl (Enter = a): ").strip().lower()
    return {
        "": default, "a": default, "c": ["claude"],
        "o": ["opencode"], "h": ["hermes"], "n": [],
    }.get(wahl, default)


def main() -> None:
    ensure_venv_runtime()
    banner()
    arg_choice = sys.argv[1] if len(sys.argv) > 1 else None
    arg_agents = sys.argv[2] if len(sys.argv) > 2 else None
    model_path = choose_model(arg_choice)
    agent_kinds = choose_agents(arg_agents)
    check_prerequisites(model_path)
    kill_old_processes()

    # 0. Embedding-Server (embeddinggemma) + lokaler KI-Langzeitspeicher vor den Servern
    start_embedding_server()
    code_in_lancedb_indexieren()

    fs_cmd = (
        'npx.cmd -y mcp-proxy@latest --port 8001 --stateless --server stream '
        f'--shell npx.cmd @modelcontextprotocol/server-filesystem "{PROJECT_DIR}"'
    )
    fs_bat = write_helper_bat(fs_cmd, cwd=ROOT, title="MCP Filesystem 8001", helper_name="fs")

    repomapper_cmd = f'"{VENV_PYTHON}" http_repomapper.py'
    repomapper_bat = write_helper_bat(
        repomapper_cmd, cwd=REPOMAPPER_DIR, title="MCP RepoMapper 8002", helper_name="repomapper"
    )

    lancedb_cmd = f'"{VENV_PYTHON}" server_gemma.py'
    lancedb_bat = write_helper_bat(
        lancedb_cmd, cwd=LANCEDB_DIR, title="MCP LanceDB 8003", helper_name="lancedb"
    )

    llama_cmd = " ".join(
        [
            f'"{SERVER_EXE}"',
            "-m", f'"{model_path}"',
            *(["--mmproj", f'"{MMPROJ_BY_MODEL[model_path]}"'] if model_path in MMPROJ_BY_MODEL else []),
            "-c", "140000",
            "-np", "1",
            *GPU_ARGS_BY_MODEL.get(model_path, ["-ngl", "99"]),
            "-fa", "on",
            "--jinja",
            "--reasoning", "off",
            "--host", "127.0.0.1",
            "--port", "8484",
            "-ub", "512",
            "--temp", "0.2",
            "--top-p", "0.9",
            "--top-k", "40",
            "--ui-mcp-proxy",
        ]
    )
    llama_bat = write_helper_bat(
        llama_cmd, cwd=ROOT, title="llama-server 8484", helper_name="llama"
    )

    print("Oeffne EIN Windows-Terminal-Fenster mit Tabs "
          "(Filesystem, RepoMapper, LanceDB, llama-server + Agenten)...")
    tab_defs = [
        ("MCP Filesystem 8001", fs_bat),
        ("MCP RepoMapper 8002", repomapper_bat),
        ("MCP LanceDB 8003", lancedb_bat),
        ("llama-server 8484", llama_bat),
    ]
    for kind in agent_kinds:
        info = AGENT_TABS.get(kind)
        if not info:
            print(f"[WARN] Unbekannter Agent '{kind}' - uebersprungen "
                  f"(erlaubt: claude, opencode, hermes)")
            continue
        title, base_cmd = info
        cmd = agent_cmd_for(kind, base_cmd)
        bat = write_helper_bat(cmd, cwd=PROJECT_DIR, title=title, helper_name=f"agent_{kind}")
        tab_defs.append((title, bat))
    open_wt_tabs(tab_defs)
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
    print("http://127.0.0.1:8484")
    print()
    print("MCP URLs:")
    print("Filesystem: http://127.0.0.1:8001/mcp")
    print("RepoMapper: http://127.0.0.1:8002/mcp")
    print("LanceDB   : http://127.0.0.1:8003/mcp")
    print("Embedding : http://127.0.0.1:8512/v1/embeddings (embeddinggemma)")
    print()
    print("Alle Dienste laufen als Tabs im selben Windows-Terminal-Fenster.")
    if agent_kinds:
        print("Agenten-Tabs (claude/opencode/hermes) sind geoeffnet - "
              "einfach in den jeweiligen Tab wechseln.")
    else:
        print("Keine Agenten-Tabs - Starte mit z.B.:  start_all.bat 1 claude,opencode,hermes")
    print("Dieses Startfenster kann jetzt geschlossen werden.")
    print("==========================================================")
    if arg_choice is None:
        input("Enter zum Beenden druecken...")


if __name__ == "__main__":
    main()
