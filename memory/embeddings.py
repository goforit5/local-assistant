"""Embedding storage with ChromaDB."""

import os
import uuid
from typing import List, Dict, Any, Optional, Union

import chromadb
from chromadb.config import Settings
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection


class EmbeddingStore:
    """Vector embedding storage with ChromaDB."""

    def __init__(
        self,
        collection_name: str = "documents",
        host: Optional[str] = None,
        port: Optional[int] = None,
        persist_directory: Optional[str] = None
    ):
        """Initialize embedding store.

        Args:
            collection_name: Name of ChromaDB collection
            host: ChromaDB server host. Defaults to CHROMA_HOST env var.
            port: ChromaDB server port. Defaults to CHROMA_PORT env var.
            persist_directory: Local persistence directory for embedded mode.
                              If None, uses client/server mode.
        """
        self.collection_name = collection_name
        self.host = host or os.getenv("CHROMA_HOST", "localhost")
        self.port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self.persist_directory = persist_directory
        self.client: Optional[ClientAPI] = None
        self.collection: Optional[Collection] = None

    async def initialize(self) -> None:
        """Initialize ChromaDB client and collection."""
        if self.persist_directory:
            # Embedded mode with local persistence
            self.client = chromadb.Client(
                Settings(
                    persist_directory=self.persist_directory,
                    anonymized_telemetry=False
                )
            )
        else:
            # Client/server mode
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=Settings(anonymized_telemetry=False)
            )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Document embeddings for local assistant"}
        )

    async def close(self) -> None:
        """Close ChromaDB client connection."""
        # ChromaDB doesn't require explicit cleanup
        pass

    def add(
        self,
        documents: Union[str, List[str]],
        embeddings: Optional[Union[List[float], List[List[float]]]] = None,
        metadatas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        ids: Optional[Union[str, List[str]]] = None
    ) -> List[str]:
        """Add documents and embeddings to collection.

        Args:
            documents: Single document or list of documents
            embeddings: Optional embeddings. If None, ChromaDB generates them.
            metadatas: Optional metadata dict or list of metadata dicts
            ids: Optional ID or list of IDs. If None, generates UUIDs.

        Returns:
            List of document IDs
        """
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        # Normalize inputs to lists
        if isinstance(documents, str):
            documents = [documents]

        if embeddings is not None and isinstance(embeddings[0], (int, float)):
            embeddings = [embeddings]

        if metadatas is not None and not isinstance(metadatas, list):
            metadatas = [metadatas]

        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        elif isinstance(ids, str):
            ids = [ids]

        # Add to collection
        add_kwargs = {
            "documents": documents,
            "ids": ids
        }

        if embeddings is not None:
            add_kwargs["embeddings"] = embeddings

        if metadatas is not None:
            add_kwargs["metadatas"] = metadatas

        self.collection.add(**add_kwargs)
        return ids

    def query(
        self,
        query_texts: Optional[Union[str, List[str]]] = None,
        query_embeddings: Optional[Union[List[float], List[List[float]]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Query collection for similar documents.

        Args:
            query_texts: Query text(s) to find similar documents
            query_embeddings: Query embedding(s) to find similar documents
            n_results: Number of results to return per query
            where: Metadata filter conditions
            where_document: Document content filter conditions
            include: Fields to include in results (embeddings, metadatas, documents, distances)

        Returns:
            Dictionary with keys: ids, embeddings, metadatas, documents, distances
        """
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        if query_texts is None and query_embeddings is None:
            raise ValueError("Must provide either query_texts or query_embeddings")

        # Normalize inputs
        if query_texts is not None and isinstance(query_texts, str):
            query_texts = [query_texts]

        if query_embeddings is not None and isinstance(query_embeddings[0], (int, float)):
            query_embeddings = [query_embeddings]

        # Default include fields
        if include is None:
            include = ["metadatas", "documents", "distances"]

        query_kwargs = {
            "n_results": n_results,
            "include": include
        }

        if query_texts is not None:
            query_kwargs["query_texts"] = query_texts
        if query_embeddings is not None:
            query_kwargs["query_embeddings"] = query_embeddings
        if where is not None:
            query_kwargs["where"] = where
        if where_document is not None:
            query_kwargs["where_document"] = where_document

        return self.collection.query(**query_kwargs)

    def get(
        self,
        ids: Optional[Union[str, List[str]]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get documents from collection by ID or filter.

        Args:
            ids: Document ID(s) to retrieve
            where: Metadata filter conditions
            where_document: Document content filter conditions
            limit: Maximum number of results
            offset: Number of results to skip
            include: Fields to include (embeddings, metadatas, documents)

        Returns:
            Dictionary with keys: ids, embeddings, metadatas, documents
        """
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        # Normalize IDs
        if ids is not None and isinstance(ids, str):
            ids = [ids]

        # Default include fields
        if include is None:
            include = ["metadatas", "documents"]

        get_kwargs = {"include": include}

        if ids is not None:
            get_kwargs["ids"] = ids
        if where is not None:
            get_kwargs["where"] = where
        if where_document is not None:
            get_kwargs["where_document"] = where_document
        if limit is not None:
            get_kwargs["limit"] = limit
        if offset is not None:
            get_kwargs["offset"] = offset

        return self.collection.get(**get_kwargs)

    def update(
        self,
        ids: Union[str, List[str]],
        embeddings: Optional[Union[List[float], List[List[float]]]] = None,
        metadatas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        documents: Optional[Union[str, List[str]]] = None
    ) -> None:
        """Update documents in collection.

        Args:
            ids: Document ID(s) to update
            embeddings: New embeddings
            metadatas: New metadata
            documents: New document content
        """
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        # Normalize inputs
        if isinstance(ids, str):
            ids = [ids]

        if embeddings is not None and isinstance(embeddings[0], (int, float)):
            embeddings = [embeddings]

        if metadatas is not None and not isinstance(metadatas, list):
            metadatas = [metadatas]

        if documents is not None and isinstance(documents, str):
            documents = [documents]

        update_kwargs = {"ids": ids}

        if embeddings is not None:
            update_kwargs["embeddings"] = embeddings
        if metadatas is not None:
            update_kwargs["metadatas"] = metadatas
        if documents is not None:
            update_kwargs["documents"] = documents

        self.collection.update(**update_kwargs)

    def delete(
        self,
        ids: Optional[Union[str, List[str]]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> None:
        """Delete documents from collection.

        Args:
            ids: Document ID(s) to delete
            where: Metadata filter conditions
            where_document: Document content filter conditions
        """
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        if ids is None and where is None and where_document is None:
            raise ValueError("Must provide at least one of: ids, where, where_document")

        # Normalize IDs
        if ids is not None and isinstance(ids, str):
            ids = [ids]

        delete_kwargs = {}

        if ids is not None:
            delete_kwargs["ids"] = ids
        if where is not None:
            delete_kwargs["where"] = where
        if where_document is not None:
            delete_kwargs["where_document"] = where_document

        self.collection.delete(**delete_kwargs)

    def count(self) -> int:
        """Get total number of documents in collection.

        Returns:
            Number of documents
        """
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        return self.collection.count()

    def peek(self, limit: int = 10) -> Dict[str, Any]:
        """Peek at first N documents in collection.

        Args:
            limit: Number of documents to return

        Returns:
            Dictionary with keys: ids, embeddings, metadatas, documents
        """
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        return self.collection.peek(limit=limit)

    def reset_collection(self) -> None:
        """Delete all documents from collection."""
        if not self.collection:
            raise RuntimeError("EmbeddingStore not initialized. Call initialize() first.")

        # Delete the collection and recreate it
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Document embeddings for local assistant"}
        )
