---
name: hephaistos-kit
description: "Kit d'infrastructure agent injectable : installe/met à jour le standard .agent/ (règles, skills, agents, workflows, scripts) dans un projet. À invoquer pour injecter, mettre à jour, restaurer ou réparer la configuration agent d'un projet, ou quand l'utilisateur dit 'hephaistos', 'injecte le kit', 'répare .agent'."
---

# Hephaistos-Kit — infrastructure agent injectable

> Le kit est le **template canonique** de l'infrastructure agent. Un projet injecté reçoit
> `.agent/` complet + `.vscode/`. Source : `github.com/art-qalam-fr/Hephaistos-Kit`.
> Template local : `<KIT_ROOT>`.

## Ce que le kit injecte

| Élément | Rôle |
|---|---|
| `.agent/rules/global_rules.md` | Règles universelles (délégation CLI, OpenCLI/puppeteer, uv, mémoire unifiée) |
| `.agent/agents/*.md` | Définitions d'agents + triggers de routage |
| `.agent/skills/*/` | ~45 skills métier (dont `hephaistos-kit`, `orchestrator`) |
| `.agent/workflows/`, `knowledge/`, `memory/` | Workflows slash-commands, docs mémoire |
| `.agent/scripts/` | Infra : `run_chrome_opencli.bat`, `beacon-sync.ps1`, `ingest-workspace.ps1`… |
| `.agent/devin/`, `.agent/hermes/` | Hooks Devin + couche Hermes |
| `.agent/REGISTRY.md` | Registre agents/providers + **agent par défaut** |
| `.vscode/` | Configs MCP partagées |

## Commandes

```bash
hephaistos-kit init              # injecte .agent/ + .vscode/ dans le cwd
hephaistos-kit init --path <dir> # autre cible
hephaistos-kit init --dry-run    # simulation, rien n'est copié
hephaistos-kit update --force    # = init --force : réaligne sur le template
```

Depuis le repo local sans install : `node <KIT_ROOT>\bin\hephaistos-kit.js init`.

## Préservations automatiques (update/--force)

Le kit ne détruit **jamais** :
- `.agent/memory-database/` — index vectoriels/caches du projet
- `.agent/rules/local_rules.md` — règles spécifiques au projet

Si un dossier est verrouillé (`EBUSY`), fallback merge-copy au lieu d'échouer.
Sont exclus de la copie : `*.log`, `*.pid`, `__pycache__`, `node_modules`.

## Réparer une injection ratée / .agent corrompu

1. **Processus résiduels** : tuer `monitor.js`, `revue serve`, scripts `.agent/` —
   un watcher ouvert verrouille les dossiers (EBUSY).
2. **Injection partielle** (`.agent` à moitié vide) : relancer `init --force` —
   le merge-copy complète sans rien perdre.
3. **Dossier zombie** (handle fantôme qui refuse rmdir même après kill) : le
   merge-copy le remplit quand même ; un reboot libère le handle résiduel.
4. **`local_rules.md` perdu** (cas ancien kit) : `git checkout .agent/rules/local_rules.md`.
5. **Vérification post-injection** : `REGISTRY.md` présent, `local_rules.md` intact,
   `memory-database/` non vide si données, `git status` → review du diff.

## Après injection dans un projet

- Committer `.agent/` (sauf fichiers runtime gitignorés : `*.log`, `*.pid`, `.ingestion-state.json`).
- Vérifier que le projet tourne toujours (tests).
- Le `local_rules.md` du projet complète — jamais remplacé par — les règles globales.

## Modifier le kit lui-même

Le template vit dans le repo `Hephaistos-Kit` : éditer `.agent/` à la racine du repo,
commit, push → la prochaine injection embarque la modif. Ne jamais y mettre de
données runtime (logs, pids, bases) ni de secrets.

## Stack MCP (`mcp/`)

Le kit embarque aussi la stack MCP canonique : `mcp/manifest.json` (18 serveurs),
sous-modules dans `mcp/servers/` (chaque MCP = son repo épinglé), `install.ps1`
(clone → build → génère la config de l'IDE), fiches `mcp/cards/`.
Secrets : noms de variables uniquement — valeurs dans `~/.hephaistos/env.local`.
Voir `mcp/README.md`.
