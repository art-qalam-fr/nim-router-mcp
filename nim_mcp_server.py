"""
Serveur MCP stdio pour le routeur NVIDIA NIM — zéro dépendance.

Expose les outils :
  nim_domains()              → domaines routés + modèle primaire
  nim_models()               → model_ids servis live (GET /models)
  nim_chat(domain, prompt)   → chat routé par domaine (+fallbacks auto)
  nim_chat_model(model, ...) → appel direct par model_id
  nim_embed(texts)           → embeddings (domaine rag_embedding)

Le LLM n'a PAS besoin de la clé : elle est lue depuis .env (dossier parent)
ou la variable d'environnement NVIDIA_API_KEY.

Enregistrement MCP (stdio, newline-delimited JSON-RPC 2.0) :
  "nim-router": {
    "command": "python",
    "args": ["D:/!!Doc_Perso/NVIDIA_MODEL_API/mcp-server/nim_mcp_server.py"]
  }
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # NVIDIA_MODEL_API/
sys.path.insert(0, ROOT)

# Charger .env AVANT d'importer le routeur (clé non passée en config MCP)
_env = os.path.join(ROOT, ".env")
if os.path.exists(_env):
    for line in open(_env, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from router import NimRouter, NimError  # noqa: E402

# Le protocole MCP stdio exige UTF-8 — Windows sort en cp1252 par défaut
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

_router = None


def router():
    global _router
    if _router is None:
        _router = NimRouter()
    return _router


TOOLS = [
    {
        "name": "nim_domains",
        "description": "Liste les domaines routés et leur modèle primaire (agent_feedback, deep_analysis, code, vision, ...)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "nim_models",
        "description": "Liste live des model_ids NVIDIA NIM actuellement servis (GET /models)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "nim_chat",
        "description": "Chat via un domaine du registre : choisit le bon modèle + fallbacks automatiques",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "ex: deep_analysis, agent_feedback, fast_chat, code, french, math_stats"},
                "prompt": {"type": "string"},
                "system": {"type": "string", "description": "prompt système optionnel"},
                "max_tokens": {"type": "integer", "default": 2048},
                "thinking": {"type": "boolean", "description": "active le reasoning (nemotron-3)"},
            },
            "required": ["domain", "prompt"],
        },
    },
    {
        "name": "nim_chat_model",
        "description": "Chat direct sur un model_id précis (bypass du routage)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "ex: nvidia/nemotron-3-ultra-550b-a55b"},
                "prompt": {"type": "string"},
                "system": {"type": "string"},
                "max_tokens": {"type": "integer", "default": 2048},
                "thinking": {"type": "boolean"},
            },
            "required": ["model", "prompt"],
        },
    },
    {
        "name": "nim_embed",
        "description": "Vectorise des textes via le modèle d'embedding du domaine rag_embedding",
        "inputSchema": {
            "type": "object",
            "properties": {"texts": {"type": "array", "items": {"type": "string"}}},
            "required": ["texts"],
        },
    },
]


def call_tool(name, args):
    if name == "nim_domains":
        return router().list_domains()
    if name == "nim_models":
        return router().list_models()
    if name == "nim_chat":
        msgs = []
        if args.get("system"):
            msgs.append({"role": "system", "content": args["system"]})
        msgs.append({"role": "user", "content": args["prompt"]})
        return router().chat(args["domain"], msgs,
                             max_tokens=int(args.get("max_tokens", 2048)),
                             thinking=args.get("thinking"))
    if name == "nim_chat_model":
        msgs = []
        if args.get("system"):
            msgs.append({"role": "system", "content": args["system"]})
        msgs.append({"role": "user", "content": args["prompt"]})
        return router().chat_model(args["model"], msgs,
                                   max_tokens=int(args.get("max_tokens", 2048)),
                                   thinking=args.get("thinking"))
    if name == "nim_embed":
        embs = router().embed(args["texts"])
        return {"count": len(embs), "dim": len(embs[0]) if embs else 0,
                "embeddings": embs}
    raise NimError(f"Outil inconnu : {name}")


def respond(req_id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            respond(req_id, {
                "protocolVersion": req.get("params", {}).get(
                    "protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "nim-router", "version": "1.0.0"},
            })
        elif method == "notifications/initialized" or method == "initialized":
            pass
        elif method == "ping":
            respond(req_id, {})
        elif method == "tools/list":
            respond(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = req.get("params", {})
            try:
                out = call_tool(params.get("name"), params.get("arguments") or {})
                respond(req_id, {
                    "content": [{"type": "text",
                                 "text": json.dumps(out, ensure_ascii=False, indent=2)}],
                })
            except Exception as e:
                respond(req_id, {
                    "content": [{"type": "text", "text": f"ERREUR: {e}"}],
                    "isError": True,
                })
        elif method in ("resources/list", "prompts/list"):
            respond(req_id, {"resources" if "resources" in method else "prompts": []})
        elif req_id is not None:
            respond(req_id, error={"code": -32601, "message": f"Method not found: {method}"})


if __name__ == "__main__":
    main()
