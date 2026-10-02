<p align="center">
  <img src="https://raw.githubusercontent.com/art-qalam-fr/Hephaistos-Kit/main/logo/hephaistos-kit_banderole.jfif" alt="Hephaistos-Kit" width="640"/>
</p>

> Ce dépôt est un **composant MCP du [Hephaistos-Kit](https://github.com/art-qalam-fr/Hephaistos-Kit)** —
> utilisable seul, mais conçu pour être cloné en sous-module et installé via `mcp/install.ps1`.
>
> ✍️ Élaboré par **art-qalam-fr**.

---

# nim-router-mcp

MCP serveur de routage vers **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`).
Expose les modèles Nemotron aux agents via MCP. Clé via `NVIDIA_API_KEY` (jamais dans le code).

## Install

```bash
uv tool install .   # ou pip install mcp + configurer le serveur
```

Config MCP : `command: python`, `args: ["<path>/nim_mcp_server.py"]`, `env: NVIDIA_API_KEY`.
