# FILE: backend/src/agents/refinement_engine/embedding_models.py
import os
import httpx
import logging
from typing import List, Any, Dict
from llama_index.core.base.embeddings.base import BaseEmbedding
from src.core.config import settings

logger = logging.getLogger(__name__)

class PineconeEmbeddingModel(BaseEmbedding):
    """
    A custom embedding model that uses Pinecone's hosted embedding API.
    """
    class Config:
        extra = "allow"

    def __init__(self, model_name: str = "multilingual-e5-large", **kwargs):
        super().__init__(model_name=model_name, **kwargs)
        
        self._api_key: str = settings.PINECONE_API_KEY
        self._api_url: str = "https://api.pinecone.io/embed"
        
        if not self._api_key:
            raise ValueError("PINECONE_API_KEY environment variable not set.")
        
        logger.info(f"Pinecone Embedding Model initialized for endpoint: {self._api_url}")

    def _get_headers(self) -> dict:
        """Constructs the required headers for the Pinecone API."""
        return {
            "Api-Key": self._api_key,
            "Content-Type": "application/json",
            "X-Pinecone-API-Version": "2025-04"
        }
        
    # --- THIS IS THE FIX ---
    def _get_payload(self, texts: List[str]) -> Dict[str, Any]:
        """Constructs the full payload for the Pinecone API."""
        payload = {
            "model": self.model_name,
            "inputs": [{"text": t} for t in texts],
        }
        # Add model-specific parameters if needed.
        if self.model_name == "multilingual-e5-large":
            payload["parameters"] = {"input_type": "passage"}
        
        return payload
    # --- END OF FIX ---

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_text_embedding(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        embeddings = await self._aget_text_embeddings([query])
        return embeddings[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embeddings([text])[0]

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        logger.info(f"Requesting async embeddings for {len(texts)} texts from Pinecone model '{self.model_name}'...")
        headers = self._get_headers()
        payload = self._get_payload(texts)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self._api_url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                response_data = response.json()
                embeddings = [item['values'] for item in response_data['data']]
                logger.info(f"Successfully received {len(embeddings)} async embeddings from Pinecone.")
                return embeddings
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error calling Pinecone API asynchronously: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred calling Pinecone API asynchronously: {e}")
                raise

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        logger.info(f"Requesting sync embeddings for {len(texts)} texts from Pinecone model '{self.model_name}'...")
        headers = self._get_headers()
        payload = self._get_payload(texts)

        with httpx.Client() as client:
            try:
                response = client.post(self._api_url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                response_data = response.json()
                embeddings = [item['values'] for item in response_data['data']]
                logger.info(f"Successfully received {len(embeddings)} sync embeddings from Pinecone.")
                return embeddings
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error calling Pinecone API synchronously: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred calling Pinecone API synchronously: {e}")
                raise