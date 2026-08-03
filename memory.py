import os
import uuid
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct
)

# QDRANT_HOST/QDRANT_PORT are read only when using remote Qdrant.
# The current code uses local Qdrant (path="qdrant_data"), so these are
# intentionally imported here in case they're needed later.
COLLECTION_NAME = "neo_dialogs"
VECTOR_SIZE = 384  # BAAI/bge-small-en via fastembed

_client = None
_embed_model = None  # singleton — loaded once, reused every call


def _get_client() -> QdrantClient | None:
    global _client, _collection_ready
    if _client is None:
        try:
            _client = QdrantClient(
                path="qdrant_data",
            )
            _ensure_collection()
            _collection_ready = True
            print(f"[Memory] Connected to local Qdrant at qdrant_data")
        except Exception as e:
            print(f"[Memory] Failed to connect to Qdrant: {e}")
            _client = None
    return _client


def _ensure_collection():
    existing = [c.name for c in _client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[Memory] Created Qdrant collection '{COLLECTION_NAME}'")


def _get_embed_model():
    """Singleton fastembed model — loaded once, zero-cost local embeddings."""
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbedding
        _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        print("[Memory] fastembed model loaded.")
    return _embed_model


def _embed(text: str) -> list[float]:
    model = _get_embed_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()


def store_turn(user_msg: str, neo_response: str, metadata: dict | None = None):
    """Store a conversation turn as a vector in Qdrant."""
    client = _get_client()
    if client is None:
        return

    try:
        combined_text = f"User: {user_msg}\nNeo: {neo_response}"
        vector = _embed(combined_text)

        payload = {
            "user": user_msg[:1000],
            "neo": neo_response[:1000],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            payload.update(metadata)

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            )],
        )
        print("[Memory] Stored turn in Qdrant.")
    except Exception as e:
        print(f"[Memory] Error storing turn: {e}")


def retrieve_relevant_turns(query: str, top_k: int = 3, max_chars_each: int = 400) -> str:
    """Retrieve the most semantically relevant past turns for the given query."""
    client = _get_client()
    if client is None:
        return ""

    try:
        vector = _embed(query)

        # query_points is the current API in qdrant-client >= 1.13
        result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=top_k,
            score_threshold=0.5,
            with_payload=True,
        )
        results = result.points

        if not results:
            return ""

        turns = []
        for hit in results:
            user_text = hit.payload.get("user", "")[:max_chars_each]
            neo_text = hit.payload.get("neo", "")[:max_chars_each]
            turns.append(f"User: {user_text}\nNeo: {neo_text}")

        context = "\n---\n".join(turns)
        return f"\n\n[CONTEXTO RELEVANTE DE CONVERSAS PASSADAS]:\n{context}\n"
    except Exception as e:
        print(f"[Memory] Error retrieving turns: {e}")
        return ""


# ── Backward-compat aliases used in agent.py ──────────────────────────────────
def store_memory(user_input: str, assistant_response: str):
    store_turn(user_input, assistant_response)


def retrieve_context(query: str, n_results: int = 3) -> str:
    return retrieve_relevant_turns(query, top_k=min(n_results, 1))
