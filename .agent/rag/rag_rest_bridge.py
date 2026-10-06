#!/usr/bin/env python3
"""
RAG REST Bridge - Pont autonome entre le pipeline Python RAG et les serveurs MCP

Ce pont expose deux serveurs HTTP locaux :
  - Port 8001 : Proxy REST pour Zvec MCP (stockage vectoriel local)
  - Port 8002 : Proxy REST pour Memory MCP (graphe de connaissances)

Il démarre les serveurs MCP en sous-processus stdio et traduit les appels
REST du pipeline Python en appels MCP JSON-RPC standards.

Usage:
    python rag_rest_bridge.py [--zvec-port 8001] [--memory-port 8002]

Architecture:
    Pipeline Python  →  HTTP REST (localhost:8001/8002)
                     →  REST Bridge (ce fichier)
                     →  MCP stdio (subprocess)
                     →  zvec-mcp-server / memory MCP server
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# Forcer UTF-8 sur la console : les logs contiennent des emojis,
# une console cp1252 lève UnicodeEncodeError et peut tuer le bridge.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Configuration - AUCUN CHEMIN HARD-CODÉ
# ---------------------------------------------------------------------------
# Tous les chemins sont résolus dans cet ordre :
#   1. Variable d'environnement (priorité absolue)
#   2. Fichier config MCP de l'IDE actif (Devin, Cursor, Kilocode, etc.)
#   3. Chemin relatif au projet (fallback portable)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ENV = PROJECT_ROOT / ".env"

# Chemins des configs MCP par IDE
IDE_CONFIG_PATHS = {
    "devin": Path.home() / "AppData" / "Roaming" / "devin" / "mcp_config.json",
    "antigravity": Path.home() / ".antigravity" / "mcp_config.json",
    "cursor": Path.home() / ".cursor" / "mcp.json",
    "kilocode": Path.home() / ".kilocode" / "mcp_config.json",
    "kilo": Path.home() / ".config" / "kilo" / "mcp_config.json",
    "cline_vscode": Path.home() / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "mcp_settings.json",
    "cline_cursor": Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "mcp_settings.json",
    "cline_antigravity": Path.home() / "AppData" / "Roaming" / "Antigravity" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "mcp_settings.json",
    "kilocode_vscode": Path.home() / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "kilocode.kilo-code" / "settings" / "mcp_settings.json",
    "kilocode_antigravity": Path.home() / "AppData" / "Roaming" / "Antigravity" / "User" / "globalStorage" / "kilocode.kilo-code" / "settings" / "mcp_settings.json",
}

def detect_active_ide() -> Optional[str]:
    """Détecte l'IDE actif via variable d'environnement ou contexte."""
    # 1. Variable explicite
    ide = os.environ.get("ACTIVE_IDE", "").lower()
    if ide in IDE_CONFIG_PATHS:
        return ide
    
    # 2. Détection par environnement
    if "DEVIN" in os.environ:
        return "devin"
    if "ANTIGRAVITY" in os.environ:
        return "antigravity"
    if "KILOCODE" in os.environ:
        return "kilocode"
    if "CURSOR" in os.environ:
        return "cursor"
    
    # 3. Détection par existence des fichiers
    for ide_name, config_path in IDE_CONFIG_PATHS.items():
        if config_path.exists():
            return ide_name
    
    return None


def load_ide_mcp_config(ide_name: Optional[str] = None) -> Dict:
    """Charge la configuration MCP de l'IDE spécifié ou détecté."""
    if ide_name is None:
        ide_name = detect_active_ide()
    
    if ide_name and ide_name in IDE_CONFIG_PATHS:
        config_path = IDE_CONFIG_PATHS[ide_name]
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARNING] Impossible de charger {config_path}: {e}")
    return {}

# --- Chargement manuel de .env si présent ---
def load_dotenv(path: Path):
    """Charge les variables d'environnement depuis un fichier .env."""
    if not path.exists():
        return
    import re
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                
                # Expansion simple des variables ${VAR}
                def replace_var(match):
                    var_name = match.group(1)
                    return os.environ.get(var_name, f"${{{var_name}}}")
                
                val = re.sub(r"\$\{([^}]+)\}", replace_var, val)
                
                if key not in os.environ or "$" in os.environ[key]:
                    os.environ[key] = val





# Logging - configuré AVANT le chargement de la config
# Logs vers stdout ET fichier dans .agent/logs/
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "rag_bridge.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] %(levelname)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            str(LOG_FILE),
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger("RAGBridge")
logger.info(f"📝 Logs écrits dans: {LOG_FILE}")

# Charger .env et config IDE
load_dotenv(PROJECT_ENV)
ACTIVE_IDE = detect_active_ide()
IDE_MCP_CONFIG = load_ide_mcp_config(ACTIVE_IDE)

if ACTIVE_IDE:
    logger.info(f"IDE détecté: {ACTIVE_IDE}")

# ---------------------------------------------------------------------------
# Résolution des chemins MCP (ordre: ENV > config > fallback relatif)
# ---------------------------------------------------------------------------

def _resolve_mcp_path(server_name: str, config_key: str, env_var: str, relative_fallback: str) -> str:
    """
    Résout un chemin MCP dans l'ordre de priorité :
    1. Variable d'environnement (env_var)
    2. Config MCP de l'IDE > mcpServers[server_name].args[0]
    3. Chemin relatif au projet (relative_fallback)
    """
    # 1. Variable d'environnement (priorité absolue)
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value
    
    # 2. Config MCP de l'IDE (format mcpServers)
    ide_servers = IDE_MCP_CONFIG.get("mcpServers", {})
    server_config = ide_servers.get(server_name, {})
    args = server_config.get("args", [])
    if args and len(args) > 0:
        config_path = args[0]
        if config_path.startswith("./"):
            return str(PROJECT_ROOT / config_path[2:])
        return config_path
    
    # 3. Fallback relatif au projet (portable)
    return str(PROJECT_ROOT / relative_fallback)


def _resolve_data_path(env_var: str, relative_fallback: str, force_env_var: str = None) -> str:
    """
    Résout un chemin de données dans l'ordre :
    1. Variable d'environnement forcée (ex: AGENT_DB_ROOT)
    2. Variable d'environnement spécifique
    3. Chemin relatif au projet
    
    Args:
        env_var: Variable d'environnement à vérifier
        relative_fallback: Chemin relatif au projet si pas de variable d'environnement
        force_env_var: Variable d'environnement prioritaire (ex: AGENT_DB_ROOT)
    """
    # 1. Variable d'environnement forcée (prioritaire)
    if force_env_var:
        force_value = os.environ.get(force_env_var)
        if force_value:
            # Construire le chemin complet à partir de la racine
            return str(Path(force_value) / "current_workspace" / "vector" / "zvec-data")
    
    # 2. Variable d'environnement spécifique
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value
    
    # 3. Fallback relatif
    return str(PROJECT_ROOT / relative_fallback)


# --- Chemins des serveurs MCP ---
ZVEC_MCP_PATH = _resolve_mcp_path(
    server_name="zvec",
    config_key="args",
    env_var="ZVEC_MCP_PATH",
    relative_fallback="<HEPHAISTOS_ROOT>/mcp/servers/zvec-mcp-server/build/index.js"
)

MEMORY_MCP_PATH = _resolve_mcp_path(
    server_name="memory",
    config_key="args",
    env_var="MEMORY_MCP_PATH",
    relative_fallback="<HEPHAISTOS_DATA>/servers/memory/dist/index.js"
)

# --- Commandes des serveurs MCP ---
ZVEC_SERVER_CMD = ["node", ZVEC_MCP_PATH]
MEMORY_SERVER_CMD = ["node", MEMORY_MCP_PATH]

# --- Répertoires de données ---
ZVEC_DATA_DIR = _resolve_data_path(
    env_var="ZVEC_DATA_DIR",
    relative_fallback="memory-database/agentmemory/vector/zvec-data",
    force_env_var="AGENT_DB_ROOT"  # Priorité absolue pour le chemin global
)

MEMORY_DB_PATH = _resolve_data_path(
    env_var="MEMORY_DB_PATH",
    relative_fallback="memory-database/agentmemory/graph/memory_mcp.db"
)

# --- Racine de la base de données (pour compatibilité) ---
DB_ROOT = os.environ.get(
    "AGENT_DB_ROOT",
    str(PROJECT_ROOT / ".agent" / "memory-database")
)

# --- Ports HTTP ---
ZVEC_PORT = int(os.environ.get("ZVEC_BRIDGE_PORT", "8001"))
MEMORY_PORT = int(os.environ.get("MEMORY_BRIDGE_PORT", "8002"))


# ---------------------------------------------------------------------------
# MCP Client (communication stdio avec le serveur MCP)
# ---------------------------------------------------------------------------

class MCPClient:
    """
    Client MCP léger qui communique avec un serveur MCP via stdio.
    Lance le serveur en sous-processus et maintient la session JSON-RPC.
    """

    def __init__(self, name: str, cmd: List[str], env: Optional[Dict] = None):
        self.name = name
        self.cmd = cmd
        self.env = env or {}
        self._proc: Optional[subprocess.Popen] = None
        self._id_lock = threading.Lock()    # Protection du compteur d'ID
        self._write_lock = threading.Lock() # Protection des écritures stdin
        self._read_lock = threading.Lock()  # Protection des lectures stdout
        self._call_lock = threading.Lock()  # Sérialisation des appels MCP (un seul à la fois)
        self._req_id = 0
        self._initialized = False

    # ------------------------------------------------------------------
    def _log_stderr(self):
        """Thread pour logger stderr en continu."""
        while self._proc and self._proc.poll() is None:
            try:
                line = self._proc.stderr.readline()
                if line:
                    logger.error(f"[{self.name}] Error on Stderr: {line.strip()}")
            except:
                break

    def start(self) -> bool:
        """Démarre le serveur MCP en sous-processus."""
        # Créer l'environnement fusionné
        merged_env = {**os.environ, **self.env}
        
        # Forcer explicitement la valeur de ZVEC_DATA_DIR pour Zvec
        if self.name == "Zvec" and "ZVEC_DATA_DIR" in self.env:
            # Écraser explicitement avec la bonne valeur
            merged_env["ZVEC_DATA_DIR"] = self.env["ZVEC_DATA_DIR"]
            # Supprimer toutes les autres variables qui pourraient interférer
            for key in list(merged_env.keys()):
                if key.startswith("ZVEC_") and key != "ZVEC_DATA_DIR":
                    continue  # Garder les autres variables ZVEC_
        
        # Log pour debug - vérifier l'environnement passé au sous-processus
        if self.name == "Zvec":
            zvec_data_dir = merged_env.get("ZVEC_DATA_DIR", "NON DÉFINI")
            logger.info(f"[{self.name}] Environnement ZVEC_DATA_DIR passé: {zvec_data_dir}")
        
        # S'assurer que les répertoires de données existent
        if self.name == "Zvec":
            data_dir = self.env.get("ZVEC_DATA_DIR")
            if data_dir:
                Path(data_dir).mkdir(parents=True, exist_ok=True)
        elif self.name == "Memory":
            db_path = self.env.get("MEMORY_FILE_PATH")
            if db_path:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
                text=True,
                encoding="utf-8",
                bufsize=0
            )
            # Démarrer le thread de lecture stderr
            stderr_thread = threading.Thread(target=self._log_stderr, daemon=True)
            stderr_thread.start()
            # Initialiser la session MCP
            self._initialize()
            logger.info(f"[{self.name}] Serveur MCP démarré (PID={self._proc.pid})")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Impossible de démarrer le serveur MCP : {e}")
            return False

    def stop(self):
        """Arrête proprement le serveur MCP."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
            logger.info(f"[{self.name}] Serveur MCP arrêté.")

    # ------------------------------------------------------------------
    def _next_id(self) -> int:
        with self._id_lock:
            self._req_id += 1
            return self._req_id

    def _send_request(self, method: str, params: Dict) -> Dict:
        """Envoie une requête JSON-RPC et attend la réponse."""
        if not self._proc or self._proc.poll() is not None:
            raise RuntimeError(f"[{self.name}] Le processus MCP n'est pas actif.")

        req_id = self._next_id()
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        raw = json.dumps(req) + "\n"

        with self._write_lock:
            try:
                self._proc.stdin.write(raw)
                self._proc.stdin.flush()
            except BrokenPipeError:
                raise RuntimeError(f"[{self.name}] Pipe cassé – le serveur s'est arrêté.")

        # Lire la réponse ligne par ligne jusqu'à trouver le bon id
        deadline = time.time() + 120  # Augmenté à 120s pour l'initialisation et les embeddings
        while time.time() < deadline:
            with self._read_lock:
                line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.01)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                # Peut être du logging du serveur, on l'ignore
                continue
            if resp.get("id") == req_id:
                return resp
        raise TimeoutError(f"[{self.name}] Timeout attente réponse MCP pour {method}")

    def _initialize(self):
        """Handshake MCP initial."""
        try:
            resp = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "rag-rest-bridge", "version": "1.0.0"}
            })
            if "error" in resp:
                raise RuntimeError(f"[{self.name}] Erreur init MCP : {resp['error']}")
            # Notification initialized
            notif = json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }) + "\n"
            self._proc.stdin.write(notif)
            self._proc.stdin.flush()
            self._initialized = True
        except Exception as e:
            # En cas d'erreur d'init, on évite le read() bloquant
            logger.error(f"[{self.name}] Échec lors de l'initialisation MCP : {e}")
            raise e

    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Appelle un outil MCP et retourne le résultat."""
        with self._call_lock:  # Sérialisation obligatoire (stdio est mono-canal)
            resp = self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
        if "error" in resp:
            raise RuntimeError(f"[{self.name}] Erreur outil '{tool_name}': {resp['error']}")
        result = resp.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list) and content[0].get("type") == "text":
            text = content[0]["text"]
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"message": text}
        return result


# ---------------------------------------------------------------------------
# Gestionnaire HTTP Zvec (port 8001)
# ---------------------------------------------------------------------------

class ZvecHandler(BaseHTTPRequestHandler):
    """
    Gestionnaire HTTP qui traduit les appels REST en appels MCP Zvec.

    Routes supportées :
      POST   /collections                       → zvec_create_collection
      POST   /collections/{name}/documents      → zvec_add_documents
      DELETE /collections/{name}/documents      → zvec_delete_documents
      POST   /collections/{name}/search         → zvec_semantic_search
      GET    /health                            → status 200
    """

    client: MCPClient  # défini sur la classe par le serveur

    def log_message(self, format, *args):
        logger.info(f"[Zvec-REST] {self.address_string()} {format % args}")

    def _parse_body(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, msg: str, status: int = 500):
        self._send_json({"error": msg}, status)

    # ------------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        
        if parsed.path == "/health":
            self._send_json({"status": "ok", "service": "zvec-rest-bridge"})
        
        # GET /collections → lister les collections
        elif parts == ["collections"]:
            try:
                logger.info("[Zvec-REST] Liste des collections")
                result = self.client.call_tool("zvec_list_collections", {})
                collections = result if isinstance(result, list) else []
                self._send_json({"collections": collections}, 200)
            except Exception as e:
                logger.error(f"[Zvec-REST] Erreur liste collections: {e}")
                self._send_error_json(str(e), 500)
        
        else:
            self._send_error_json("Not Found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        body = self._parse_body()
        
        logger.info(f"[Zvec-REST] POST {self.path} - Body: {body}")

        try:
            # POST /collections  →  créer collection
            if parts == ["collections"]:
                name = body.get("name")
                logger.info(f"[Zvec-REST] Création collection: {name}")
                distance = body.get("distance", "Cosine")
                enable_hybrid = body.get("enableHybrid", True)
                result = self.client.call_tool("zvec_create_collection", {
                    "name": name,
                    "distance": distance,
                    "enableHybrid": enable_hybrid
                })
                logger.info(f"[Zvec-REST] Collection créée: {result}")
                self._send_json(result, 201)

            # POST /collections/{name}/documents  →  ajouter document
            elif len(parts) == 3 and parts[0] == "collections" and parts[2] == "documents":
                collection = parts[1]
                doc_id = body.get("id")
                text = body.get("text", "")
                metadata = body.get("metadata", {})
                logger.info(f"[Zvec-REST] Ajout document {doc_id} à {collection}")
                result = self.client.call_tool("zvec_add_documents", {
                    "collection": collection,
                    "documents": [{"id": doc_id, "text": text, "metadata": metadata}]
                })
                logger.info(f"[Zvec-REST] Document ajouté: {result}")
                self._send_json(result, 200)

            # POST /collections/{name}/search  →  recherche sémantique
            elif len(parts) == 3 and parts[0] == "collections" and parts[2] == "search":
                collection = parts[1]
                query = body.get("query", "")
                limit = body.get("limit", 5)
                logger.info(f"[Zvec-REST] Recherche dans {collection}: '{query}'")
                result = self.client.call_tool("zvec_semantic_search", {
                    "collection": collection,
                    "query": query,
                    "limit": limit
                })
                logger.info(f"[Zvec-REST] Résultats: {len(result) if isinstance(result, list) else 0} items")
                self._send_json({"results": result if isinstance(result, list) else []}, 200)

            else:
                logger.warning(f"[Zvec-REST] Route non supportée: {parts}")
                self._send_error_json("Route non supportée", 404)

        except Exception as e:
            logger.error(f"[Zvec-REST] Erreur : {e}", exc_info=True)
            self._send_error_json(str(e), 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        body = self._parse_body()

        try:
            # DELETE /collections/{name}/documents  →  supprimer documents
            if len(parts) == 3 and parts[0] == "collections" and parts[2] == "documents":
                collection = parts[1]
                ids = body.get("ids", [])
                result = self.client.call_tool("zvec_delete_documents", {
                    "collection": collection,
                    "ids": ids
                })
                self._send_json(result, 200)
            else:
                self._send_error_json("Route non supportée", 404)
        except Exception as e:
            logger.error(f"[Zvec-REST] Erreur DELETE : {e}")
            self._send_error_json(str(e), 500)


# ---------------------------------------------------------------------------
# Gestionnaire HTTP Memory MCP (port 8002)
# ---------------------------------------------------------------------------

class MemoryHandler(BaseHTTPRequestHandler):
    """
    Gestionnaire HTTP qui traduit les appels REST en appels MCP Memory.

    Routes supportées :
      POST  /entities         → create_entities
      POST  /relations        → create_relations
      GET   /health           → status 200
    """

    client: MCPClient  # défini sur la classe par le serveur

    def log_message(self, format, *args):
        logger.info(f"[Memory-REST] {self.address_string()} {format % args}")

    def _parse_body(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, msg: str, status: int = 500):
        self._send_json({"error": msg}, status)

    # ------------------------------------------------------------------
    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self._send_json({"status": "ok", "service": "memory-rest-bridge"})
        else:
            self._send_error_json("Not Found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        body = self._parse_body()

        try:
            # POST /entities
            if parts == ["entities"]:
                entities = body.get("entities", [])
                result = self.client.call_tool("create_entities", {"entities": entities})
                self._send_json(result, 201)

            # POST /relations
            elif parts == ["relations"]:
                relations = body.get("relations", [])
                result = self.client.call_tool("create_relations", {"relations": relations})
                self._send_json(result, 201)

            else:
                self._send_error_json("Route non supportée", 404)

        except Exception as e:
            logger.error(f"[Memory-REST] Erreur : {e}")
            self._send_error_json(str(e), 500)


# ---------------------------------------------------------------------------
# Lancement des serveurs HTTP
# ---------------------------------------------------------------------------

def make_handler_class(handler_cls: type, mcp_client: MCPClient) -> type:
    """Crée une sous-classe du handler avec le client MCP injecté."""
    return type(
        f"{handler_cls.__name__}WithClient",
        (handler_cls,),
        {"client": mcp_client}
    )


def start_http_server(handler_cls: type, mcp_client: MCPClient, port: int) -> HTTPServer:
    """Démarre un serveur HTTP en arrière-plan dans un thread daemon."""
    BoundHandler = make_handler_class(handler_cls, mcp_client)
    server = HTTPServer(("127.0.0.1", port), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Serveur REST actif sur http://127.0.0.1:{port}")
    return server


# ---------------------------------------------------------------------------
# Vérification / auto-création des collections Zvec au démarrage
# ---------------------------------------------------------------------------

ZVEC_DEFAULT_COLLECTIONS = [
    "concepts_index",
    "entities_index",
    "actions_index",
    "relations_index",
    "context_index",
]

def ensure_zvec_collections(zvec_client: MCPClient):
    """Crée les collections Zvec par défaut si elles n'existent pas déjà."""
    try:
        existing_raw = zvec_client.call_tool("zvec_list_collections", {})
        # Le résultat peut être une liste ou un dict avec une clé 'collections'
        if isinstance(existing_raw, list):
            existing = {c.get("name") for c in existing_raw if isinstance(c, dict)}
        else:
            existing = set()

        for coll_name in ZVEC_DEFAULT_COLLECTIONS:
            if coll_name not in existing:
                logger.info(f"[Zvec] Création collection : {coll_name}")
                zvec_client.call_tool("zvec_create_collection", {
                    "name": coll_name,
                    "distance": "Cosine",
                    "enableHybrid": True
                })
            else:
                logger.info(f"[Zvec] Collection existante : {coll_name}")
    except Exception as e:
        logger.warning(f"[Zvec] Impossible de vérifier les collections : {e}")


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("RAG REST Bridge — démarrage")
    logger.info(f"  Zvec  : port {ZVEC_PORT}  →  {' '.join(ZVEC_SERVER_CMD)}")
    logger.info(f"  Memory: port {MEMORY_PORT} →  {' '.join(MEMORY_SERVER_CMD)}")
    logger.info(f"  ZVEC_DATA_DIR : {ZVEC_DATA_DIR}")
    logger.info("=" * 60)

    # Environnement Zvec — embedding via NVIDIA NIM (OpenAI-compatible)
    zvec_env = {
        "ZVEC_DATA_DIR": ZVEC_DATA_DIR,
        "EMBEDDING_PROVIDER": "openai",
        "EMBEDDING_MODEL": os.environ.get("RAG_ZVEC_MODEL", "nvidia/nemotron-3-embed-1b"),
        "EMBEDDING_DIMENSIONS": os.environ.get("RAG_ZVEC_DIMENSIONS", "2048"),
        "EMBEDDING_BASE_URL": "https://integrate.api.nvidia.com/v1",
        "ZVEC_BACKEND": "brute",
        "TRANSPORT_MODE": "stdio",
    }
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    if nvidia_key:
        zvec_env["OPENAI_API_KEY"] = nvidia_key

    # Environnement Memory MCP
    memory_env = {
        "MEMORY_FILE_PATH": MEMORY_DB_PATH,
        "AGENT_DB_ROOT": DB_ROOT,
        "TRANSPORT_MODE": "stdio",
        "LOG_LEVEL": "info"
    }

    # ------------------------------------------------------------------
    # Vérification des chemins avant de lancer
    # ------------------------------------------------------------------
    logger.info("🔍 Vérification des serveurs MCP...")
    for name, path in [("Zvec", ZVEC_MCP_PATH), ("Memory", MEMORY_MCP_PATH)]:
        logger.info(f"  {name}: {path} {'✅ existe' if Path(path).exists() else '❌ INEXISTANT'}")
        if not Path(path).exists():
            logger.error(f"⚠️ Erreur: Le serveur MCP {name} est introuvable à : {path}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # Démarrage des clients MCP
    # ------------------------------------------------------------------
    logger.info("🚀 Démarrage des clients MCP...")
    zvec_client = MCPClient("Zvec", ZVEC_SERVER_CMD, zvec_env)
    memory_client = MCPClient("Memory", MEMORY_SERVER_CMD, memory_env)

    logger.info("  Démarrage Zvec...")
    if not zvec_client.start():
        logger.error("❌ Impossible de démarrer Zvec MCP. Arrêt.")
        sys.exit(1)
    logger.info("  ✅ Zvec démarré")

    logger.info("  Démarrage Memory...")
    if not memory_client.start():
        logger.error("❌ Impossible de démarrer Memory MCP. Arrêt.")
        zvec_client.stop()
        sys.exit(1)
    logger.info("  ✅ Memory démarré")

    # ------------------------------------------------------------------
    # Démarrage des serveurs HTTP REST
    # ------------------------------------------------------------------
    zvec_server   = start_http_server(ZvecHandler,   zvec_client,   ZVEC_PORT)
    memory_server = start_http_server(MemoryHandler, memory_client, MEMORY_PORT)

    # Auto-création des collections (APRES ouverture des ports pour le health check)
    logger.info("Vérification des collections Zvec...")
    ensure_zvec_collections(zvec_client)

    logger.info("✅ RAG REST Bridge opérationnel — en attente de requêtes...")
    logger.info("   Ctrl+C pour arrêter.")

    # ------------------------------------------------------------------
    # Boucle principale (keepalive)
    # ------------------------------------------------------------------
    try:
        while True:
            # Vérifier que les processus MCP sont toujours vivants
            if zvec_client._proc and zvec_client._proc.poll() is not None:
                logger.warning("[Zvec] Le processus MCP s'est arrêté, redémarrage...")
                zvec_client.start()
            if memory_client._proc and memory_client._proc.poll() is not None:
                logger.warning("[Memory] Le processus MCP s'est arrêté, redémarrage...")
                memory_client.start()
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé.")
    finally:
        zvec_server.shutdown()
        memory_server.shutdown()
        zvec_client.stop()
        memory_client.stop()
        logger.info("RAG REST Bridge arrêté proprement.")


if __name__ == "__main__":
    main()
