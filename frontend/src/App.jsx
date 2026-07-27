import React, { useState, useEffect, useRef } from "react";
import "./App.css";

const BACKEND_URL = "http://localhost:8000";

function App() {
  // --- Authentication States ---
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [role, setRole] = useState(localStorage.getItem("role") || "");
  const [username, setUsername] = useState(localStorage.getItem("username") || "");
  
  // Login Form States
  const [loginUser, setLoginUser] = useState("");
  const [loginPass, setLoginPass] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  // --- Dashboard States ---
  const [notifications, setNotifications] = useState([]);
  
  // Chatbot States
  const [messages, setMessages] = useState([
    {
      sender: "bot",
      text: "Welcome to the KTU Academic Intelligent Hub! Ask me about syllabus rules, industrial visits, or activity points.",
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Admin Ingestion States
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadRoleAccess, setUploadRoleAccess] = useState("All");
  const [uploadDocType, setUploadDocType] = useState("Curriculum");
  const [uploadTopic, setUploadTopic] = useState("General");
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadAlert, setUploadAlert] = useState(null);
  const fileInputRef = useRef(null);

  // Admin Notification States
  const [announceTitle, setAnnounceTitle] = useState("");
  const [announceContent, setAnnounceContent] = useState("");
  const [announceRoleAccess, setAnnounceRoleAccess] = useState("All");
  const [announceLoading, setAnnounceLoading] = useState(false);
  const [announceAlert, setAnnounceAlert] = useState(null);

  // Admin Document Management States (Update clearances)
  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [editingDoc, setEditingDoc] = useState(null); // { title: str, role_access: str, doc_type: str, topic: str }
  const [editLoading, setEditLoading] = useState(false);
  const [editAlert, setEditAlert] = useState(null);

  // --- Effects ---
  useEffect(() => {
    if (token) {
      fetchNotifications();
      if (role === "Admin") {
        fetchDocuments();
      }
    }
  }, [token, role]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, chatLoading]);

  // --- Helper Functions ---
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!loginUser.trim() || !loginPass.trim()) {
      setLoginError("Please enter both username and password.");
      return;
    }

    setLoginLoading(true);
    setLoginError("");

    try {
      const response = await fetch(`${BACKEND_URL}/api/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: loginUser.trim(),
          password: loginPass
        })
      });

      if (response.ok) {
        const data = await response.json();
        
        // Save to state & local storage
        setToken(data.token);
        setRole(data.role);
        setUsername(data.username);
        localStorage.setItem("token", data.token);
        localStorage.setItem("role", data.role);
        localStorage.setItem("username", data.username);
        
        // Reset login form
        setLoginUser("");
        setLoginPass("");
        
        // Push welcome chat
        setMessages([
          {
            sender: "bot",
            text: `Welcome back, ${data.username}! You are logged in as a ${data.role}. How can I assist you today?`,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      } else {
        const errData = await response.json();
        setLoginError(errData.detail || "Authentication failed. Check credentials.");
      }
    } catch (error) {
      setLoginError("Connection refused: Verify the FastAPI backend is running on port 8000.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    setToken("");
    setRole("");
    setUsername("");
    setNotifications([]);
    setDocuments([]);
    localStorage.clear();
  };

  const fetchNotifications = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/notifications`, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setNotifications(data);
      } else {
        console.error("Failed to load notifications.");
      }
    } catch (error) {
      console.error("Error connecting to notification endpoint:", error);
    }
  };

  const fetchDocuments = async () => {
    if (role !== "Admin") return;
    setDocsLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/documents`, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setDocuments(data);
      }
    } catch (error) {
      console.error("Error loading documents list:", error);
    } finally {
      setDocsLoading(false);
    }
  };

  const handleSendMessage = async (textToSend = null) => {
    const queryText = textToSend || chatInput;
    if (!queryText.trim()) return;

    const userMsg = {
      sender: "user",
      text: queryText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setChatInput("");
    setChatLoading(true);

    try {
      const response = await fetch(`${BACKEND_URL}/api/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ query: queryText })
      });

      if (response.ok) {
        const data = await response.json();
        const botMsg = {
          sender: "bot",
          text: data.response,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages((prev) => [...prev, botMsg]);
      } else {
        const errData = await response.json();
        setMessages((prev) => [
          ...prev,
          {
            sender: "bot",
            text: `Error: ${errData.detail || "RAG pipeline error."}`,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "bot",
          text: "Error: Failed to reach the RAG backend server.",
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUploadFileSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadAlert({ type: "error", text: "Please select a PDF document to upload." });
      return;
    }

    setUploadLoading(true);
    setUploadAlert(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("role_access", uploadRoleAccess);
    formData.append("doc_type", uploadDocType);
    formData.append("topic", uploadTopic);

    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/upload`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setUploadAlert({
          type: "success",
          text: `Success: Indexed "${data.filename}" (${data.chunks_created} chunks).`
        });
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        
        // Refresh documents view
        fetchDocuments();
      } else {
        const errData = await response.json();
        setUploadAlert({ type: "error", text: `Upload failed: ${errData.detail || "Error"}` });
      }
    } catch (error) {
      setUploadAlert({ type: "error", text: "Network error: Upload failed." });
    } finally {
      setUploadLoading(false);
    }
  };

  const handlePublishAnnouncement = async (e) => {
    e.preventDefault();
    if (!announceTitle.trim() || !announceContent.trim()) {
      setAnnounceAlert({ type: "error", text: "Please fill out all announcement fields." });
      return;
    }

    setAnnounceLoading(true);
    setAnnounceAlert(null);

    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/notify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          title: announceTitle,
          content: announceContent,
          role_access: announceRoleAccess
        })
      });

      if (response.ok) {
        const data = await response.json();
        setAnnounceAlert({ type: "success", text: `Published announcement: "${data.title}"` });
        setAnnounceTitle("");
        setAnnounceContent("");
        
        // Refresh feed & docs (as notification is vectorized)
        fetchNotifications();
        fetchDocuments();
      } else {
        const errData = await response.json();
        setAnnounceAlert({ type: "error", text: `Failed: ${errData.detail || "Error"}` });
      }
    } catch (error) {
      setAnnounceAlert({ type: "error", text: "Network error: Failed to publish." });
    } finally {
      setAnnounceLoading(false);
    }
  };

  const handleUpdateDocumentMetadata = async (e) => {
    e.preventDefault();
    if (!editingDoc) return;

    setEditLoading(true);
    setEditAlert(null);

    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/update_document`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(editingDoc)
      });

      if (response.ok) {
        setEditAlert({ type: "success", text: `Document tags updated successfully.` });
        setEditingDoc(null);
        fetchDocuments();
      } else {
        const errData = await response.json();
        setEditAlert({ type: "error", text: `Update failed: ${errData.detail || "Error"}` });
      }
    } catch (error) {
      setEditAlert({ type: "error", text: "Network error: Failed to update document tags." });
    } finally {
      setEditLoading(false);
    }
  };

  const handleDeleteDocument = async (title) => {
    if (!window.confirm(`Are you sure you want to completely delete "${title}"? This will remove it from the database, local storage, and the RAG index.`)) {
      return;
    }

    setDocsLoading(true);
    setEditAlert(null);

    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/delete_document`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ title })
      });

      if (response.ok) {
        setEditAlert({ type: "success", text: `Document "${title}" deleted successfully.` });
        fetchDocuments();
      } else {
        const errData = await response.json();
        setEditAlert({ type: "error", text: `Delete failed: ${errData.detail || "Error"}` });
      }
    } catch (error) {
      setEditAlert({ type: "error", text: "Network error: Failed to delete document." });
    } finally {
      setDocsLoading(false);
    }
  };

  const parseBoldAndItalic = (text) => {
    if (!text) return "";
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, idx) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={idx}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return <code key={idx}>{part.slice(1, -1)}</code>;
      }
      return part;
    });
  };

  const renderMessageText = (text) => {
    if (!text) return "";
    const paragraphs = text.split("\n\n");
    return paragraphs.map((para, pIdx) => {
      if (para.startsWith("**Sources:**") || para.startsWith("Sources:")) {
        const lines = para.split("\n");
        return (
          <div key={pIdx} className="citations-block">
            <h4 style={{fontSize: "11px", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: "6px", fontWeight: "600"}}>Sources:</h4>
            <div style={{display: "flex", flexWrap: "wrap", gap: "6px"}}>
              {lines.filter(l => l.trim() && !l.includes("Sources:")).map((line, lIdx) => {
                const cleanLine = line.replace(/^\s*[-\*+]\s*/, "").replace(/[\[\]]/g, "");
                return (
                  <div key={lIdx} className="citation-badge">
                    📄 {cleanLine}
                  </div>
                );
              })}
            </div>
          </div>
        );
      }
      
      if (para.includes("\n- ") || para.includes("\n* ") || para.startsWith("- ") || para.startsWith("* ")) {
        const lines = para.split("\n");
        return (
          <ul key={pIdx}>
            {lines.map((line, lIdx) => {
              const cleanLine = line.replace(/^\s*[-\*+]\s*/, "");
              if (!cleanLine.trim()) return null;
              return <li key={lIdx}>{parseBoldAndItalic(cleanLine)}</li>;
            })}
          </ul>
        );
      }

      return <p key={pIdx}>{parseBoldAndItalic(para)}</p>;
    });
  };

  // Chat Prompt Suggestions
  const suggestions = [
    "What is the semester registration deadline?",
    "Tell me about curriculum revisions",
    "What are the rules for activity points?",
    "Faculty curriculum revision details"
  ];

  // --- Render Login Screen if not authenticated ---
  if (!token) {
    return (
      <div className="login-page-wrapper">
        <div className="login-card glass-panel pulse-glow-border">
          <div className="login-header">
            <div className="logo-icon" style={{width: "48px", height: "48px", fontSize: "24px"}}>K</div>
            <h1>Academic Intelligent Hub</h1>
            <p>On-Premise KTU Document RAG & Notifications</p>
          </div>

          <form onSubmit={handleLogin} className="login-form">
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                className="form-control"
                placeholder="Enter username"
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                disabled={loginLoading}
              />
            </div>
            
            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                className="form-control"
                placeholder="Enter password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                disabled={loginLoading}
              />
            </div>

            {loginError && (
              <div className="status-alert error">
                {loginError}
              </div>
            )}

            <button 
              type="submit" 
              className="btn-submit"
              style={{marginTop: "8px"}}
              disabled={loginLoading}
            >
              {loginLoading ? "Verifying Credentials..." : "Authenticate Session"}
            </button>
          </form>

          <div className="login-credentials-helper">
            <h4>Mock Accounts Available:</h4>
            <div className="credentials-list">
              <div>Student Clearance: <code>student</code> / <code>student123</code></div>
              <div>Faculty Clearance: <code>faculty</code> / <code>faculty123</code></div>
              <div>Admin Clearance: <code>admin</code> / <code>admin123</code></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // --- Render Dashboard Screen once authenticated ---
  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header glass-panel pulse-glow-border">
        <div className="brand-section">
          <div className="logo-icon">K</div>
          <div className="brand-details">
            <h1>Academic Intelligent Hub</h1>
            <p>KTU On-Premise Document RAG & Centralized Announcement System</p>
          </div>
        </div>
        
        <div className="user-control-panel">
          <div style={{textAlign: "right", marginRight: "4px"}}>
            <span style={{fontSize: "10px", color: "var(--text-muted)", display: "block"}}>Signed in as</span>
            <span style={{fontSize: "13px", fontWeight: "600", color: "var(--text-primary)"}}>{username}</span>
          </div>
          
          <div className={`role-badge ${role}`}>
            <span>{role === "Student" ? "👤" : role === "Faculty" ? "🎓" : "🛡️"}</span>
            <span>Role: {role}</span>
          </div>
          
          <button className="btn-logout" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      {/* Grid Dashboard */}
      <div className="dashboard-grid">
        
        {/* Left column: Notifications Feed */}
        <aside className="sidebar-panel glass-panel">
          <div className="sidebar-header">
            <h2>Announcements</h2>
            <span className="notification-count">{notifications.length} Active</span>
          </div>
          
          <div className="notifications-list scroll-container">
            {notifications.length === 0 ? (
              <div className="empty-feed">No announcements matching your role clearance.</div>
            ) : (
              notifications.map((notif) => (
                <div key={notif.id} className="notification-card">
                  <div className="notification-header">
                    <h3>{notif.title}</h3>
                    <span className={`audience-badge ${notif.role_access.toLowerCase()}`}>
                      {notif.role_access}
                    </span>
                  </div>
                  <p className="notification-content">{notif.content}</p>
                  <span className="notification-time">
                    {new Date(notif.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                </div>
              ))
            )}
          </div>
        </aside>

        {/* Right column: Chatbot & Admin operations */}
        <main className="workspace-panel">
          
          {/* RAG Chatbot */}
          <section className="chatbot-wrapper glass-panel">
            <div className="chatbot-header">
              <div className="chatbot-info">
                <div className="bot-avatar">AI</div>
                <div className="chatbot-title">
                  <h3>KTU Assistant</h3>
                  <p>Local On-Premise LLM</p>
                </div>
              </div>
              <div style={{fontSize: "12px", color: "var(--text-secondary)"}}>
                Clearance Clearances: <strong>{role === "Student" ? "Student & All Docs" : role === "Faculty" ? "Faculty & Student Docs" : "All System Docs"}</strong>
              </div>
            </div>

            {/* Message window */}
            <div className="chat-window scroll-container">
              {messages.map((msg, index) => (
                <div key={index} className={`chat-bubble-container ${msg.sender}`}>
                  <div className="chat-bubble">
                    {renderMessageText(msg.text)}
                  </div>
                  <span className="chat-metadata">{msg.time}</span>
                </div>
              ))}
              
              {chatLoading && (
                <div className="chat-bubble-container bot">
                  <div className="chat-bubble">
                    <div className="loading-bubble">
                      <div className="dot"></div>
                      <div className="dot"></div>
                      <div className="dot"></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input form */}
            <div className="chat-input-bar">
              <div className="chat-input-container">
                <textarea
                  className="chat-input"
                  rows="1"
                  placeholder="Ask about curriculum guidelines, activity points mandates..."
                  value={chatInput}
                  onChange={(e) => {
                    setChatInput(e.target.value);
                    e.target.style.height = "auto";
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={chatLoading}
                  style={{
                    resize: "none",
                    height: "auto",
                    maxHeight: "120px",
                    overflowY: "auto",
                    paddingTop: "12px",
                    paddingBottom: "12px",
                  }}
                />
                <button 
                  className="chat-send-btn" 
                  onClick={() => handleSendMessage()}
                  disabled={chatLoading || !chatInput.trim()}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M22 2L11 13M22 2L15 22L11 13M11 13L2 9L22 2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              </div>
            </div>
            
            <div style={{padding: "10px 20px", background: "rgba(0, 0, 0, 0.3)"}}>
              <div className="suggestions-row">
                {suggestions.map((sug, i) => (
                  <button 
                    key={i} 
                    className="suggestion-pill"
                    onClick={() => handleSendMessage(sug)}
                    disabled={chatLoading}
                  >
                    {sug}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* Admin Panels (Visible to Admin Only) */}
          {role === "Admin" && (
            <div className="admin-section">
              
              {/* Form 1: Upload Document */}
              <section className="admin-card glass-panel">
                <h2>Ingest Document (RAG)</h2>
                
                <form onSubmit={handleUploadFileSubmit} style={{display: "flex", flexDirection: "column", gap: "12px"}}>
                  <div className="form-group">
                    <label>PDF Document</label>
                    <div 
                      className="file-dropzone"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      {selectedFile ? (
                        <div className="selected-file-badge">
                          <span>📄 {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                          <button 
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedFile(null);
                            }}
                          >
                            ×
                          </button>
                        </div>
                      ) : (
                        <>
                          <p>Click to select PDF file</p>
                          <span>Syllabus, guidelines, rules, calendars</span>
                        </>
                      )}
                      <input 
                        type="file" 
                        ref={fileInputRef}
                        style={{display: "none"}} 
                        accept=".pdf"
                        onChange={handleFileChange}
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Clearance Level</label>
                      <select 
                        className="form-control"
                        value={uploadRoleAccess}
                        onChange={(e) => setUploadRoleAccess(e.target.value)}
                      >
                        <option value="All">All Students & Faculty</option>
                        <option value="Student">Students Only</option>
                        <option value="Faculty">Faculty Members Only</option>
                      </select>
                    </div>
                    
                    <div className="form-group">
                      <label>Document Type</label>
                      <select 
                        className="form-control"
                        value={uploadDocType}
                        onChange={(e) => setUploadDocType(e.target.value)}
                      >
                        <option value="Curriculum">Syllabus / Curriculum</option>
                        <option value="Activity Points">Activity Points</option>
                        <option value="Guidelines">University Guides</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>General Topic</label>
                    <input 
                      type="text" 
                      className="form-control" 
                      placeholder="e.g. Activity Points Guideline"
                      value={uploadTopic}
                      onChange={(e) => setUploadTopic(e.target.value)}
                    />
                  </div>

                  {uploadAlert && (
                    <div className={`status-alert ${uploadAlert.type}`}>
                      {uploadAlert.text}
                    </div>
                  )}

                  <button 
                    type="submit" 
                    className="btn-submit"
                    disabled={uploadLoading || !selectedFile}
                  >
                    {uploadLoading ? "Processing Ingestion..." : "⚡ Ingest & Index Document"}
                  </button>
                </form>
              </section>

              {/* Form 2: Publish Announcement */}
              <section className="admin-card glass-panel">
                <h2>Publish New Announcement</h2>
                
                <form onSubmit={handlePublishAnnouncement} style={{display: "flex", flexDirection: "column", gap: "12px"}}>
                  <div className="form-group">
                    <label>Announcement Title</label>
                    <input 
                      type="text" 
                      className="form-control" 
                      placeholder="e.g. Semester Exam Postponement Announcement"
                      value={announceTitle}
                      onChange={(e) => setAnnounceTitle(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label>Announcement Details</label>
                    <textarea 
                      className="form-control" 
                      placeholder="Enter announcement description..."
                      value={announceContent}
                      onChange={(e) => setAnnounceContent(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label>Clearance Level</label>
                    <select 
                      className="form-control"
                      value={announceRoleAccess}
                      onChange={(e) => setAnnounceRoleAccess(e.target.value)}
                    >
                      <option value="All">All Students & Faculty</option>
                      <option value="Student">Students Only</option>
                      <option value="Faculty">Faculty Members Only</option>
                    </select>
                  </div>

                  {announceAlert && (
                    <div className={`status-alert ${announceAlert.type}`}>
                      {announceAlert.text}
                    </div>
                  )}

                  <button 
                    type="submit" 
                    className="btn-submit notify-btn"
                    disabled={announceLoading || !announceTitle.trim() || !announceContent.trim()}
                  >
                    {announceLoading ? "Publishing Announcement..." : "📣 Dispatch Announcement"}
                  </button>
                </form>
              </section>

              {/* Form 3 / Wide Table: Document Clearance Updation Panel */}
              <section className="admin-card glass-panel admin-wide-section">
                <h2>Document Clearance Updation Panel</h2>

                {editAlert && (
                  <div className={`status-alert ${editAlert.type}`} style={{marginBottom: "12px"}}>
                    {editAlert.text}
                  </div>
                )}

                {/* Inline Editing Form */}
                {editingDoc && (
                  <div className="edit-form-panel" style={{marginBottom: "16px"}}>
                    <div className="edit-form-header">
                      <h3>Update clearance for: <strong>{editingDoc.title}</strong></h3>
                      <span className="notification-time">Editing tags</span>
                    </div>

                    <form onSubmit={handleUpdateDocumentMetadata}>
                      <div className="form-row" style={{marginBottom: "12px"}}>
                        <div className="form-group">
                          <label>Clearance Level</label>
                          <select
                            className="form-control"
                            value={editingDoc.role_access}
                            onChange={(e) => setEditingDoc({...editingDoc, role_access: e.target.value})}
                          >
                            <option value="All">All Students & Faculty</option>
                            <option value="Student">Students Only</option>
                            <option value="Faculty">Faculty Members Only</option>
                          </select>
                        </div>
                        
                        <div className="form-group">
                          <label>Document Type</label>
                          <select
                            className="form-control"
                            value={editingDoc.doc_type}
                            onChange={(e) => setEditingDoc({...editingDoc, doc_type: e.target.value})}
                          >
                            <option value="Curriculum">Syllabus / Curriculum</option>
                            <option value="Activity Points">Activity Points</option>
                            <option value="Guidelines">University Guides</option>
                          </select>
                        </div>
                      </div>

                      <div className="form-group" style={{marginBottom: "12px"}}>
                        <label>General Topic</label>
                        <input
                          type="text"
                          className="form-control"
                          value={editingDoc.topic}
                          onChange={(e) => setEditingDoc({...editingDoc, topic: e.target.value})}
                        />
                      </div>

                      <div className="edit-form-actions">
                        <button type="submit" className="btn-submit" style={{marginTop: 0}} disabled={editLoading}>
                          {editLoading ? "Updating..." : "Save Tag Changes"}
                        </button>
                        <button type="button" className="btn-cancel" onClick={() => setEditingDoc(null)} disabled={editLoading}>
                          Cancel
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                <div className="table-container">
                  {docsLoading ? (
                    <div style={{padding: "20px", textAlign: "center", color: "var(--text-secondary)"}}>Loading indexed document list...</div>
                  ) : documents.length === 0 ? (
                    <div style={{padding: "20px", textAlign: "center", color: "var(--text-muted)"}}>No indexed documents found in RAG database. Ingest a document above to see it list here.</div>
                  ) : (
                    <table className="doc-table">
                      <thead>
                        <tr>
                          <th>Document Filename</th>
                          <th>Clearance Level</th>
                          <th>Doc Type</th>
                          <th>Topic Tag</th>
                          <th>Uploaded At</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {documents.map((doc, idx) => (
                          <tr key={idx}>
                            <td style={{fontWeight: "500"}}>{doc.title}</td>
                            <td>
                              <span className={`audience-badge ${doc.role_access.toLowerCase()}`}>
                                {doc.role_access}
                              </span>
                            </td>
                            <td>{doc.doc_type}</td>
                            <td>{doc.topic}</td>
                            <td style={{color: "var(--text-muted)", fontSize: "11px"}}>
                              {new Date(doc.uploaded_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                            </td>
                            <td>
                              <div style={{display: "flex", gap: "8px"}}>
                                <button 
                                  className="btn-edit-pill"
                                  onClick={() => {
                                    setEditingDoc({
                                      title: doc.title,
                                      role_access: doc.role_access,
                                      doc_type: doc.doc_type,
                                      topic: doc.topic
                                    });
                                    setEditAlert(null);
                                  }}
                                >
                                  Edit Clearance
                                </button>
                                <button 
                                  className="btn-edit-pill"
                                  style={{background: "rgba(239, 68, 68, 0.15)", color: "#f87171", borderColor: "rgba(239, 68, 68, 0.3)"}}
                                  onClick={() => handleDeleteDocument(doc.title)}
                                >
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </section>

            </div>
          )}

        </main>
      </div>
    </div>
  );
}

export default App;
