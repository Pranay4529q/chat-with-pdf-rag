import React, { useState } from "react";
import axios from "axios";
import "./App.css";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

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
  const [policyKey, setPolicyKey] = useState("");
  const [version, setVersion] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [includeSuperseded, setIncludeSuperseded] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [oldId, setOldId] = useState("");
  const [newId, setNewId] = useState("");
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [semantic, setSemantic] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [compareError, setCompareError] = useState("");
  const compare = async () => {
    setCompareError("");
    setComparison(null);
    setSemantic(null);
    if (!oldId || !newId || oldId === newId) {
      setCompareError("Choose two different processed versions.");
      return;
    }
    setComparing(true);
    try {
      const result = await axios.post(`${API_URL}/documents/compare`,
        { old_document_id: oldId, new_document_id: newId }, { headers: authHeaders });
      setComparison(result.data);
    } catch (err) {
      setCompareError(err.response?.data?.detail || "Comparison failed");
    } finally {
      setComparing(false);
    }
  };

  const analyzeChanges = async () => {
    setCompareError("");
    setSemantic(null);
    if (!oldId || !newId || oldId === newId) {
      setCompareError("Choose two different processed versions.");
      return;
    }
    setAnalyzing(true);
    try {
      const result = await axios.post(`${API_URL}/documents/compare/semantic`,
        { old_document_id: oldId, new_document_id: newId }, { headers: authHeaders });
      setSemantic(result.data);
    } catch (err) {
      setCompareError(err.response?.data?.detail || "Semantic analysis failed; check the backend logs.");
    } finally {
      setAnalyzing(false);
    }
  };

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
    if (policyKey.trim()) formData.append("policy_key", policyKey.trim());
    if (version.trim()) formData.append("version_label", version.trim());
    if (effectiveDate) formData.append("effective_date", effectiveDate);

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
        include_superseded: includeSuperseded,
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
          <input placeholder="Policy key (same key groups versions)" value={policyKey} onChange={e => setPolicyKey(e.target.value)} />
          <input placeholder="Version label (e.g. v2)" value={version} onChange={e => setVersion(e.target.value)} />
          <label>Effective date <input type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} /></label>
          <button onClick={handleUpload} disabled={uploading || !file}>
            {uploading ? "Uploading..." : "Upload"}
          </button>

          {documents.length > 0 && (
            <div className="documents">
              <h3>Uploaded Documents ({documents.length})</h3>
              <ul>
                {documents.map((doc, idx) => (
                  <li key={idx}>📄 {doc} — {docItems[idx]?.status || "unknown"} {docItems[idx]?.version_label && `· ${docItems[idx].version_label}`} {docItems[idx]?.policy_key && `· ${docItems[idx].policy_key}`} {docItems[idx]?.is_current === false && "· Superseded"}</li>
                ))}
              </ul>
              <button onClick={handleClear} className="clear-btn">
                Clear All
              </button>
            </div>
          )}
        </div>

        <div className="section">
          <h2>2. Compare policy versions</h2>
          <p>Choose two ready documents with the same policy key. This shows textual changes with source pages; it does not determine legal or semantic conflicts.</p>
          <label>Earlier version
            <select aria-label="Earlier version" value={oldId} onChange={e => setOldId(e.target.value)}>
              <option value="">Select a document</option>
              {docItems.filter(d => d.status === "ready" && d.policy_key).map(d =>
                <option key={d.id} value={d.id}>{d.filename} ({d.version_label || "unlabeled"})</option>)}
            </select>
          </label>
          <label>Later version
            <select aria-label="Later version" value={newId} onChange={e => setNewId(e.target.value)}>
              <option value="">Select a document</option>
              {docItems.filter(d => d.status === "ready" && d.policy_key).map(d =>
                <option key={d.id} value={d.id}>{d.filename} ({d.version_label || "unlabeled"})</option>)}
            </select>
          </label>
          <button onClick={compare} disabled={comparing || !oldId || !newId}>{comparing ? "Comparing..." : "Compare versions"}</button>
          <button onClick={analyzeChanges} disabled={analyzing || comparing || !oldId || !newId}>{analyzing ? "Analyzing..." : "Analyze policy impact (AI)"}</button>
          {compareError && <p role="alert">{compareError}</p>}
          {comparison && <div aria-live="polite">
            <h3>{comparison.change_count} change groups</h3>
            <p>{comparison.method}</p>
            {comparison.changes.length === 0 && <p>No textual changes detected.</p>}
            {comparison.changes.map((change, idx) =>
              <div key={idx} className="comparison-change">
                <h4>{change.type}</h4>
                <div><strong>Before</strong>
                  {change.before.map((line, i) => <p key={i}>Page {line.page}: {line.text}</p>)}
                </div>
                <div><strong>After</strong>
                  {change.after.map((line, i) => <p key={i}>Page {line.page}: {line.text}</p>)}
                </div>
              </div>)}
            {comparison.truncated && <p>Results truncated. Narrow the documents for detailed review.</p>}
          </div>}
        </div>
        {semantic && <div className="section" aria-live="polite">
          <h2>AI policy impact analysis</h2>
          <p>{semantic.method}</p>
          <p>{semantic.change_count} groups analyzed. Interpretations require human review.</p>
          {semantic.changes.map((change, idx) => <div key={idx} className="comparison-change">
            <h3>Change {change.group} — {change.type}</h3>
            {change.interpretation ? <>
              <p><strong>{change.interpretation.category}</strong>: {change.interpretation.summary}</p>
              <p><strong>Potential impact:</strong> {change.interpretation.impact}</p>
              {change.interpretation.uncertainty && <p><strong>Uncertainty:</strong> {change.interpretation.uncertainty}</p>}
            </> : <p>Interpretation unavailable; inspect evidence below.</p>}
            {change.numeric_change && <p><strong>INR change:</strong> {change.numeric_change.delta_inr}; percentage: {change.numeric_change.percent_change === null ? "N/A" : change.numeric_change.percent_change + "%"}</p>}
            <details><summary>Review exact evidence and page numbers</summary>
              <strong>Before</strong>
              {change.before.map((line, i) => <p key={i}>Page {line.page}: {line.text}</p>)}
              <strong>After</strong>
              {change.after.map((line, i) => <p key={i}>Page {line.page}: {line.text}</p>)}
            </details>
          </div>)}
          {semantic.truncated && <p>Analysis truncated to protect latency and API usage.</p>}
        </div>}
        {/* ===== QUESTION SECTION ===== */}
        <div className="section question-section">
          <h2>3. Ask Questions</h2>
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
                checked={includeSuperseded}
                onChange={(e) => setIncludeSuperseded(e.target.checked)}
              />
              Include superseded document versions (for historical comparison)
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
              {(answer.citations || []).map((source, idx) => (
                <li key={idx}><strong>[{source.index}] {source.document} · page {source.page}</strong>
                {source.version && ` · ${source.version}`} {source.is_current === false && " · Superseded"}
                <details><summary>View retrieved passage</summary><pre style={{whiteSpace:"pre-wrap"}}>{source.passage}</pre></details></li>
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
