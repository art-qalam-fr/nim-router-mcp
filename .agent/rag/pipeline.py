"""
Pipeline Module - Orchestration complète du système RAG

Ce module implémente le pipeline principal qui coordonne tous les
composants RAG: chunking, tagging, routing, embedding et fusion.

Classes:
    - RAGPipeline: Pipeline principal d'indexation et recherche
"""

from typing import List, Dict, Any, Optional, Iterable
from pathlib import Path
import json
import asyncio
import fnmatch
import argparse
import sys

# Support exécution en script direct (python pipeline.py) sans package.
try:
    from .chunker import Chunker, Chunk, ChunkType
    from .tagger import Tagger, Tag, TagCategory
    from .router import Router, RoutingDecision, StoreTarget
    from .embedder import EmbedderManager
    from .fusion import FusionEngine, SearchResult
    from .utils.env_loader import merge_config_with_env, get_workspace_root
except ImportError:  # pragma: no cover - fallback script
    base_dir = Path(__file__).resolve().parent
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))
    from chunker import Chunker, Chunk, ChunkType
    from tagger import Tagger, Tag, TagCategory
    from router import Router, RoutingDecision, StoreTarget
    from embedder import EmbedderManager
    from fusion import FusionEngine, SearchResult
    from utils.env_loader import merge_config_with_env, get_workspace_root


class RAGPipeline:
    """
    Pipeline principal RAG
    
    Orchestre le flux complet d'indexation et de recherche:
    1. Chunking: Découpage intelligent du document
    2. Tagging: Attribution de tags multi-dimensionnels
    3. Routing: Détermination des stores cibles
    4. Embedding: Génération et stockage des embeddings
    5. Memory: Stockage des relations dans Memory MCP
    
    Attributes:
        config: Configuration complète
        config_path: Chemin du fichier de configuration
        chunker: Module de chunking
        tagger: Module de tagging
        router: Module de routage
        embedder: Gestionnaire d'embeddings
        fusion: Moteur de fusion
    
    Example:
        >>> pipeline = RAGPipeline()
        >>> report = await pipeline.index_file("document.md")
        >>> results = await pipeline.search("requete")
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialise le pipeline RAG
        
        Args:
            config_path: Chemin vers le fichier de configuration.
                        Par défaut: .agent/rag/config.json
        """
        # Charger la configuration
        if config_path is None:
            config_path = str(Path(__file__).parent / "config.json")
        
        self.config_path = config_path
        self.config = self._load_config(config_path)
        
        # Initialiser les composants
        self.chunker = Chunker(self.config)
        self.tagger = Tagger(self.config)
        self.router = Router(self.config)
        self.embedder = EmbedderManager(self.config)
        self.fusion = FusionEngine(self.config)
        self.cache_config = (
            self.config.get("cache", {}).get("search", {"enabled": True, "max_entries": 50})
        )
        self._search_cache: Dict[str, List[SearchResult]] = {}
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Charge la configuration depuis un fichier JSON
        
        Les variables d'environnement ont priorité sur le JSON.
        
        Args:
            config_path: Chemin du fichier
            
        Returns:
            Configuration fusionnée avec les variables d'environnement
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config non trouvée à {config_path}, utilisation des défauts")
            config = self._default_config()
        except json.JSONDecodeError as e:
            print(f"Warning: Erreur JSON dans config: {e}, utilisation des défauts")
            config = self._default_config()
        
        # Fusionner avec les variables d'environnement
        config = merge_config_with_env(config)
        
        return config
    
    def _default_config(self) -> Dict[str, Any]:
        """
        Retourne une configuration par défaut
        
        Returns:
            Configuration par défaut
        """
        return {
            "chunking": {
                "default_size": 300,
                "overlap_percent": 10,
                "min_chunk_size": 50,
                "max_chunk_size": 1000,
                "types": {
                    "atomic": {"min": 50, "max": 100},
                    "modular": {"min": 200, "max": 500},
                    "contextual": {"min": 500, "max": 1000},
                    "structural": {"min": 100, "max": 2000}
                }
            },
            "tagging": {
                "auto_detect": True,
                "min_confidence": 0.7,
                "max_tags_per_chunk": 10
            },
            "routing": {
                "strategy": "dual",
                "fallback": "both"
            },
            "embedding": {
                "qdrant": {"enabled": True, "dimensions": 2048, "collections": {}},
                "zvec": {"enabled": True, "dimensions": 2048, "collections": {}}
            },
            "fusion": {
                "weights": {"qdrant": 0.4, "zvec": 0.4, "memory": 0.2},
                "max_results": 20,
                "min_results": 5,
                "deduplication": True
            },
            "cache": {
                "search": {"enabled": True, "max_entries": 50}
            }
        }
    
    async def ingest_workspace(
        self,
        root_path: Optional[str] = None,
        include_ext: Iterable[str] = (".md", ".txt", ".py", ".json", ".yaml", ".yml"),
        exclude_globs: Iterable[str] = (
            "**/.git/**",
            "**/.venv/**",
            "**/venv/**",
            "**/__pycache__/**",
            "**/.cursor/**",
            "**/.devin/**",
        ),
    ) -> Dict[str, Any]:
        """
        Indexe récursivement les fichiers du workspace.

        Chemins strictement relatifs (aucun chemin absolu n'est construit).
        """

        root = Path(root_path) if root_path else get_workspace_root()
        report: Dict[str, Any] = {
            "status": "success",
            "files_indexed": 0,
            "errors": [],
            "details": [],
        }

        def _is_excluded(p: Path) -> bool:
            rel = str(p)
            return any(fnmatch.fnmatch(rel, pattern) for pattern in exclude_globs)

        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in include_ext:
                continue
            if _is_excluded(file_path):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(file_path.relative_to(root))
                doc_type = self._guess_doc_type(file_path.suffix.lower())
                res = await self.index_document(
                    content=content,
                    doc_type=doc_type,
                    source_file=rel_path,
                    metadata={"source": "workspace", "relative_path": rel_path},
                )
                report["files_indexed"] += 1
                report["details"].append({"file": rel_path, "chunks": res.get("chunks_created", 0)})
            except Exception as e:
                report["status"] = "error" if report["files_indexed"] == 0 else "partial"
                report["errors"].append(f"{file_path}: {e}")
                print(f"[!] Erreur critique sur {file_path}: {e}")

        return report

    def _guess_doc_type(self, suffix: str) -> str:
        if suffix in {".py", ".js", ".ts", ".tsx", ".jsx"}:
            return "code"
        if suffix in {".md", ".markdown"}:
            return "markdown"
        if suffix in {".json", ".yaml", ".yml"}:
            return "json"
        return "text"

    async def index_document(
        self,
        content: str,
        doc_type: str = "text",
        source_file: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Indexe un document complet
        
        Args:
            content: Contenu du document
            doc_type: Type de document (text, code, markdown, json)
            source_file: Fichier source optionnel
            metadata: Métadonnées additionnelles
            
        Returns:
            Rapport d'indexation
        """
        report = {
            "status": "success",
            "chunks_created": 0,
            "tags_generated": 0,
            "qdrant_stored": 0,
            "zvec_stored": 0,
            "memory_relations": 0,
            "errors": [],
            "chunks": []
        }
        
        try:
            # 1. Chunking
            chunks = self.chunker.chunk_document(
                content=content,
                doc_type=doc_type,
                source_file=source_file
            )
            report["chunks_created"] = len(chunks)
            
            # 2. Traitement de chaque chunk
            for chunk in chunks:
                try:
                    chunk_report = await self._process_chunk(
                        chunk=chunk,
                        metadata=metadata
                    )
                    
                    report["tags_generated"] += chunk_report.get("tags_count", 0)
                    report["qdrant_stored"] += chunk_report.get("qdrant_stored", 0)
                    report["zvec_stored"] += chunk_report.get("zvec_stored", 0)
                    report["memory_relations"] += chunk_report.get("memory_relations", 0)
                    report["chunks"].append(chunk_report)
                    
                except Exception as e:
                    report["errors"].append(f"Chunk {chunk.id}: {str(e)}")
            
        except Exception as e:
            report["status"] = "error"
            report["errors"].append(str(e))
        
        return report
    
    async def _process_chunk(
        self,
        chunk: Chunk,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Traite un chunk individuel
        
        Args:
            chunk: Chunk à traiter
            metadata: Métadonnées additionnelles
            
        Returns:
            Rapport de traitement du chunk
        """
        report = {
            "chunk_id": chunk.id,
            "tags_count": 0,
            "qdrant_stored": 0,
            "zvec_stored": 0,
            "memory_relations": 0,
            "routing": None
        }
        
        # 1. Tagging
        tags = self.tagger.tag_chunk(chunk)
        report["tags_count"] = len(tags)
        
        # 2. Routing
        routing = self.router.route(chunk, tags)
        report["routing"] = routing.to_dict()
        
        # 3. Préparer les métadonnées
        chunk_metadata = {
            **(metadata or {}),
            **chunk.metadata,
            "tags": [t.to_dict() for t in tags],
            "routing": routing.to_dict(),
            "source_file": chunk.source_file,
            "chunk_type": chunk.type.value
        }
        
        # 4. Stockage Qdrant
        if routing.should_index_qdrant():
            for collection in routing.qdrant_collections:
                success = await self.embedder.qdrant.store(
                    collection=collection,
                    chunk_id=chunk.id,
                    content=chunk.content,
                    metadata=chunk_metadata
                )
                if success:
                    report["qdrant_stored"] += 1
        
        # 5. Stockage Zvec
        if routing.should_index_zvec():
            for collection in routing.zvec_collections:
                success = await self.embedder.zvec.store(
                    collection=collection,
                    chunk_id=chunk.id,
                    content=chunk.content,
                    metadata=chunk_metadata
                )
                if success:
                    report["zvec_stored"] += 1
        
        # 6. Memory MCP (relations)
        await self._store_memory_relations(chunk, tags)
        report["memory_relations"] = 1
        
        return report
    
    async def _store_memory_relations(self, chunk: Chunk, tags: List[Tag]) -> None:
        """
        Stocke les relations dans Memory MCP via l'API REST locale
        """
        import httpx
        import os
        
        # Récupération de l'URL depuis la config
        url_base = self.config.get("memory_mcp", {}).get("url", "http://localhost:8002")
        
        try:
            async with httpx.AsyncClient() as client:
                # 1. Créer l'entité chunk
                entity_payload = {
                    "entities": [
                        {
                            "name": chunk.id,
                            "entityType": "chunk",
                            "observations": [f"Source: {chunk.source_file}", chunk.content[:1000]]
                        }
                    ]
                }
                await client.post(f"{url_base}/entities", json=entity_payload, timeout=5.0)
                
                # 2. Créer les relations avec les tags
                relations = []
                for tag in tags:
                    # Construire nom et description depuis les attributs réels du Tag
                    tag_category = tag.category.value if hasattr(tag.category, 'value') else str(tag.category)
                    tag_name = f"tag:{tag_category}:{tag.key}:{tag.value}"
                    tag_desc = f"{tag_category}/{tag.key}={tag.value} (confidence={tag.confidence:.2f})"
                    # S'assurer que le tag existe en tant qu'entité
                    tag_entity = {"name": tag_name, "entityType": "tag", "observations": [tag_desc]}
                    await client.post(f"{url_base}/entities", json={"entities": [tag_entity]}, timeout=2.0)
                    
                    relations.append({
                        "from": chunk.id,
                        "to": tag_name,
                        "relationType": "has_tag"
                    })
                
                if relations:
                    await client.post(f"{url_base}/relations", json={"relations": relations}, timeout=5.0)
                    
        except Exception as e:
            # On log l'erreur mais on ne bloque pas le pipeline (Memory est souvent optionnel/lent)
            print(f"Note: Erreur stockage Memory MCP (Ignoré): {e}")
    
    async def index_file(self, file_path: str) -> Dict[str, Any]:
        """
        Indexe un fichier
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Rapport d'indexation
        """
        path = Path(file_path)
        
        # Vérifier l'existence
        if not path.exists():
            return {
                "status": "error",
                "errors": [f"Fichier non trouvé: {file_path}"]
            }
        
        # Détecter le type
        suffix = path.suffix.lower()
        type_map = {
            ".py": "code",
            ".js": "code",
            ".ts": "code",
            ".jsx": "code",
            ".tsx": "code",
            ".java": "code",
            ".go": "code",
            ".rs": "code",
            ".c": "code",
            ".cpp": "code",
            ".h": "code",
            ".md": "markdown",
            ".markdown": "markdown",
            ".json": "json",
            ".yaml": "config",
            ".yml": "config",
            ".toml": "config",
            ".ini": "config",
            ".env": "config",
            ".txt": "text",
            ".log": "log",
        }
        doc_type = type_map.get(suffix, "text")
        
        # Lire le contenu
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return {
                "status": "error",
                "errors": [f"Erreur lecture: {str(e)}"]
            }
        
        # Indexer
        return await self.index_document(
            content=content,
            doc_type=doc_type,
            source_file=str(path),
            metadata={
                "file_name": path.name,
                "file_extension": suffix,
                "file_size": path.stat().st_size if path.exists() else 0
            }
        )
    
    async def index_directory(
        self,
        dir_path: str,
        extensions: List[str] = None,
        exclude_patterns: List[str] = None
    ) -> Dict[str, Any]:
        """
        Indexe tous les fichiers d'un répertoire
        
        Args:
            dir_path: Chemin du répertoire
            extensions: Extensions à inclure (optionnel)
            exclude_patterns: Patterns à exclure (optionnel)
            
        Returns:
            Rapport d'indexation global
        """
        dir_path = Path(dir_path)
        
        if not dir_path.is_dir():
            return {
                "status": "error",
                "errors": [f"Répertoire non trouvé: {dir_path}"]
            }
        
        # Extensions par défaut
        if extensions is None:
            extensions = [
                ".py", ".js", ".ts", ".jsx", ".tsx",
                ".md", ".json", ".yaml", ".yml",
                ".txt"
            ]
        
        # Patterns d'exclusion par défaut
        if exclude_patterns is None:
            exclude_patterns = [
                "node_modules", ".git", "__pycache__",
                "dist", "build", ".venv", "venv"
            ]
        
        report = {
            "status": "success",
            "files_processed": 0,
            "files_failed": 0,
            "total_chunks": 0,
            "total_tags": 0,
            "errors": [],
            "files": []
        }
        
        # Parcourir les fichiers
        for file_path in dir_path.rglob("*"):
            # Vérifier l'extension
            if file_path.suffix.lower() not in extensions:
                continue
            
            # Vérifier les exclusions
            if any(pattern in str(file_path) for pattern in exclude_patterns):
                continue
            
            # Indexer le fichier
            file_report = await self.index_file(str(file_path))
            
            if file_report.get("status") == "success":
                report["files_processed"] += 1
                report["total_chunks"] += file_report.get("chunks_created", 0)
                report["total_tags"] += file_report.get("tags_generated", 0)
            else:
                report["files_failed"] += 1
            
            report["files"].append({
                "path": str(file_path),
                "status": file_report.get("status"),
                "chunks": file_report.get("chunks_created", 0)
            })
        
        return report
    
    async def search(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        limit: int = 10,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """
        Recherche hybride
        
        Args:
            query: Requête textuelle
            collections: Collections spécifiques (optionnel)
            limit: Nombre max de résultats
            filters: Filtres de métadonnées (optionnel)
            
        Returns:
            Résultats fusionnés
        """
        # Cache clé (query + collections + limit + filters)
        cache_key = self._make_cache_key(query, collections, limit, filters)
        if self._cache_enabled():
            cached = self._search_cache.get(cache_key)
            if cached is not None:
                return cached[:limit]

        qdrant_collections = collections or list(self.embedder.qdrant.collections.values())
        zvec_collections = collections or list(self.embedder.zvec.collections.values())

        results = await self.embedder.search_dual(
            query=query,
            qdrant_collections=qdrant_collections,
            zvec_collections=zvec_collections,
            limit=limit
        )

        memory_relations = await self._get_memory_relations(query)

        fused_results = await self.fusion.fuse(
            qdrant_results=results.get("qdrant", []),
            zvec_results=results.get("zvec", []),
            memory_relations=memory_relations
        )

        # Mise en cache (LRU simple)
        if self._cache_enabled():
            max_entries = int(self.cache_config.get("max_entries", 50))
            self._search_cache[cache_key] = fused_results[:limit]
            if max_entries > 0 and len(self._search_cache) > max_entries:
                first_key = next(iter(self._search_cache))
                self._search_cache.pop(first_key, None)

        return fused_results[:limit]

    def _make_cache_key(
        self,
        query: str,
        collections: Optional[List[str]],
        limit: int,
        filters: Optional[Dict]
    ) -> str:
        cols = tuple(collections) if collections else ()
        filt = tuple(sorted(filters.items())) if filters else ()
        return f"{query}|{cols}|{limit}|{filt}"

    def _cache_enabled(self) -> bool:
        return bool(self.cache_config.get("enabled", True))

    def clear_search_cache(self) -> None:
        self._search_cache.clear()
    
    async def _get_memory_relations(self, query: str) -> List[Dict]:
        """
        Récupère les relations depuis Memory MCP
        
        Args:
            query: Requête pour la recherche
            
        Returns:
            Liste de relations
        """
        import httpx
        url_base = self.config.get("memory_mcp", {}).get("url", "http://localhost:8002")
        
        try:
            async with httpx.AsyncClient() as client:
                # Recherche par similarité (si supporté par le bridge REST du MCP)
                response = await client.get(f"{url_base}/search?query={query}", timeout=5.0)
                if response.status_code == 200:
                    return response.json().get("results", [])
        except Exception as e:
            print(f"Erreur recherche Memory MCP: {e}")
        
        return []
    
    async def delete(self, chunk_id: str) -> Dict[str, Any]:
        """
        Supprime un chunk de tous les stores
        
        Args:
            chunk_id: ID du chunk
            
        Returns:
            Rapport de suppression
        """
        report = {
            "status": "success",
            "chunk_id": chunk_id,
            "qdrant_deleted": False,
            "zvec_deleted": False,
            "memory_deleted": False
        }
        
        # Supprimer des stores vectoriels
        report["qdrant_deleted"] = await self.embedder.qdrant.delete("all", chunk_id)
        report["zvec_deleted"] = await self.embedder.zvec.delete("all", chunk_id)
        
        # Supprimer de Memory MCP
        await self._delete_memory_entity(chunk_id)
        report["memory_deleted"] = True
        
        return report
    
    async def _delete_memory_entity(self, chunk_id: str) -> None:
        """
        Supprime l'entité de Memory MCP
        
        Args:
            chunk_id: ID du chunk
        """
        import httpx
        url_base = self.config.get("memory_mcp", {}).get("url", "http://localhost:8002")
        
        try:
            async with httpx.AsyncClient() as client:
                # 1. Identifier les entités liées au fichier
                # 2. Supprimer les entités
                await client.request("DELETE", f"{url_base}/entities", json={"source": file_path}, timeout=5.0)
        except Exception as e:
            print(f"Erreur nettoyage Memory MCP: {e}")
            
        success = True
        return success
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du pipeline
        
        Returns:
            Statistiques de configuration
        """
        return {
            "config_path": self.config_path,
            "chunking": {
                "default_size": self.chunker.chunking_config.get("default_size"),
                "overlap_percent": self.chunker.chunking_config.get("overlap_percent")
            },
            "tagging": {
                "min_confidence": self.tagger.tagging_config.get("min_confidence"),
                "max_tags": self.tagger.tagging_config.get("max_tags_per_chunk")
            },
            "embedding": {
                "qdrant_enabled": self.embedder.qdrant.enabled,
                "qdrant_dimensions": self.embedder.qdrant.dimensions,
                "zvec_enabled": self.embedder.zvec.enabled,
                "zvec_dimensions": self.embedder.zvec.dimensions
            },
            "fusion": {
                "weights": self.fusion.weights
            }
        }
    
    async def initialize(self) -> Dict[str, bool]:
        """
        Initialise toutes les collections vectorielles
        
        Returns:
            Résultats d'initialisation
        """
        return await self.embedder.initialize_collections()


# Fonction utilitaire pour créer un pipeline rapidement
def create_pipeline(config_path: str = None) -> RAGPipeline:
    """
    Crée un pipeline RAG
    
    Args:
        config_path: Chemin vers la configuration (optionnel)
        
    Returns:
        Instance de RAGPipeline
    """
    return RAGPipeline(config_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG Pipeline CLI (relative paths only)")
    parser.add_argument("command", choices=["ingest", "search"], help="Action à exécuter")
    parser.add_argument("--query", dest="query", help="Requête de recherche (search)")
    parser.add_argument("--root", dest="root", default=".", help="Racine workspace (ingest)")
    parser.add_argument("--limit", dest="limit", type=int, default=10, help="Limite résultats (search)")
    args = parser.parse_args()

    async def _main():
        pipeline = RAGPipeline()
        if args.command == "ingest":
            report = await pipeline.ingest_workspace(root_path=args.root)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.command == "search":
            query = args.query or "test"
            results = await pipeline.search(query=query, limit=args.limit)
            print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))

    asyncio.run(_main())
