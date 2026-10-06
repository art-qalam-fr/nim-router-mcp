"""
Embedder Module - Génération des embeddings et stockage vectoriel

Ce module implémente la génération d'embeddings pour Qdrant et Zvec via
NVIDIA NIM (nvidia/nemotron-3-embed-1b, 2048 dims), ainsi que le stockage
et la recherche.

Classes:
    - QdrantEmbedder: Embeddings via API OpenAI-compatible (NVIDIA par défaut, 2048 dim)
    - ZvecEmbedder: Embeddings via le bridge MCP Zvec (NVIDIA NIM, 2048 dim)
"""

from typing import List, Dict, Any, Optional
import json


# Endpoints et variables de clé par provider d'embedding (API OpenAI-compatible)
PROVIDER_EMBED_ENDPOINTS = {
    "nvidia": "https://integrate.api.nvidia.com/v1/embeddings",
    "openai": "https://api.openai.com/v1/embeddings",
}
PROVIDER_KEY_ENV = {
    "nvidia": "NVIDIA_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class QdrantEmbedder:
    """
    Gestion des embeddings Qdrant via API OpenAI-compatible.

    Provider configuré via RAG_QDRANT_PROVIDER (nvidia par défaut,
    nemotron-3-embed-1b en 2048 dims).

    Attributes:
        config: Configuration Qdrant depuis config.json
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialise l'embedder Qdrant

        Args:
            config: Configuration Qdrant depuis config.json
        """
        self.config = config
        self.provider = config.get("provider", "nvidia")
        self.dimensions = config.get("dimensions", 2048)
        self.model = config.get("model", "nvidia/nemotron-3-embed-1b")
        self.enabled = config.get("enabled", True)
        self.collections = config.get("collections", {})

    async def embed(self, text: str, input_type: str = "passage") -> List[float]:
        """
        Génère l'embedding via l'API du provider configuré (NVIDIA par défaut).
        input_type: 'passage' pour indexer, 'query' pour chercher (convention NIM).
        """
        if not self.enabled:
            return [0.0] * self.dimensions

        import httpx
        import os

        key_env = PROVIDER_KEY_ENV.get(self.provider, "NVIDIA_API_KEY")
        api_key = os.getenv(key_env) or os.getenv("NVIDIA_API_KEY")
        if not api_key:
            print(f"Warning: {key_env} non trouvée")
            return [0.0] * self.dimensions

        url = self.config.get("embed_url") or PROVIDER_EMBED_ENDPOINTS.get(
            self.provider, PROVIDER_EMBED_ENDPOINTS["nvidia"]
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": self.model,
            "input": [text],
            "input_type": input_type,
            "encoding_format": "float",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                if response.status_code == 200:
                    return response.json()["data"][0]["embedding"]
                else:
                    print(f"Erreur API embedding ({self.provider}): {response.text}")
                    return [0.0] * self.dimensions
        except Exception as e:
            print(f"Erreur génération embedding ({self.provider}): {e}")
            return [0.0] * self.dimensions
    
    async def store(
        self,
        collection: str,
        chunk_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Stocke un document dans Qdrant via l'API REST
        
        Args:
            collection: Nom de la collection
            chunk_id: ID unique du chunk (Haché si nécessaire)
            content: Contenu textuel
            metadata: Métadonnées du chunk
            
        Returns:
            True si succès
        """
        if not self.enabled:
            return False
            
        import httpx
        import hashlib
        
        # Qdrant nécessite un entier 64-bit ou un UUID
        # On génère un ID numérique depuis le chunk_id pour Qdrant
        qdrant_id_int = int(hashlib.sha256(chunk_id.encode()).hexdigest()[:16], 16)
        
        url = f"{self.config.get('url', 'http://localhost:6333')}/collections/{collection}/points?wait=true"
        
        # L'embedding est généré via le provider configuré (NVIDIA NIM par défaut)
        vector = await self.embed(content)
        
        # Vérifier la présence d'un tag moral Asimov pour boost éthique
        ethics_payload = {}
        tags = metadata.get("tags", {})
        if isinstance(tags, dict):
            context_tags = tags.get("contextuel", {})
            if context_tags.get("moral") == "asimov":
                ethics_payload = {"ethics_level": "high", "boost": 1.5}
        
        
        payload = {
            "points": [
                {
                    "id": qdrant_id_int,
                    "vector": {"dense": vector},  # Format hybride : vecteur nommé "dense"
                    "payload": {
                        **metadata,
                        **ethics_payload,
                        "content": content,
                        "source_id": chunk_id
                    }
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(url, json=payload, timeout=30.0)
                if response.status_code != 200:
                    raise Exception(f"API Qdrant error ({response.status_code}): {response.text}")
                return True
        except httpx.ConnectError:
            raise Exception(f"Connexion impossible au serveur Qdrant sur {url}. Le serveur est-il lance?")
        except Exception as e:
            print(f"Erreur stockage Qdrant: {e}")
            raise e
    
    async def search(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        filter_metadata: Dict = None
    ) -> List[Dict[str, Any]]:
        """
        Recherche sémantique dans Qdrant
        """
        if not self.enabled:
            return []
            
        import httpx
        url = f"{self.config.get('url', 'http://localhost:6333')}/collections/{collection}/points/search"
        
        # On génère l'embedding de la requête
        vector = await self.embed(query, input_type="query")
        
        payload = {
            "vector": {"dense": vector},  # Format hybride : vecteur nommé "dense"
            "limit": limit,
            "with_payload": True,
            "with_vector": False
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                if response.status_code == 200:
                    results = response.json().get("result", [])
                    return results
                return []
        except Exception as e:
            print(f"Erreur recherche Qdrant: {e}")
            return []
    
    async def delete(self, collection: str, chunk_id: str) -> bool:
        """
        Supprime un document de Qdrant
        
        Args:
            collection: Nom de la collection
            chunk_id: ID du chunk à supprimer
            
        Returns:
            True si succès
        """
        try:
            import httpx
            url = f"{self.config.get('url', 'http://localhost:6333')}/collections/{collection}/points/delete"
            
            payload = {
                "filter": {
                    "must": [
                        {
                            "key": "source_id",
                            "match": {"value": chunk_id}
                        }
                    ]
                }
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, timeout=5.0)
                return True
        except Exception as e:
            print(f"Erreur suppression Qdrant: {e}")
            return False
    
    async def create_collection(self, name: str) -> bool:
        """
        Crée une nouvelle collection Qdrant
        
        Args:
            name: Nom de la collection
            
        Returns:
            True si succès
        """
        try:
            import httpx
            url = f"{self.config.get('url', 'http://localhost:6333')}/collections/{name}"
            
            payload = {
                "vectors": {
                    "dense": {
                        "size": self.dimensions,
                        "distance": "Cosine"
                    }
                },
                "sparse_vectors": {
                    "text": {
                        "modifier": "idf"
                    }
                }
            }
            
            async with httpx.AsyncClient() as client:
                # Vérifier si elle existe déjà
                check = await client.get(url, timeout=2.0)
                if check.status_code != 200:
                    await client.put(url, json=payload, timeout=5.0)
                return True
        except Exception as e:
            print(f"Erreur création collection Qdrant: {e}")
            return False


class ZvecEmbedder:
    """
    Gestion des embeddings Zvec (2048 dimensions via NVIDIA NIM)

    Cette classe délègue la génération d'embeddings au bridge Zvec MCP,
    qui appelle l'API NVIDIA NIM (nvidia/nemotron-3-embed-1b).
    
    Attributes:
        config: Configuration Zvec
        model_name: Nom du modèle local
        enabled: Si Zvec est activé
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialise l'embedder Zvec
        
        Args:
            config: Configuration Zvec depuis config.json
        """
        self.config = config
        self.dimensions = config.get("dimensions", 2048)
        self.model = config.get("model", "nvidia/nemotron-3-embed-1b")
        self.enabled = config.get("enabled", True)
        self.collections = config.get("collections", {})
        self._model = None
        self._tokenizer = None
    
    def _load_model(self):
        """
        Charge le modèle local (lazy loading)
        
        Le modèle n'est chargé que lors de la première utilisation.
        """
        if self._model is None:
            try:
                from transformers import AutoTokenizer, AutoModel
                import torch
                
                self._tokenizer = AutoTokenizer.from_pretrained(self.model)
                self._model = AutoModel.from_pretrained(self.model)
            except ImportError:
                print("Warning: transformers non installé, utilisation MCP uniquement")
                self._model = False
    
    async def embed(self, text: str) -> List[float]:
        """
        Génère l'embedding localement
        
        Note: Cette méthode utilise l'outil MCP zvec qui gère
        automatiquement l'embedding local.
        
        Args:
            text: Texte à embedder
            
        Returns:
            Vecteur de 2048 dimensions (géré par MCP)
        """
        # L'embedding est géré automatiquement par le MCP Zvec
        return []
    
    async def store(
        self,
        collection: str,
        chunk_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Stocke un document dans Zvec via l'API REST locale
        """
        if not self.enabled:
            return False
        
        import httpx
        url = f"{self.config.get('url', 'http://localhost:8001')}/collections/{collection}/documents"
        
        payload = {
            "id": chunk_id,
            "text": content,
            "metadata": metadata
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=20.0)
                if response.status_code not in (200, 201):
                    raise Exception(f"API Zvec error ({response.status_code}): {response.text}")
                return True
        except httpx.ConnectError:
            raise Exception(f"Connexion impossible au serveur Zvec sur {url}. Le serveur est-il lance?")
        except Exception as e:
            print(f"Erreur stockage Zvec: {e}")
            raise e
    
    async def search(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        filter_metadata: Dict = None
    ) -> List[Dict[str, Any]]:
        """
        Recherche sémantique dans Zvec
        """
        if not self.enabled:
            return []
        
        import httpx
        url = f"{self.config.get('url', 'http://localhost:8001')}/collections/{collection}/search"
        
        payload = {
            "query": query,
            "limit": limit
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                if response.status_code == 200:
                    return response.json().get("results", [])
                return []
        except Exception as e:
            print(f"Erreur recherche Zvec: {e}")
            return []
    
    async def delete(self, collection: str, chunk_id: str) -> bool:
        """
        Supprime un document de Zvec
        
        Args:
            collection: Nom de la collection
            chunk_id: ID du chunk à supprimer
            
        Returns:
            True si succès
        """
        try:
            import httpx
            url = f"{self.config.get('url', 'http://localhost:8001')}/collections/{collection}/documents"
            
            async with httpx.AsyncClient() as client:
                await client.request("DELETE", url, json={"ids": [chunk_id]}, timeout=5.0)
                return True
        except Exception as e:
            print(f"Erreur suppression Zvec: {e}")
            return False
    
    async def create_collection(self, name: str) -> bool:
        """
        Crée une nouvelle collection Zvec
        
        Args:
            name: Nom de la collection
            
        Returns:
            True si succès
        """
        try:
            import httpx
            url = f"{self.config.get('url', 'http://localhost:8001')}/collections"
            
            payload = {
                "name": name,
                "distance": "Cosine",
                "enableHybrid": True
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, timeout=5.0)
                return True
        except Exception as e:
            print(f"Erreur création collection Zvec: {e}")
            return False


class EmbedderManager:
    """
    Gestionnaire centralisé des embedders
    
    Cette classe coordonne les embedders Qdrant et Zvec
    pour faciliter les opérations batch.
    
    Attributes:
        qdrant: Embedder Qdrant
        zvec: Embedder Zvec
        config: Configuration complète
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le gestionnaire d'embedders
        
        Args:
            config: Configuration complète du pipeline RAG
        """
        self.config = config
        embedding_config = config.get("embedding", {})
        
        self.qdrant = QdrantEmbedder(embedding_config.get("qdrant", {}))
        self.zvec = ZvecEmbedder(embedding_config.get("zvec", {}))
    
    async def store_dual(
        self,
        chunk_id: str,
        content: str,
        metadata: Dict[str, Any],
        qdrant_collections: List[str],
        zvec_collections: List[str]
    ) -> Dict[str, bool]:
        """
        Stocke dans les deux stores simultanément
        
        Args:
            chunk_id: ID du chunk
            content: Contenu textuel
            metadata: Métadonnées
            qdrant_collections: Collections Qdrant cibles
            zvec_collections: Collections Zvec cibles
            
        Returns:
            Résultats par store
        """
        results = {
            "qdrant": False,
            "zvec": False
        }
        
        # Stocker dans Qdrant
        for collection in qdrant_collections:
            if await self.qdrant.store(collection, chunk_id, content, metadata):
                results["qdrant"] = True
        
        # Stocker dans Zvec
        for collection in zvec_collections:
            if await self.zvec.store(collection, chunk_id, content, metadata):
                results["zvec"] = True
        
        return results
    
    async def search_dual(
        self,
        query: str,
        qdrant_collections: List[str],
        zvec_collections: List[str],
        limit: int = 10
    ) -> Dict[str, List[Dict]]:
        """
        Recherche dans les deux stores simultanément
        
        Args:
            query: Requête textuelle
            qdrant_collections: Collections Qdrant à rechercher
            zvec_collections: Collections Zvec à rechercher
            limit: Nombre max de résultats par store
            
        Returns:
            Résultats par store
        """
        results = {
            "qdrant": [],
            "zvec": []
        }
        
        # Rechercher dans Qdrant
        for collection in qdrant_collections:
            qdrant_results = await self.qdrant.search(collection, query, limit)
            results["qdrant"].extend(qdrant_results)
        
        # Rechercher dans Zvec
        for collection in zvec_collections:
            zvec_results = await self.zvec.search(collection, query, limit)
            results["zvec"].extend(zvec_results)
        
        return results
    
    async def delete_from_all(self, chunk_id: str) -> bool:
        """
        Supprime un chunk de tous les stores
        
        Args:
            chunk_id: ID du chunk à supprimer
            
        Returns:
            True si au moins une suppression réussie
        """
        success = False
        
        # Supprimer de toutes les collections Qdrant
        for collection in self.qdrant.collections.values():
            if await self.qdrant.delete(collection, chunk_id):
                success = True
        
        # Supprimer de toutes les collections Zvec
        for collection in self.zvec.collections.values():
            if await self.zvec.delete(collection, chunk_id):
                success = True
        
        return success
    
    async def initialize_collections(self) -> Dict[str, bool]:
        """
        Initialise toutes les collections configurées
        
        Returns:
            Résultats de création par collection
        """
        results = {}
        
        # Collections Qdrant
        for name in self.qdrant.collections.values():
            results[f"qdrant:{name}"] = await self.qdrant.create_collection(name)
        
        # Collections Zvec
        for name in self.zvec.collections.values():
            results[f"zvec:{name}"] = await self.zvec.create_collection(name)
        
        return results
