import React, { useState } from "react";
import axios from "axios";
import "./App.css";

const API_URL = "http://localhost:8000";

function App() {
  const [file, setFile] = useState(null);
  const [token, setToken] = useState(() => sessionStorage.getItem("rag_token") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [docItems, setDocItems] = useState([]);
  const authHeaders = { Authorization: `Bearer ${token}` };
  const authenticate = async (register) => {
    try {
      if (register) await axios.post(`${API_URL}/auth/register`, { email, password });
      const response = await axios.post(`${API_URL}/auth/login`, { email, password });
      sessionStorage.setItem("rag_token", response.data.access_token);
      setToken(response.data.access_token);
      setPassword("");
    } catch (error) { alert(error.response?.data?.detail || "Authentication failed"); }
  };
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [useTools, setUseTools] = useState(false);
  const [documents, setDocuments] = useState([]);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) {
      alert("Please select a PDF file");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: { ...authHeaders, "Content-Type": "multipart/form-data" },
      });

      alert("Upload accepted. Processing in background; refresh documents to check status.");
      setFile(null);
      fetchDocuments(); 
    } catch (error) {
      alert("Error uploading file: " + error.response?.data?.detail);
    } finally {
      setUploading(false);
    }
  };


  const handleAsk = async () => {
    if (!question.trim()) {
      alert("Please enter a question");
      return;
    }

    setLoading(true);
    setAnswer(null);

    try {
      const response = await axios.post(`${API_URL}/ask`, {
        question: question,
        use_tools: useTools,
      }, { headers: authHeaders });

      setAnswer(response.data);
    } catch (error) {
      alert("Error: " + error.response?.data?.detail);
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_URL}/documents`, { headers: authHeaders });
      setDocuments(response.data.documents);
      setDocItems(response.data.items || []);
    } catch (error) {
      console.error("Error fetching documents:", error);
    }
  };

  const handleClear = async () => {
    if (window.confirm("Clear all documents?")) {
      try {
        await axios.delete(`${API_URL}/clear`, { headers: authHeaders });
        setDocuments([]);
        setDocItems([]);
        setAnswer(null);
        alert("All documents cleared");
      } catch (error) {
        alert("Error clearing documents");
      }
    }
  };
  React.useEffect(() => {
    fetchDocuments();
  }, [token]);
  return (
    <div className="App">
      <header>
        <h1>📚 Smart Document Q&A</h1>
        <p>Upload PDFs and ask questions powered by RAG + LangChain</p>
      </header>

      <div className="container">
        {!token ? <div className="section"><h2>Sign in or register</h2><input placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} /><input type="password" placeholder="Password (8+ characters)" value={password} onChange={e => setPassword(e.target.value)} /><button onClick={() => authenticate(false)}>Log in</button><button onClick={() => authenticate(true)}>Register</button></div> : <div className="section"><button onClick={() => { sessionStorage.removeItem("rag_token"); setToken(""); setDocuments([]); }}>Log out</button><button onClick={fetchDocuments}>Refresh document status</button></div>}
        {token && <>
        {/* ===== UPLOAD SECTION ===== */}
        <div className="section upload-section">
          <h2>1. Upload PDF</h2>
          <input type="file" accept=".pdf" onChange={handleFileChange} />
          <button onClick={handleUpload} disabled={uploading || !file}>
            {uploading ? "Uploading..." : "Upload"}
          </button>

          {documents.length > 0 && (
            <div className="documents">
              <h3>Uploaded Documents ({documents.length})</h3>
              <ul>
                {documents.map((doc, idx) => (
                  <li key={idx}>📄 {doc} — {docItems[idx]?.status || "unknown"}</li>
                ))}
              </ul>
              <button onClick={handleClear} className="clear-btn">
                Clear All
              </button>
            </div>
          )}
        </div>

        {/* ===== QUESTION SECTION ===== */}
        <div className="section question-section">
          <h2>2. Ask Questions</h2>
          <textarea
            placeholder="What is this document about?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
          />

          <div className="options">
            <label>
              <input
                type="checkbox"
                checked={useTools}
                onChange={(e) => setUseTools(e.target.checked)}
              />
              Enable Tools (Calculator, etc.)
            </label>
          </div>

          <button
            onClick={handleAsk}
            disabled={loading || !docItems.some(d => d.status === "ready")}
          >
            {loading ? "Thinking..." : "Ask Question"}
          </button>
        </div>

        {/* ===== ANSWER SECTION ===== */}
        {answer && (
          <div className="section answer-section">
            <h2>Answer</h2>
            <div className="answer">
              <p>{answer.answer}</p>
            </div>

            <h3>Sources</h3>
            <ul className="sources">
              {answer.sources.map((source, idx) => (
                <li key={idx}>{source}</li>
              ))}
            </ul>
          </div>
        )}
        </>}
      </div>
    </div>
  );
}

export default App;
