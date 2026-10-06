"""
RAG Module - Retrieval-Augmented Generation pour Hephaistos-Kit

Ce module implémente un système RAG modulaire avec double indexation vectorielle
(Qdrant + Zvec) permettant des recherches hybrides combinant approche catégorielle
et sémantique.

Modules:
    - chunker: Découpage intelligent de documents
    - tagger: Attribution de tags multi-dimensionnels
    - router: Routage dual vers Qdrant/Zvec
    - embedder: Génération des embeddings
    - fusion: Fusion des résultats de recherche
    - pipeline: Orchestration complète

Usage:
    from rag.pipeline import RAGPipeline
    
    pipeline = RAGPipeline()
    await pipeline.index_file("document.md")
    results = await pipeline.search("requete")
"""

__version__ = "1.0.0"
__author__ = "Hephaistos-Kit Team"

from .chunker import Chunker, Chunk, ChunkType
from .tagger import Tagger, Tag, TagCategory
from .router import Router, RoutingDecision, StoreTarget
from .fusion import FusionEngine, SearchResult
from .pipeline import RAGPipeline

__all__ = [
    "Chunker",
    "Chunk",
    "ChunkType",
    "Tagger",
    "Tag",
    "TagCategory",
    "Router",
    "RoutingDecision",
    "StoreTarget",
    "FusionEngine",
    "SearchResult",
    "RAGPipeline",
]
