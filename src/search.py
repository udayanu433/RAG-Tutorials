import os
from dotenv import load_dotenv
from src.vectorstore import FaissVectorStore
from langchain_groq import ChatGroq

load_dotenv()

def is_ollama_running(url="http://localhost:11434"):
    try:
        import requests
        response = requests.get(f"{url}/api/tags", timeout=1)
        return response.status_code == 200
    except Exception:
        return False

class RAGSearch:
    def __init__(self, persist_dir: str = "faiss_store", embedding_model: str = "all-MiniLM-L6-v2", llm_model: str = "gemma2-9b-it"):
        self.vectorstore = FaissVectorStore(persist_dir, embedding_model)
        # Load or build vectorstore
        faiss_path = os.path.join(persist_dir, "faiss.index")
        meta_path = os.path.join(persist_dir, "metadata.pkl")
        if not (os.path.exists(faiss_path) and os.path.exists(meta_path)):
            from src.data_loader import load_all_documents
            docs = load_all_documents("data")
            self.vectorstore.build_from_documents(docs)
        else:
            self.vectorstore.load()
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if groq_api_key:
            from langchain_groq import ChatGroq
            self.llm = ChatGroq(groq_api_key=groq_api_key, model_name=llm_model)
            self.llm_type = "groq"
            print(f"[INFO] Groq LLM initialized: {llm_model}")
        elif is_ollama_running():
            from langchain_community.chat_models import ChatOllama
            ollama_model = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.1")
            self.llm = ChatOllama(model=ollama_model, base_url="http://localhost:11434")
            self.llm_type = "ollama"
            print(f"[INFO] Ollama LLM initialized: {ollama_model}")
        else:
            from transformers import pipeline
            print("[INFO] Neither Groq nor local Ollama detected. Initializing local Hugging Face LLM (Qwen/Qwen2.5-0.5B-Instruct)...")
            self.pipe = pipeline("text-generation", model="Qwen/Qwen2.5-0.5B-Instruct", device_map="auto")
            self.llm_type = "local_hf"
            print("[INFO] Local Hugging Face LLM initialized successfully.")

    def search_and_summarize(self, query: str, top_k: int = 5) -> str:
        results = self.vectorstore.query(query, top_k=top_k)
        texts = [r["metadata"].get("text", "") for r in results if r["metadata"]]
        context = "\n\n".join(texts)
        if not context:
            return "No relevant documents found."
        prompt = f"""Summarize the following context for the query: '{query}'\n\nContext:\n{context}\n\nSummary:"""
        if self.llm_type in ["groq", "ollama"]:
            response = self.llm.invoke([prompt])
            return response.content
        else:
            messages = [
                {"role": "user", "content": prompt}
            ]
            outputs = self.pipe(messages, max_new_tokens=256, temperature=0.7, do_sample=True)
            return outputs[0]["generated_text"][-1]["content"]

# Example usage
if __name__ == "__main__":
    rag_search = RAGSearch()
    query = "What is attention mechanism?"
    summary = rag_search.search_and_summarize(query, top_k=3)
    print("Summary:", summary)
