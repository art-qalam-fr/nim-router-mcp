"""
NimRouter — routeur de modèles NVIDIA NIM par domaine d'application.

Zéro dépendance (urllib) : fonctionne tel quel sur Windows, Linux, Kaggle.

Usage:
    from router import NimRouter
    r = NimRouter()                          # lit NVIDIA_API_KEY (env ou .env voisin)
    r.chat("agent_feedback", [{"role": "user", "content": "..."}])
    r.chat_model("nvidia/nemotron-3-ultra-550b-a55b", msgs, thinking=True)
    r.embed(["texte à vectoriser"])
    r.list_domains()

Le mapping domaine → modèles vit dans registre-modeles.json (même dossier).
Ajouter un modèle = éditer le JSON, pas le code.
"""
import json
import os
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
REGISTRY_PATH = os.path.join(HERE, "registre-modeles.json")


class NimError(Exception):
    pass


class NimRouter:
    def __init__(self, api_key=None, base_url=None, registry_path=None,
                 max_retries=2, timeout=180):
        self._load_dotenv()
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY", "")
        if not self.api_key:
            raise NimError("NVIDIA_API_KEY manquant — https://build.nvidia.com/settings")
        self.base_url = (base_url or os.getenv("NVIDIA_BASE_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        self.max_retries = max_retries
        self.timeout = timeout
        with open(registry_path or REGISTRY_PATH, encoding="utf-8") as f:
            self.registry = json.load(f)

    # ── Registre ─────────────────────────────────────────────
    def list_domains(self):
        return {d: v.get("primary") for d, v in self.registry["domains"].items()
                if isinstance(v, dict) and v.get("primary")}

    def list_models(self):
        """Modèles réellement servis (appel live GET /models)."""
        return sorted(m["id"] for m in self._request("GET", "/models")["data"])

    def resolve(self, domain):
        """Domaine → liste ordonnée de model_ids [primary, *fallbacks]."""
        d = self.registry["domains"].get(domain)
        if not d or not d.get("primary"):
            raise NimError(f"Domaine inconnu : {domain}. "
                           f"Dispo : {', '.join(self.list_domains())}")
        return [d["primary"], *(d.get("fallback") or [])]

    # ── Chat ─────────────────────────────────────────────────
    def chat(self, domain, messages, **kw):
        """Chat via le domaine : essaie primary puis fallbacks."""
        last_err = None
        for model in self.resolve(domain):
            try:
                return self.chat_model(model, messages, **kw)
            except Exception as e:
                last_err = e
                time.sleep(1)
        raise NimError(f"Tous les modèles du domaine '{domain}' ont échoué. "
                       f"Dernière erreur : {last_err}")

    def chat_model(self, model, messages, temperature=0.6, max_tokens=2048,
                   top_p=0.95, thinking=None, stream=False, **extra):
        """Appel direct par model_id. `thinking=True` active le reasoning
        (famille nemotron-3 : enable_thinking)."""
        body = {
            "model": model, "messages": messages,
            "temperature": temperature, "top_p": top_p,
            "max_tokens": max_tokens, **extra,
        }
        if thinking is not None:
            body["chat_template_kwargs"] = {"enable_thinking": bool(thinking)}
        if stream:
            body["stream"] = True
            return self._stream(body)
        r = self._request("POST", "/chat/completions", body)
        msg = r["choices"][0]["message"]
        return {
            "content": msg.get("content") or "",
            "reasoning": msg.get("reasoning_content"),
            "model": r.get("model", model),
            "usage": r.get("usage"),
        }

    # ── Embeddings ───────────────────────────────────────────
    def embed(self, texts, domain="rag_embedding", input_type="query"):
        if isinstance(texts, str):
            texts = [texts]
        model = self.registry["domains"][domain]["primary"]
        r = self._request("POST", "/embeddings", {
            "model": model, "input": texts, "input_type": input_type,
        })
        return [d["embedding"] for d in r["data"]]

    # ── HTTP interne ─────────────────────────────────────────
    def _request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < self.max_retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                detail = e.read()[:300].decode("utf-8", "replace")
                raise NimError(f"HTTP {e.code} sur {path}: {detail}")
            except Exception:
                if attempt < self.max_retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise

    def _stream(self, body):
        """Générateur SSE — yields delta.content / reasoning_content."""
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0]["delta"]
                    yield {"content": delta.get("content"),
                           "reasoning": delta.get("reasoning_content")}
                except (KeyError, json.JSONDecodeError):
                    continue

    def _load_dotenv(self):
        env = os.path.join(HERE, ".env")
        if os.path.exists(env):
            for line in open(env, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = NimRouter()
    print("Domaines routés :")
    for d, m in r.list_domains().items():
        print(f"  {d:20s} → {m}")
    print("\nTest rapide 'fast_chat'...")
    out = r.chat("fast_chat", [{"role": "user", "content": "Dis: OK"}], max_tokens=16)
    print("→", out["content"][:80], f"({out['model']})")
