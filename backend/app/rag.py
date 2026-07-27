import os
import faiss
import numpy as np
import pickle
import sqlite3
import datetime
from datetime import datetime as dt
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

# Define Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "faiss.index")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "metadata.pkl")
DB_PATH = os.path.join(BASE_DIR, "academic_hub.db")

def is_ollama_running(url="http://localhost:11434"):
    try:
        import requests
        response = requests.get(f"{url}/api/tags", timeout=1)
        return response.status_code == 200
    except Exception:
        return False

class BackendRAG:
    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model_name
        print(f"[INFO] Initializing embedding model: {embedding_model_name}...")
        self.embed_model = SentenceTransformer(embedding_model_name)
        
        self.index = None
        self.metadata = []
        self.load_index()
        
        # Initialize LLM
        self.llm_type = None
        self.llm = None
        self.pipe = None
        self.init_llm()
        
        # Initialize Gemini Cloud Generator
        self.gemini_enabled = False
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_enabled = True
                print("[INFO] RAG pipeline: Gemini API Key detected. Hybrid Cloud Generation is enabled!")
            except Exception as e:
                print(f"[WARNING] Failed to initialize Gemini generator on startup: {e}")

    def init_llm(self):
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if groq_api_key:
            from langchain_groq import ChatGroq
            self.llm = ChatGroq(groq_api_key=groq_api_key, model_name="gemma2-9b-it")
            self.llm_type = "groq"
            print("[INFO] RAG pipeline: Using Groq LLM.")
        elif is_ollama_running():
            from langchain_community.chat_models import ChatOllama
            ollama_model = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.1")
            self.llm = ChatOllama(model=ollama_model, base_url="http://localhost:11434")
            self.llm_type = "ollama"
            print(f"[INFO] RAG pipeline: Using local Ollama with {ollama_model}.")
        else:
            print("[INFO] RAG pipeline: Neither Groq nor local Ollama detected. Offline Hugging Face LLM (Qwen/Qwen2.5-0.5B-Instruct) will load lazily on-demand if needed.")
            self.llm_type = "local_hf"

    def rebuild_gemini_caches(self):
        """
        No-op method kept for backwards compatibility with endpoints.
        No cloud caches are built, as we use a hybrid search strategy.
        """
        pass

    def load_index(self):
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(METADATA_PATH):
            try:
                self.index = faiss.read_index(FAISS_INDEX_PATH)
                with open(METADATA_PATH, "rb") as f:
                    self.metadata = pickle.load(f)
                print(f"[INFO] Loaded FAISS index with {len(self.metadata)} chunks.")
            except Exception as e:
                print(f"[ERROR] Failed to load FAISS index: {e}. Starting fresh.")
                self.index = None
                self.metadata = []
        else:
            print("[INFO] No existing FAISS index found. Starting fresh.")
            self.index = None
            self.metadata = []

    def save_index(self):
        if self.index is not None:
            faiss.write_index(self.index, FAISS_INDEX_PATH)
            with open(METADATA_PATH, "wb") as f:
                pickle.dump(self.metadata, f)
            print("[INFO] FAISS index and metadata saved successfully.")

    def add_documents(self, text_chunks: List[str], metadatas: List[Dict[str, Any]]):
        """
        Embeds and adds text chunks with metadata to the FAISS index (local vector store).
        """
        if not text_chunks:
            return
            
        embeddings = self.embed_model.encode(text_chunks).astype('float32')
        dim = embeddings.shape[1]
        
        if self.index is None:
            self.index = faiss.IndexFlatL2(dim)
            
        self.index.add(embeddings)
        self.metadata.extend(metadatas)
        self.save_index()
        print(f"[INFO] Successfully added {len(text_chunks)} chunks to FAISS store.")

    def query(self, query_text: str, user_role: str, top_k: int = 5) -> str:
        """
        Performs standard FAISS local chunk retrieval (role-filtered), formats context,
        and uses the Gemini API as generator (if enabled), falling back to local models.
        """
        # --- Local FAISS Retrieval (Role-Filtered Context) ---
        if self.index is None or not self.metadata:
            return "Knowledge base is currently empty. Please upload documents or add notifications first."
            
        query_emb = self.embed_model.encode([query_text]).astype('float32')
        candidate_count = min(top_k * 4, len(self.metadata))
        D, I = self.index.search(query_emb, candidate_count)
        
        allowed_access = ["All", "Student"] if user_role == "Student" else ["All", "Student", "Faculty"]
        
        filtered_context_chunks = []
        source_pages = {} # filename -> set of page numbers
        
        for idx, dist in zip(I[0], D[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            role_access = meta.get("role_access", "All")
            
            if role_access in allowed_access:
                filtered_context_chunks.append(meta.get("text", ""))
                title = meta.get("title", "Unknown Document")
                page_num = meta.get("page_number")
                
                if title not in source_pages:
                    source_pages[title] = set()
                if page_num is not None:
                    source_pages[title].add(page_num)
                    
                if len(filtered_context_chunks) >= top_k:
                    break
                    
        if not filtered_context_chunks:
            return "No relevant documents matching your permission level were found."
            
        # Format citations
        citation_list = []
        for title, pages in source_pages.items():
            if pages:
                sorted_pages = sorted(list(pages))
                pages_str = ", ".join([f"Page {p}" for p in sorted_pages])
                citation_list.append(f"[Source: {title} ({pages_str})]")
            else:
                citation_list.append(f"[Source: {title}]")
        sources_str = "\n".join(citation_list)
        
        context = "\n\n".join(filtered_context_chunks)
        prompt = f"""You are the KTU Academic Intelligent Hub assistant. Answer the user's question using ONLY the provided verified context.
If the answer cannot be found in the context, state that you do not have that information. Keep the response concise, accurate, and structured. Do not append manual source lists inside the answer.

User Role: {user_role}
User Query: {query_text}

Context:
{context}

Answer:"""
        
        # Call LLM Generator
        response_text = ""
        if self.gemini_enabled:
            import google.generativeai as genai
            print("[INFO] RAG pipeline: Querying Gemini API with local FAISS context chunks (Hybrid RAG)...")
            model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
            try:
                response = model.generate_content(
                    prompt,
                    request_options={"timeout": 30}
                )
                response_text = response.text
            except Exception as e:
                print(f"[WARNING] Gemini Cloud Query failed: {e}. Falling back to local offline model...")
                response_text = ""
                
        if not response_text:
            # Fallback to local models
            if self.llm_type in ["groq", "ollama"]:
                response = self.llm.invoke([prompt])
                response_text = response.content
            else:
                if self.pipe is None:
                    from transformers import pipeline
                    print("[INFO] RAG pipeline: Loading offline Hugging Face LLM (Qwen/Qwen2.5-0.5B-Instruct) on-demand...")
                    self.pipe = pipeline("text-generation", model="Qwen/Qwen2.5-0.5B-Instruct")
                messages = [
                    {"role": "user", "content": prompt}
                ]
                outputs = self.pipe(messages, max_new_tokens=256, temperature=0.3, do_sample=False)
                response_text = outputs[0]["generated_text"][-1]["content"]
            
        # Programmatically append sources at the bottom
        if sources_str:
            response_text += f"\n\n**Sources:**\n{sources_str}"
            
        return response_text

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Retrieves all uploaded documents directly from the SQLite registry.
        """
        if not os.path.exists(DB_PATH):
            return []
            
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
            if not cursor.fetchone():
                conn.close()
                return []
                
            cursor.execute("SELECT title, role_access, doc_type, topic, uploaded_at FROM documents ORDER BY uploaded_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[ERROR] Failed to query documents from database: {e}")
            return []

    def update_document_metadata(self, title: str, role_access: str, doc_type: str, topic: str) -> int:
        """
        Updates metadata tags for all chunks of a document in local FAISS cache.
        """
        updated_count = 0
        for meta in self.metadata:
            if meta.get("title") == title:
                meta["role_access"] = role_access
                meta["doc_type"] = doc_type
                meta["topic"] = topic
                updated_count += 1
        if updated_count > 0:
            self.save_index()
            print(f"[INFO] Updated tags for {updated_count} chunks of document: '{title}'")
        return updated_count

    def delete_document(self, title: str) -> bool:
        """
        Deletes metadata chunks from the registry and completely rebuilds the FAISS index
        excluding the deleted document chunks.
        """
        remaining_metadata = [meta for meta in self.metadata if meta.get("title") != title]
        deleted_count = len(self.metadata) - len(remaining_metadata)
        
        if deleted_count == 0:
            print(f"[WARNING] Document '{title}' was not found in FAISS metadata index.")
            return False
            
        self.metadata = remaining_metadata
        
        # Rebuild FAISS index
        if not self.metadata:
            self.index = None
            print("[INFO] FAISS index is now empty.")
        else:
            remaining_texts = [meta["text"] for meta in self.metadata]
            embeddings = self.embed_model.encode(remaining_texts).astype('float32')
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(embeddings)
            print(f"[INFO] FAISS index rebuilt with remaining {len(self.metadata)} chunks.")
            
        self.save_index()
        return True

# Global RAG Instance
rag_pipeline = BackendRAG()
