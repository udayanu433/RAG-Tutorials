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
        
        # Initialize Gemini Cloud Caching
        self.gemini_enabled = False
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.active_caches = {}
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_enabled = True
                print("[INFO] RAG pipeline: Gemini API Key detected. Cloud Context Caching is enabled!")
                self.rebuild_gemini_caches()
            except Exception as e:
                print(f"[WARNING] Failed to initialize Gemini client or caches on startup: {e}")

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
            from transformers import pipeline
            print("[INFO] RAG pipeline: Neither Groq nor local Ollama detected. Loading offline Hugging Face LLM (Qwen/Qwen2.5-0.5B-Instruct)...")
            self.pipe = pipeline("text-generation", model="Qwen/Qwen2.5-0.5B-Instruct")
            self.llm_type = "local_hf"
            print("[INFO] RAG pipeline: Offline Hugging Face LLM loaded.")

    def rebuild_gemini_caches(self):
        """
        Gathers uploaded files from SQLite DB, maps them to Student/Admin roles,
        verifies/uploads them to Gemini Files API, and creates/replaces Gemini Context Caches.
        """
        if not self.gemini_enabled:
            return
            
        import google.generativeai as genai
        from google.generativeai import caching
        import datetime
        
        print("[INFO] Rebuilding Gemini cloud context caches...")
        
        if not os.path.exists(DB_PATH):
            print("[INFO] SQLite database does not exist yet. Skipping cloud caching.")
            return
            
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        if not cursor.fetchone():
            conn.close()
            print("[INFO] SQLite documents table does not exist yet. Skipping cloud caching.")
            return
            
        cursor.execute("SELECT title, file_path, role_access FROM documents")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            print("[INFO] No documents in SQLite yet. Skipping cloud caching.")
            return

        student_docs = []
        admin_docs = []
        
        for row in rows:
            title = row["title"]
            file_path = row["file_path"]
            role_access = row["role_access"]
            
            if os.path.exists(file_path):
                if role_access in ["Student", "All"]:
                    student_docs.append((title, file_path))
                admin_docs.append((title, file_path))
            else:
                print(f"[WARNING] File not found locally for upload: {file_path}")

        # List currently active files in Gemini to avoid uploading duplicates
        try:
            gemini_files = {f.display_name: f for f in genai.list_files()}
        except Exception as e:
            print(f"[WARNING] Error listing Gemini files: {e}. Starting with empty file registry.")
            gemini_files = {}
            
        def get_or_upload_file(title: str, path: str):
            display_name = os.path.basename(path)
            if display_name in gemini_files:
                return gemini_files[display_name]
            print(f"[INFO] Uploading '{display_name}' to Gemini cloud storage...")
            g_file = genai.upload_file(path=path, display_name=display_name)
            return g_file

        def build_cache_for_role(role_name: str, doc_list: list):
            if not doc_list:
                return None
                
            g_files = []
            for title, path in doc_list:
                try:
                    g_file = get_or_upload_file(title, path)
                    g_files.append(g_file)
                except Exception as e:
                    print(f"[WARNING] Failed to upload {title} to Gemini: {e}")
                    
            if not g_files:
                return None
                
            cache_display_name = f"ktu_hub_{role_name.lower()}_cache"
            
            try:
                # Delete existing cache with same display name to avoid leaks
                for c in caching.CachedContent.list():
                    if c.display_name == cache_display_name:
                        print(f"[INFO] Cleaning up stale cache: {c.name}")
                        c.delete()
            except Exception as e:
                print(f"[WARNING] Error cleaning old Gemini caches: {e}")
                
            try:
                print(f"[INFO] Creating fresh CachedContent '{cache_display_name}' with {len(g_files)} files...")
                cache = caching.CachedContent.create(
                    model="models/gemini-1.5-flash-001",
                    display_name=cache_display_name,
                    contents=g_files,
                    ttl=datetime.timedelta(hours=5),
                )
                return cache
            except Exception as e:
                print(f"[ERROR] Failed to create CachedContent: {e}")
                return None

        # Build caches
        self.active_caches["Student"] = build_cache_for_role("Student", student_docs)
        self.active_caches["Admin"] = build_cache_for_role("Admin", admin_docs)
        print("[INFO] Rebuilding Gemini caches complete.")

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
        Embeds and adds text chunks with metadata to the FAISS index (fallback vector store).
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
        If Gemini is enabled, queries the Gemini model directly using Cloud Context Caching.
        Otherwise, performs standard FAISS local chunk retrieval and falls back to Ollama or local LLM.
        """
        if self.gemini_enabled:
            import google.generativeai as genai
            
            # Map role to active cache:
            # Student: uses student cache
            # Faculty/Admin: uses admin cache
            cache_role = "Student" if user_role == "Student" else "Admin"
            cache = self.active_caches.get(cache_role)
            
            if cache:
                print(f"[INFO] RAG pipeline: Querying Gemini API with Cloud Cache ({cache.display_name})...")
                model = genai.GenerativeModel(model_name="models/gemini-1.5-flash-001")
                prompt = f"""You are the KTU Academic Intelligent Hub assistant. Answer the user's question using ONLY the provided cached context.
At the end of your response, ALWAYS append a section called "Sources:" listing the exact document name(s) and page number(s) (e.g. "[Source: ktu_activity_points.pdf (Page 3)]") you used to answer the question.
If the answer cannot be found in the context, state that you do not have that information. Keep the response concise, accurate, and structured.

User Role: {user_role}
User Query: {query_text}

Answer:"""
                try:
                    response = model.generate_content(
                        prompt,
                        request_options={"timeout": 60}
                    )
                    return response.text
                except Exception as e:
                    print(f"[WARNING] Gemini Cached Query failed: {e}. Falling back to local FAISS search...")
            else:
                print("[INFO] RAG pipeline: No active Gemini cache found. Falling back to local FAISS search...")

        # --- Local FAISS Fallback ---
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
        if self.llm_type in ["groq", "ollama"]:
            response = self.llm.invoke([prompt])
            response_text = response.content
        else:
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
