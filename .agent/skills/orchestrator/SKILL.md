---
name: orchestrator
description: "Délégation intelligente multi-agents via l'orchestrateur MCP v2 : dispatch_task choisit l'agent par skill, le modèle free live, et le prompt de rôle. À invoquer pour toute tâche à sous-traiter (code, debug, review, docs, test, explore) ou quand l'utilisateur dit 'orchestrateur' / 'dispatche' / 'délègue'."
---

# Orchestrateur intelligent — délégation multi-agents

> Le rôle de l'agent principal (Devin/Antigravity) est **architecte** : planifier, dispatcher, vérifier, synthétiser. L'exécution va aux agents CLI enregistrés.

## Déclencheurs

Utiliser ce skill quand : l'utilisateur dit « orchestrateur », « dispatche », « délègue », ou qu'une tâche doit partir vers un autre agent (code, debug, review, docs, test, explore).

## Pré-requis (rapide)

1. Lire `.agent/REGISTRY.md` — agents réels, skills, providers, outils morts (Trae abandonné, `gemini` CLI stock bloqué → `agy` à la place, llama.cpp sans modèle).
2. `orchestrator.list_agents` — agents actifs + leur `config` JSON (`skills`, `providers`, `command`, `model_prefs`, `full_prompt`).
3. Agents enregistrés connus : `agy` (Antigravity CLI, abonnement, toujours dispo, skills `*`), `kilo` (code/refactor/review/test), `hermes` (code/debug/review/explore/docs/test).

## Procédure de délégation

```
dispatch_task(title, task_type, context, files, workspace, [agent_name], [priority])
```

1. **`task_type`** parmi `code` | `debug` | `review` | `docs` | `test` | `explore` — détermine le prompt de rôle et le matching de skills.
2. **`context`** : le spécifique — problème, objectif, contraintes. Pas besoin de rédiger le prompt complet, le template du rôle s'en charge.
3. **`files`** : fichiers concernés (tableau de chemins).
4. **`agent_name`** : optionnel, force un agent précis. Sinon le routeur choisit par skill (puis wildcard `*`).
5. L'orchestrateur sonde les modèles free **à l'instant T** (Ollama local + OpenRouter `:free`, cache 60 s), respecte `providers`/`model_prefs` de l'agent, rend le prompt, crée la tâche, assigne et **notifie le CLI de l'agent**.

## Outils utiles autour

- `suggest_agent(task_type)` → quel agent matcherait, avec la config de tous les agents.
- `available_models` → modèles free/local up maintenant.
- `set_prompt_template(role, template)` → créer un rôle custom (placeholders `{{task}} {{context}} {{files}} {{model}}`). Rôles seedés : code, debug, review, docs, test, explore.
- `update_agent(agent_name, config)` → ajuster skills/providers/command/model_prefs.
- `list_tasks` / `update_task` / `get_next_task` / `create_task` — cycle de vie classique (create_task = sans notification).

## Règles

- **Modèles gratuits uniquement** pour les délégations CLI (sauf `agy` : abonnement inclus).
- **Jamais de SQL direct** sur orchestrator.db — uniquement les outils MCP.
- **`full_prompt:true`** dans la config agent = le CLI reçoit le prompt complet (agents sans accès MCP orchestrator, ex: `agy --print`). Sinon ils reçoivent « va lire la tâche #N ».
- Vérifier le retour de `dispatch_task` : `warning` signale l'absence de modèle free trouvé.
- Fallback one-shot si orchestrateur down : `hermes -z "<prompt>"` ou `agy --print "<prompt>"`.

## Pièges

- Ne PAS utiliser `gemini` CLI stock — `IneligibleTierError` sur ce compte ; passer par `agy.exe`.
- Un agent sans `skills` dans sa config ne sera jamais choisi automatiquement — `update_agent` pour le déclarer, ou `agent_name` pour forcer.
- `dispatch_task` réveille réellement le CLI de l'agent : ne pas l'appeler « pour voir ».
