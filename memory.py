import os
import chromadb

# Conecta ao ChromaDB no Docker (ou local se não houver host definido)
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")

try:
    client = chromadb.HttpClient(host=CHROMA_HOST, port=8000)
    collection = client.get_or_create_collection(name="neo_memory")
except Exception as e:
    print(f"[Memory] Failed to connect to ChromaDB at {CHROMA_HOST}: {e}")
    collection = None

def store_memory(user_input: str, assistant_response: str):
    if not collection: return
    
    doc_id = str(hash(user_input + assistant_response))
    document = f"User: {user_input}\nNeo: {assistant_response}"
    
    try:
        collection.add(
            documents=[document],
            metadatas=[{"role": "conversation"}],
            ids=[doc_id]
        )
        print(f"[Memory] Stored interaction in long-term memory.")
    except Exception as e:
        print(f"[Memory] Error storing memory: {e}")

def retrieve_context(query: str, n_results: int = 3) -> str:
    if not collection: return ""
    
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if results and results['documents'] and results['documents'][0]:
            context_str = "\n---\n".join(results['documents'][0])
            return f"\n\n[MEMÓRIA DE LONGO PRAZO DO NEO - CONTEXTO RELEVANTE DA CONVERSA PASSADA]:\n{context_str}\n"
    except Exception as e:
        print(f"[Memory] Error retrieving context: {e}")
    
    return ""
