# REGISTRE INFRASTRUCTURE — source de vérité
Dernière vérification : 2026-10-04. Mettre à jour à chaque changement d'agent/provider/MCP.

## Agent exécutant par défaut

**`agy`** (abonnement, tous skills `*`, incl. `generate_image`).
Toute délégation sans précision d'agent va à cet agent. Pour changer le défaut : modifier cette ligne, pas les règles. Fallbacks one-shot : `kilo` (code) → `hermes` (debug/docs).

## Agents exécutants (enregistrés dans l'orchestrateur)

| Agent | Type | Skills | Commande | Quota |
|---|---|---|---|---|
| `agy` | CLI Antigravity | tous (`*`) | `agy.exe --dangerously-skip-permissions --print="{msg}" --print-timeout 600s` | Abonnement — **toujours dispo**, modèles Gemini/Claude via `--model` |
| `kilo` | KiloCode CLI | code, refactor, review, test | `kilo.exe run "{msg}" -m "{model}"` | Free/auto-free |
| `hermes` | Hermes CLI | code, debug, review, explore, docs, test | `hermes -z "{msg}"` | Config providers free |
| `devin` | Agent principal | architecture, orchestration | — | Agent IDE principal |

## Providers & modèles (ordre de préférence : local d'abord)

| Provider | État | Modèles notables | Usage |
|---|---|---|---|
| `ollama` local (:11434) | ✅ UP | qwen3.5:0.8b, qwen3:1.7b, gemma3:1b, deepseek-coder:1.3b (petits), qwen3.5:4b/9b, mistral:7b… | Routage, petites tâches (embeddings : **NVIDIA NIM**, pas Ollama) |
| `nvidia` NIM | ✅ | nemotron-3-embed-1b (2048D), nemotron-3-super-120b-a12b | **Embeddings (tous stores)**, chat cloud principal |
| `ollama` cloud | ✅ | gpt-oss:120b-cloud, nemotron-3-ultra, gemma4:31b | Gros raisonnement gratuit |
| `openrouter-free` | ✅ ~24 modèles `:free` | qwen3.8-27b, nex-n2.5, laguna, north-mini-code | Fallback quand Ollama off |
| `antigravity` (agy) | ✅ | gemini-3.8-flash + catalogue abo | Agent à tout faire garanti |
| llama.cpp | ⚠️ installé, **aucun GGUF** | — | Inutilisable sans télécharger un modèle |
| `gemini` CLI stock | ❌ **bloqué** | — | `IneligibleTierError` : Google exige un forfait Antigravity pour les comptes personnels. Ne pas utiliser, passer par `agy` |

## Orchestrateur MCP v2 (fork local, `<HEPHAISTOS_ROOT>\mcp\servers\orchestrator-server`)

Outils : `create_task` `update_task` `get_next_task` `register_agent` `update_agent` `list_agents` `list_tasks` `delete_task` **`dispatch_task`** `suggest_agent` `available_models` `set_prompt_template` `list_prompt_templates`

- `dispatch_task(title, task_type, context, files, workspace)` : choisit l'agent par skill → sonde les modèles free live (cache 60 s) → rend le prompt du rôle → crée+assigne+notifie le CLI.
- Rôles de prompt seedés : `code` `debug` `review` `docs` `test` `explore` (placeholders `{{task}} {{context}} {{files}} {{model}}`).
- Config agent JSON : `{skills:[], providers:[], command:"…{message} {model} {provider} {workspace}…", model_prefs:[], full_prompt:true/false}`.

## MCP actifs (Devin)

agentmemory, filesystem, qdrant, sequentialthinking, sqlite-node, zvec, orchestrator, model-discovery, kaggle, colab-mcp, notebooks, beacon, **nim-router** + `mcp-mux` (partagé multi-clients).

- `nim-router` : serveur autonome, package `nim-router-mcp` (sous-module `mcp/servers/nim-router-mcp` du kit : `nim_mcp_server.py` + `router.py` + `registre-modeles.json`). **Enregistré aux deux endroits** (même chemin absolu, synchronisés) : `%APPDATA%/devin/mcp_config.json` (serveur direct Devin, outils `nim_*` natifs) et `~/.config/mcp-mux/mcp-mux.json` (mux multi-clients, outils `mcp-mux.nim-router__nim_*` via mcporter). En cas de `Failed to connect/initialize` : vérifier le chemin dans les DEUX fichiers — ils se modifient indépendamment.
- `agy.exe` : `%LOCALAPPDATA%\agy\bin` est dans le **PATH utilisateur** (persistant). Un shell déjà ouvert conserve l'ancien PATH → rouvrir un shell, ou `export PATH="$PATH:$LOCALAPPDATA/agy/bin"` (bash) / `$env:Path += ";$env:LOCALAPPDATA\agy\bin"` (PowerShell). Ne jamais créer d'alias ou de shim.

## Règles d'usage

0. « **Sous-agents** » = les CLI agents externes (`agy`, `kilo`, `hermes`) délégués via `orchestrator.dispatch_task` / `acp-dispatch.mjs` / appel direct — distincts des *sub-agents* internes à l'IDE.
1. Toute délégation → `orchestrator.dispatch_task`, jamais de prompt CLI à la main.
2. `suggest_agent` en cas de doute sur le bon agent.
3. Modèle précis souhaité → `model_prefs` de l'agent via `update_agent`.
4. Nouveau rôle récurrent → `set_prompt_template` au lieu de réécrire le prompt.
5. Gemini CLI stock = indisponible pour les comptes personnels → utiliser `agy`.

## Problèmes connus

- ~~Collecteur Beacon non supervisé~~ → **RÉSOLU** : service Windows `BeaconCollector` (démarrage automatique), survit au logout.
- llama.cpp sans modèle — inutilisé.
- Orchestrateur présent dans Devin direct ET mcp-mux : **volontaire**, même DB partagée (WAL). Ne pas "corriger".
