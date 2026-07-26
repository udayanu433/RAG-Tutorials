import os
import shutil
import tempfile
from datetime import datetime
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from backend.app.database import get_db_connection, init_db
from backend.app.auth import get_current_role, require_role, MOCK_CREDENTIALS, ROLE_TO_TOKEN
from backend.app.rag import rag_pipeline
from backend.app.pdf_parser import parse_pdf_structured_pages
from typing import Dict, Any
from typing import Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Initialize FastAPI App
app = FastAPI(
    title="Academic Intelligent Hub API",
    description="Secure On-Premise RAG System and Centralized Notification Platform for KTU",
    version="1.0.0"
)

# Enable CORS for React Frontend (running on port 3000 by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ingestion text splitter config
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", " ", ""]
)

# Startup Handler
@app.on_event("startup")
def startup_event():
    init_db()

# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    role: str
    username: str

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    response: str
    role_used: str

class NotificationCreate(BaseModel):
    title: str
    content: str
    role_access: str # 'Student', 'Faculty', or 'All'

class NotificationResponse(BaseModel):
    id: int
    title: str
    content: str
    role_access: str
    created_at: str

class DocumentUpdate(BaseModel):
    title: str
    role_access: str
    doc_type: str
    topic: str

class DocumentDelete(BaseModel):
    title: str

# --- Endpoints ---

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "time": datetime.now().isoformat()}

@app.get("/api/notifications", response_model=List[NotificationResponse])
def get_notifications(role: str = Depends(get_current_role)):
    """
    Retrieves all announcements that the current user's role has permission to see.
    Students see 'Student' and 'All' access notifications.
    Faculty members see 'Faculty', 'Student', and 'All' access notifications.
    """
    allowed_access = ["All", "Student"] if role == "Student" else ["All", "Student", "Faculty"]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Generate query placeholders
    placeholders = ",".join(["?"] * len(allowed_access))
    query = f"SELECT * FROM notifications WHERE role_access IN ({placeholders}) ORDER BY id DESC"
    
    cursor.execute(query, allowed_access)
    rows = cursor.fetchall()
    
    notifications = []
    for row in rows:
        notifications.append(NotificationResponse(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            role_access=row["role_access"],
            created_at=row["created_at"]
        ))
        
    conn.close()
    return notifications

@app.post("/api/query", response_model=QueryResponse)
def query_rag(request: QueryRequest, role: str = Depends(get_current_role)):
    """
    RAG endpoint that queries the FAISS vector database.
    Documents are filtered based on the user's role before feeding to the LLM.
    """
    query_text = request.query
    print(f"[INFO] Received query: '{query_text}' from role: '{role}'")
    
    try:
        response_text = rag_pipeline.query(query_text, user_role=role)
        return QueryResponse(
            query=query_text,
            response=response_text,
            role_used=role
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG query execution failed: {str(e)}"
        )

@app.post("/api/admin/upload")
def upload_document(
    file: UploadFile = File(...),
    role_access: str = Form("All"), # 'Student', 'Faculty', or 'All'
    doc_type: str = Form("Curriculum"), # 'Curriculum', 'Activity Points', 'Guides'
    topic: str = Form("General"),
    admin_role: str = Depends(require_role(["Admin"]))
):
    """
    Upload and index PDF files. Only accessible by Admin.
    Converts tables to Markdown using pdfplumber to maintain structure.
    Saves the file permanently and rebuilds the Gemini context cache if enabled.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF file uploads are supported.")
        
    if role_access not in ["Student", "Faculty", "All"]:
        raise HTTPException(status_code=400, detail="role_access must be 'Student', 'Faculty', or 'All'")
        
    # Save the file permanently
    uploaded_docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploaded_docs")
    os.makedirs(uploaded_docs_dir, exist_ok=True)
    permanent_file_path = os.path.join(uploaded_docs_dir, file.filename)
    
    try:
        with open(permanent_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"[INFO] Uploaded file saved permanently to: {permanent_file_path}")
        
        # 1. Update SQLite Document Registry
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO documents (title, file_path, role_access, doc_type, topic, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file.filename, permanent_file_path, role_access, doc_type, topic, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        # 2. Rebuild Gemini context cache in the background (if Gemini is configured)
        if rag_pipeline.gemini_enabled:
            try:
                rag_pipeline.rebuild_gemini_caches()
            except Exception as e:
                print(f"[WARNING] Failed to rebuild Gemini caches during upload: {e}")
                
        # 3. Parse structured pages and chunk locally (with page numbers in metadata) for FAISS fallback
        pages = parse_pdf_structured_pages(permanent_file_path)
        
        all_chunks = []
        all_metadatas = []
        
        for p in pages:
            page_num = p["page_number"]
            page_text = p["content"]
            
            # Split page text into chunks
            chunks = text_splitter.split_text(page_text)
            
            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadatas.append({
                    "text": chunk,
                    "title": file.filename,
                    "page_number": page_num,
                    "role_access": role_access,
                    "doc_type": doc_type,
                    "topic": topic,
                    "uploaded_at": datetime.now().isoformat()
                })
        
        print(f"[INFO] Document parsed locally and split into {len(all_chunks)} chunks.")
        rag_pipeline.add_documents(all_chunks, all_metadatas)
        
        return {
            "message": "Document uploaded and indexed successfully.",
            "filename": file.filename,
            "chunks_created": len(all_chunks),
            "role_access": role_access
        }
        
    except Exception as e:
        print(f"[ERROR] Failed during upload/index process: {e}")
        # Clean up local file on failure
        if os.path.exists(permanent_file_path):
            os.remove(permanent_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to process and index PDF: {str(e)}")

@app.post("/api/admin/notify", response_model=NotificationResponse)
def create_notification(
    notification: NotificationCreate,
    admin_role: str = Depends(require_role(["Admin"]))
):
    """
    Pushes an official announcement. Inserts it into the SQLite table for the news feed,
    and vectorizes it into FAISS so the RAG bot is aware of it in real-time.
    """
    if notification.role_access not in ["Student", "Faculty", "All"]:
        raise HTTPException(status_code=400, detail="role_access must be 'Student', 'Faculty', or 'All'")
        
    now = datetime.now().isoformat()
    
    # 1. Route to Relational DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notifications (title, content, role_access, created_at) VALUES (?, ?, ?, ?)",
        (notification.title, notification.content, notification.role_access, now)
    )
    conn.commit()
    notification_id = cursor.lastrowid
    conn.close()
    
    # 2. Route to FAISS Vector DB
    notification_text = f"Notification Announcement: {notification.title}\nContent: {notification.content}\nDate Posted: {now}"
    
    metadata = {
        "text": notification_text,
        "title": f"Notification: {notification.title}",
        "role_access": notification.role_access,
        "doc_type": "Notification",
        "topic": "Announcements",
        "uploaded_at": now
    }
    
    try:
        rag_pipeline.add_documents([notification_text], [metadata])
        print(f"[INFO] Vectorized notification: '{notification.title}' into FAISS.")
    except Exception as e:
        print(f"[WARNING] Failed to vectorize notification: {e}")
        # We don't fail the request since database insertion worked.
        
    return NotificationResponse(
        id=notification_id,
        title=notification.title,
        content=notification.content,
        role_access=notification.role_access,
        created_at=now
    )

@app.post("/api/login", response_model=LoginResponse)
def login(request: LoginRequest):
    username = request.username.strip().lower()
    password = request.password.strip()
    
    if username not in MOCK_CREDENTIALS or MOCK_CREDENTIALS[username]["password"] != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )
        
    role = MOCK_CREDENTIALS[username]["role"]
    token = ROLE_TO_TOKEN[role]
    
    return LoginResponse(
        token=token,
        role=role,
        username=username
    )

@app.get("/api/admin/documents")
def get_documents(admin_role: str = Depends(require_role(["Admin"]))):
    """
    Returns a deduplicated list of all indexed documents in the FAISS index.
    Only accessible by Admin.
    """
    try:
        return rag_pipeline.get_all_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/update_document")
def update_document(
    doc: DocumentUpdate,
    admin_role: str = Depends(require_role(["Admin"]))
):
    """
    Updates the clearance level and tagging metadata for all chunks of an indexed document.
    Only accessible by Admin.
    """
    if doc.role_access not in ["Student", "Faculty", "All"]:
        raise HTTPException(status_code=400, detail="role_access must be 'Student', 'Faculty', or 'All'")
        
    try:
        # 1. Update FAISS fallback
        updated = rag_pipeline.update_document_metadata(
            title=doc.title,
            role_access=doc.role_access,
            doc_type=doc.doc_type,
            topic=doc.topic
        )
        
        # 2. Update SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE documents
            SET role_access = ?, doc_type = ?, topic = ?
            WHERE title = ?
            """,
            (doc.role_access, doc.doc_type, doc.topic, doc.title)
        )
        conn.commit()
        conn.close()
        
        # 3. Rebuild Gemini cache
        if rag_pipeline.gemini_enabled:
            try:
                rag_pipeline.rebuild_gemini_caches()
            except Exception as e:
                print(f"[WARNING] Failed to rebuild Gemini caches during document update: {e}")
                
        return {"message": "Document updated successfully.", "updated_chunks": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/delete_document")
def delete_document(
    doc: DocumentDelete,
    admin_role: str = Depends(require_role(["Admin"]))
):
    """
    Deletes an indexed document from SQLite, local storage, and the FAISS vector store.
    Only accessible by Admin.
    """
    try:
        # 1. Retrieve the local file path from DB first
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM documents WHERE title = ?", (doc.title,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Document '{doc.title}' not found in registry.")
            
        file_path = row["file_path"]
        
        # 2. Delete from DB
        cursor.execute("DELETE FROM documents WHERE title = ?", (doc.title,))
        conn.commit()
        conn.close()
        
        # 3. Delete the local PDF file
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[INFO] Deleted local PDF file: {file_path}")
            
        # 4. Delete from FAISS index
        rag_pipeline.delete_document(doc.title)
        
        # 5. Rebuild Gemini cache (if Gemini is configured)
        if rag_pipeline.gemini_enabled:
            try:
                rag_pipeline.rebuild_gemini_caches()
            except Exception as e:
                print(f"[WARNING] Failed to rebuild Gemini caches during document deletion: {e}")
                
        return {"message": "Document deleted successfully."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
