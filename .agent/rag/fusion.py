"""
Fusion Module - Fusion des résultats de recherche hybride

Ce module implémente la fusion des résultats provenant de Qdrant
(catégorique) et Zvec (sémantique) avec boost des relations Memory MCP.

Classes:
    - SearchResult: Résultat de recherche unifié
    - FusionEngine: Moteur de fusion
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import defaultdict


@dataclass
class SearchResult:
    """
    Résultat de recherche unifié
    
    Représente un résultat après fusion des sources Qdrant,
    Zvec et Memory MCP.
    
    Attributes:
        chunk_id: ID du chunk
        content: Contenu textuel
        score: Score combiné final
        qdrant_score: Score Qdrant (catégorique)
        zvec_score: Score Zvec (sémantique)
        memory_boost: Boost Memory MCP (relations)
        source: Source principale du résultat
        metadata: Métadonnées du chunk
    """
    chunk_id: str
    content: str
    score: float = 0.0
    qdrant_score: float = 0.0
    zvec_score: float = 0.0
    memory_boost: float = 0.0
    source: str = "hybrid"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit le résultat en dictionnaire
        
        Returns:
            Dictionnaire représentant le résultat
        """
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "qdrant_score": self.qdrant_score,
            "zvec_score": self.zvec_score,
            "memory_boost": self.memory_boost,
            "source": self.source,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchResult':
        """
        Crée un résultat depuis un dictionnaire
        
        Args:
            data: Dictionnaire source
            
        Returns:
            Instance de SearchResult
        """
        return cls(
            chunk_id=data.get("chunk_id", data.get("id", "")),
            content=data.get("content", data.get("text", "")),
            score=data.get("score", 0.0),
            qdrant_score=data.get("qdrant_score", 0.0),
            zvec_score=data.get("zvec_score", 0.0),
            memory_boost=data.get("memory_boost", 0.0),
            source=data.get("source", "hybrid"),
            metadata=data.get("metadata", {})
        )
    
    def __hash__(self) -> int:
        """Hash pour déduplication"""
        return hash(self.chunk_id)
    
    def __eq__(self, other) -> bool:
        """Égalité pour déduplication"""
        if not isinstance(other, SearchResult):
            return False
        return self.chunk_id == other.chunk_id


class FusionEngine:
    """
    Moteur de fusion des résultats de recherche
    
    Le FusionEngine combine les résultats de Qdrant et Zvec
    en appliquant des poids configurables et un boost Memory MCP.
    
    Attributes:
        config: Configuration complète du pipeline RAG
        fusion_config: Configuration spécifique à la fusion
        weights: Poids pour chaque source
    
    Example:
        >>> config = {"fusion": {"weights": {"qdrant": 0.4, ...}}}
        >>> engine = FusionEngine(config)
        >>> results = await engine.fuse(qdrant_results, zvec_results, memory_relations)
    """
    
    # Boost par type de relation Memory MCP
    RELATION_BOOST = {
        "contains": 0.1,
        "stored_in": 0.05,
        "relates_to": 0.2,
        "references": 0.15,
        "depends_on": 0.1,
        "implements": 0.15,
        "extends": 0.1,
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le moteur de fusion
        
        Args:
            config: Configuration complète du pipeline RAG
        """
        self.config = config
        self.fusion_config = config.get("fusion", {
            "weights": {
                "qdrant": 0.4,
                "zvec": 0.4,
                "memory": 0.2
            },
            "min_results": 5,
            "max_results": 20,
            "deduplication": True
        })
        self.weights = self.fusion_config.get("weights", {
            "qdrant": 0.4,
            "zvec": 0.4,
            "memory": 0.2
        })
    
    async def fuse(
        self,
        qdrant_results: List[Dict],
        zvec_results: List[Dict],
        memory_relations: List[Dict]
    ) -> List[SearchResult]:
        """
        Fusionne les résultats de toutes les sources
        
        Args:
            qdrant_results: Résultats de Qdrant
            zvec_results: Résultats de Zvec
            memory_relations: Relations de Memory MCP
            
        Returns:
            Résultats fusionnés et triés
        """
        # 1. Indexer les résultats par chunk_id
        results_map: Dict[str, SearchResult] = {}
        
        # 2. Ajouter résultats Qdrant
        for result in qdrant_results:
            chunk_id = self._extract_id(result)
            results_map[chunk_id] = SearchResult(
                chunk_id=chunk_id,
                content=self._extract_content(result),
                score=0.0,
                qdrant_score=result.get("score", 0.8),
                zvec_score=0.0,
                memory_boost=0.0,
                source="qdrant",
                metadata=result.get("metadata", result.get("payload", {}))
            )
        
        # 3. Ajouter/fusionner résultats Zvec
        for result in zvec_results:
            chunk_id = self._extract_id(result)

            if chunk_id in results_map:
                results_map[chunk_id].zvec_score = result.get("score", 0.8)
                results_map[chunk_id].source = "hybrid"
            else:
                results_map[chunk_id] = SearchResult(
                    chunk_id=chunk_id,
                    content=self._extract_content(result),
                    score=0.0,
                    qdrant_score=0.0,
                    zvec_score=result.get("score", 0.8),
                    memory_boost=0.0,
                    source="zvec",
                    metadata=result.get("metadata", {})
                )

        # 4. Appliquer les boosts Memory MCP
        relation_boosts = self._compute_memory_boosts(memory_relations)
        for chunk_id, boost in relation_boosts.items():
            if chunk_id not in results_map:
                results_map[chunk_id] = SearchResult(
                    chunk_id=chunk_id,
                    content="",
                    score=0.0,
                    qdrant_score=0.0,
                    zvec_score=0.0,
                    memory_boost=boost,
                    source="memory",
                    metadata={}
                )
            else:
                results_map[chunk_id].memory_boost = boost

        # 5. Calculer le score final avec pondérations
        wq = self.weights.get("qdrant", 0.4)
        wz = self.weights.get("zvec", 0.4)
        wm = self.weights.get("memory", 0.2)

        for result in results_map.values():
            result.score = (
                (result.qdrant_score or 0.0) * wq +
                (result.zvec_score or 0.0) * wz +
                (result.memory_boost or 0.0) * wm
            )

        # 6. Rerank: Boost éthique Asimov (1.5x si ethics_level=high)
        for result in results_map.values():
            ethics_level = result.metadata.get("ethics_level", "")
            if ethics_level == "high":
                result.score = min(result.score * 1.5, 1.0)

        # 7. Déduplication, tri et contraintes min/max
        fused = sorted(results_map.values(), key=lambda r: r.score, reverse=True)
        min_results = self.fusion_config.get("min_results", 5)
        max_results = self.fusion_config.get("max_results", 20)
        fused = fused[:max_results]
        if len(fused) < min_results:
            fused = fused

        return fused
    
    def _extract_id(self, result: Dict) -> str:
        """
        Extrait l'ID d'un résultat (format variable selon source)
        
        Args:
            result: Résultat de recherche
            
        Returns:
            ID du chunk
        """
        return result.get("id", result.get("chunk_id", result.get("document_id", "")))
    
    def _extract_content(self, result: Dict) -> str:
        """
        Extrait le contenu d'un résultat
        
        Args:
            result: Résultat de recherche
            
        Returns:
            Contenu textuel
        """
        return result.get("content", result.get("text", result.get("document", "")))
    
    def _calculate_score(
        self,
        qdrant_score: float,
        zvec_score: float,
        memory_boost: float
    ) -> float:
        """
        Calcule le score combiné pondéré
        
        Args:
            qdrant_score: Score Qdrant (0.0 - 1.0)
            zvec_score: Score Zvec (0.0 - 1.0)
            memory_boost: Boost Memory MCP (0.0 - 0.5)
            
        Returns:
            Score combiné (0.0 - 1.0)
        """
        score = (
            self.weights.get("qdrant", 0.4) * qdrant_score +
            self.weights.get("zvec", 0.4) * zvec_score +
            self.weights.get("memory", 0.2) * memory_boost
        )
        
        return min(score, 1.0)

    def _compute_memory_boosts(self, memory_relations: List[Dict]) -> Dict[str, float]:
        """
        Calcule les boosts Memory MCP pour chaque chunk

        Args:
            memory_relations: Relations de Memory MCP

        Returns:
            Dictionnaire {chunk_id: boost_value}
        """
        boosts: Dict[str, float] = {}
        for relation in memory_relations:
            chunk_id = relation.get("to", relation.get("target", ""))
            rel_type = relation.get("relationType", "relates_to")
            boost = self.RELATION_BOOST.get(rel_type, 0.05)
            if chunk_id:
                boosts[chunk_id] = max(boosts.get(chunk_id, 0.0), boost)
        return boosts
    
    def _rank(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Trie les résultats par score décroissant
        
        Args:
            results: Résultats à trier
            
        Returns:
            Résultats triés
        """
        return sorted(results, key=lambda r: r.score, reverse=True)
    
    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Déduplique les résultats par chunk_id
        
        Args:
            results: Résultats à dédupliquer
            
        Returns:
            Résultats uniques
        """
        seen = set()
        unique = []
        
        for result in results:
            if result.chunk_id not in seen:
                seen.add(result.chunk_id)
                unique.append(result)
        
        return unique
    
    def get_fusion_stats(self, results: List[SearchResult]) -> Dict[str, Any]:
        """
        Calcule les statistiques de fusion
        
        Args:
            results: Résultats fusionnés
            
        Returns:
            Statistiques de fusion
        """
        stats = {
            "total": len(results),
            "hybrid": 0,
            "qdrant_only": 0,
            "zvec_only": 0,
            "avg_score": 0.0,
            "avg_qdrant_score": 0.0,
            "avg_zvec_score": 0.0,
            "avg_memory_boost": 0.0,
        }
        
        if not results:
            return stats
        
        for result in results:
            if result.source == "hybrid":
                stats["hybrid"] += 1
            elif result.source == "qdrant":
                stats["qdrant_only"] += 1
            elif result.source == "zvec":
                stats["zvec_only"] += 1
            
            stats["avg_score"] += result.score
            stats["avg_qdrant_score"] += result.qdrant_score
            stats["avg_zvec_score"] += result.zvec_score
            stats["avg_memory_boost"] += result.memory_boost
        
        count = len(results)
        stats["avg_score"] /= count
        stats["avg_qdrant_score"] /= count
        stats["avg_zvec_score"] /= count
        stats["avg_memory_boost"] /= count
        
        return stats
    
    def adjust_weights(self, weights: Dict[str, float]) -> None:
        """
        Ajuste les poids de fusion
        
        Args:
            weights: Nouveaux poids {qdrant, zvec, memory}
        """
        # Normaliser les poids
        total = sum(weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in weights.items()}
    
    def get_top_k_by_source(
        self,
        results: List[SearchResult],
        source: str,
        k: int = 5
    ) -> List[SearchResult]:
        """
        Retourne les top-k résultats d'une source spécifique
        
        Args:
            results: Tous les résultats
            source: Source à filtrer
            k: Nombre de résultats
            
        Returns:
            Top-k résultats de la source
        """
        filtered = [r for r in results if source in r.source]
        return sorted(filtered, key=lambda r: r.score, reverse=True)[:k]
