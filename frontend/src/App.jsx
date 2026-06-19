import { useState, useRef, useEffect } from 'react'
// Mise à jour des icônes : Ajout de Cpu (nouveau logo), Edit2 (renommer) et X (supprimer)
import { Send, FileText, UploadCloud, Terminal, Loader2, Cpu, Trash2, MessageSquareX, FolderOpen, Plus, Edit2, X, Check } from 'lucide-react'

const API_URL = "http://127.0.0.1:8000"

const generateMissionId = () => `Mission-${Math.random().toString(36).substring(2, 6).toUpperCase()}`

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const [fileStatus, setFileStatus] = useState("Aucun document classifié chargé.")
  
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(generateMissionId())
  
  // NOUVEAU : État pour gérer le renommage en cours
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editingTitle, setEditingTitle] = useState("")

  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  useEffect(() => {
    fetchSessions()
  }, [])

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_URL}/sessions`)
      const data = await res.json()
      if (data.status === "success") {
        setSessions(data.sessions)
      }
    } catch (err) {
      console.error("Erreur:", err)
    }
  }

  const loadHistory = async (sessionId) => {
    if (editingSessionId === sessionId) return; // Évite de charger si on est en train d'éditer
    setCurrentSessionId(sessionId)
    setFileStatus(`Bascule sur la mission : ${sessionId}`)
    try {
      const res = await fetch(`${API_URL}/history/${sessionId}`)
      const data = await res.json()
      if (data.status === "success") {
        setMessages(data.history)
      }
    } catch (err) {
      setFileStatus("❌ Erreur chargement historique.")
    }
  }

  const createNewMission = () => {
    const newId = generateMissionId()
    setCurrentSessionId(newId)
    setMessages([])
    setFileStatus(`Nouvelle mission initiée : ${newId}.`)
  }

  // --- NOUVELLES FONCTIONS : SUPPRESSION ET RENOMMAGE ---
  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation(); // Empêche le clic de déclencher 'loadHistory'
    if (!window.confirm("Détruire définitivement cette mission ?")) return;

    try {
      const res = await fetch(`${API_URL}/sessions/${sessionId}`, { method: "DELETE" })
      if (res.ok) {
        setFileStatus(`Mission ${sessionId} détruite.`)
        if (currentSessionId === sessionId) {
           createNewMission(); // Crée une nouvelle session si on supprime l'actuelle
        } else {
           fetchSessions(); // Met à jour la liste
        }
      }
    } catch (err) {
      setFileStatus("❌ Erreur de suppression.")
    }
  }

  const startEditing = (session, e) => {
      e.stopPropagation();
      setEditingSessionId(session.session_id);
      setEditingTitle(session.title);
  }

  const saveRename = async (sessionId, e) => {
      e.stopPropagation();
      if (!editingTitle.trim()) {
          setEditingSessionId(null);
          return;
      }

      try {
          const res = await fetch(`${API_URL}/sessions/${sessionId}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ new_title: editingTitle })
          });
          if (res.ok) {
              setEditingSessionId(null);
              fetchSessions(); // Rafraîchit la liste avec le nouveau nom
          }
      } catch (err) {
          console.error("Erreur renommage", err);
      }
  }

  const cancelRename = (e) => {
      e.stopPropagation();
      setEditingSessionId(null);
  }
  // ----------------------------------------------------

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setFileStatus("Chiffrement...")
    const formData = new FormData()
    formData.append("file", file)
    try {
      const res = await fetch(`${API_URL}/upload?session_id=${currentSessionId}`, { method: "POST", body: formData })
      if (res.ok) {
        setFileStatus(`✔️ Document lié à ${currentSessionId}`)
        fetchSessions()
      } else setFileStatus("❌ Échec.")
    } catch (err) {
      setFileStatus("❌ Erreur serveur.")
    }
  }

  const clearChat = () => setMessages([]) 

  const clearDatabase = async () => {
    setFileStatus("Purge RAG en cours...")
    try {
      const res = await fetch(`${API_URL}/clear_docs`, { method: "POST" })
      if (res.ok) setFileStatus("🗑️ Base documentaire purgée.")
      else setFileStatus("❌ Échec de purge.")
    } catch (err) {
      setFileStatus("❌ Erreur serveur.")
    }
  }

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!input.trim() || isTyping) return
    const userMessage = { role: "user", content: input }
    setMessages(prev => [...prev, userMessage])
    setInput("")
    setIsTyping(true)
    setMessages(prev => [...prev, { role: "assistant", content: "", sources: [] }])
    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [...messages, userMessage], temperature: 0.1, session_id: currentSessionId })
      })
      if (!response.ok) throw new Error("Erreur serveur")
      if (messages.length === 0) fetchSessions()
      const reader = response.body.getReader()
      const decoder = new TextDecoder("utf-8")
      let buffer = ""
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop()
        for (const line of lines) {
          if (line.trim()) {
            const data = JSON.parse(line)
            setMessages(prev => {
              const newMessages = [...prev]
              const lastIndex = newMessages.length - 1
              const lastMessage = { ...newMessages[lastIndex] }
              if (data.sources) lastMessage.sources = data.sources
              else if (data.chunk) lastMessage.content += data.chunk
              newMessages[lastIndex] = lastMessage
              return newMessages
            })
          }
        }
      }
    } catch (error) {
      setMessages(prev => {
        const newMessages = [...prev]
        newMessages[newMessages.length - 1].content = "⚠️ ERREUR : " + error.message
        return newMessages
      })
    } finally {
      setIsTyping(false)
    }
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-300 font-sans">
      <div className="w-80 bg-slate-900 border-r border-emerald-900/30 p-6 flex flex-col shadow-2xl relative z-10">
        
        {/* NOUVEAU LOGO */}
        <div className="flex items-center gap-3 mb-8 text-emerald-500">
          <Cpu size={36} className="text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]" />
          <h1 className="text-xl font-bold tracking-wider">LOCAL_LLM_AGENT<br/><span className="text-sm text-slate-500 font-mono">SECURE AGENT v4.0</span></h1>
        </div>

        <div className="flex-1 space-y-8 overflow-y-auto pr-2">
          
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xs font-bold text-slate-500 tracking-widest uppercase">Missions Actives</h2>
              <button onClick={createNewMission} className="p-1.5 bg-emerald-900/30 hover:bg-emerald-800/50 rounded text-emerald-500 transition-colors" title="Nouvelle Mission">
                <Plus size={16} />
              </button>
            </div>
            
            <div className="space-y-2 max-h-[30vh] overflow-y-auto custom-scrollbar">
              {sessions.length === 0 ? (
                <p className="text-xs text-slate-600 italic">Aucune mission enregistrée.</p>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.session_id}
                    onClick={() => loadHistory(session.session_id)}
                    className={`group w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-colors border cursor-pointer ${
                      currentSessionId === session.session_id 
                        ? 'bg-emerald-900/20 border-emerald-700/50 text-emerald-400' 
                        : 'bg-slate-950/50 border-slate-800 text-slate-400 hover:bg-slate-800 hover:border-slate-600'
                    }`}
                  >
                    {editingSessionId === session.session_id ? (
                      // Mode Édition
                      <div className="flex items-center w-full gap-2" onClick={e => e.stopPropagation()}>
                        <FolderOpen size={14} className="text-emerald-500 flex-shrink-0" />
                        <input 
                          type="text" 
                          value={editingTitle} 
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && saveRename(session.session_id, e)}
                          className="flex-1 bg-slate-900 border border-emerald-500/50 rounded px-1 text-slate-200 outline-none"
                          autoFocus
                        />
                        <button onClick={(e) => saveRename(session.session_id, e)} className="text-emerald-500 hover:text-emerald-400"><Check size={14}/></button>
                        <button onClick={cancelRename} className="text-slate-500 hover:text-red-400"><X size={14}/></button>
                      </div>
                    ) : (
                      // Mode Affichage Normal
                      <>
                        <div className="flex items-center gap-2 overflow-hidden">
                          <FolderOpen size={14} className={currentSessionId === session.session_id ? 'text-emerald-500 flex-shrink-0' : 'text-slate-500 flex-shrink-0'} />
                          <span className="truncate">{session.title}</span>
                        </div>
                        {/* Boutons d'action visibles au survol */}
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={(e) => startEditing(session, e)} className="p-1 hover:text-emerald-300 transition-colors" title="Renommer">
                            <Edit2 size={12} />
                          </button>
                          <button onClick={(e) => handleDeleteSession(session.session_id, e)} className="p-1 hover:text-red-400 transition-colors" title="Supprimer">
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          <hr className="border-slate-800" />

          <div>
            <h2 className="text-xs font-bold text-slate-500 tracking-widest mb-4 uppercase">Base Documentaire</h2>
            <label className="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-emerald-900/50 rounded-lg cursor-pointer bg-slate-950/50 hover:bg-emerald-900/20 transition-colors">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <UploadCloud className="w-8 h-8 mb-2 text-emerald-600" />
                <p className="text-sm text-slate-400 text-center">Uploader un document<br/><span className="text-xs text-slate-500">(PDF, TXT, MD, DOCX, CSV, JPG, PNG)</span></p>
              </div>
              <input type="file" className="hidden" accept=".pdf,.txt,.md,.docx,.doc,.csv,.png,.jpg,.jpeg" onChange={handleFileUpload} />
            </label>
            <p className="mt-3 text-xs font-mono text-emerald-600/70 leading-relaxed">{fileStatus}</p>
          </div>

          <div>
            <h2 className="text-xs font-bold text-slate-500 tracking-widest mb-4 uppercase">Contrôle Système</h2>
            <div className="space-y-3">
              <button onClick={clearChat} className="w-full flex items-center gap-3 px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm text-slate-300 transition-colors">
                <MessageSquareX size={16} className="text-emerald-500" /> Effacer l'écran
              </button>
              <button onClick={clearDatabase} className="w-full flex items-center gap-3 px-4 py-3 bg-red-950/20 hover:bg-red-900/40 border border-red-900/50 rounded-lg text-sm text-red-400 transition-colors">
                <Trash2 size={16} /> Purger bases RAG
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col h-full relative">
        <header className="h-16 bg-slate-900/50 border-b border-emerald-900/30 flex items-center px-8 backdrop-blur-sm relative z-10 justify-between">
          <div className="flex items-center">
            <Terminal size={18} className="text-emerald-500 mr-3" />
            <span className="font-mono text-sm tracking-widest text-emerald-500/80">TERMINAL OPÉRATIONNEL</span>
          </div>
          <div className="px-3 py-1 bg-slate-800/80 border border-slate-700 rounded text-xs font-mono text-slate-400">
            ID Mission : <span className="text-emerald-400">{currentSessionId}</span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-8 space-y-6 scroll-smooth">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-4">
              <Cpu size={64} className="opacity-20" />
              <p className="font-mono tracking-widest uppercase">Mission {currentSessionId} prête.</p>
              <p className="text-sm font-mono opacity-50 text-center">Uploadez un document pour initier la mémoire de cette session,<br/>ou posez une question générale.</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-3xl rounded-lg p-5 ${msg.role === 'user' ? 'bg-slate-800 text-slate-200 border border-slate-700 shadow-lg' : 'bg-emerald-950/20 border-l-4 border-emerald-600 text-emerald-50 shadow-md'}`}>
                <div className="flex items-center gap-2 mb-2 opacity-50">
                  {msg.role === 'user' ? <Terminal size={14}/> : <Cpu size={14}/>}
                  <span className="text-xs font-mono uppercase tracking-wider">{msg.role === 'user' ? 'Opérateur' : 'Système IA'}</span>
                </div>
                <div className="whitespace-pre-wrap leading-relaxed text-sm md:text-base">{msg.content}</div>
                {msg.sources && msg.sources.length > 0 && !isTyping && (
                  <div className="mt-4 pt-4 border-t border-emerald-900/30">
                    <p className="text-xs font-mono text-emerald-600 mb-2 flex items-center gap-2">
                      <FileText size={12}/> SOURCES EXTRAITES (Base RAG) :
                    </p>
                    {msg.sources.map((src, i) => (
                      <div key={i} className="text-xs text-slate-400 bg-slate-900/50 p-3 rounded mb-2 font-mono border border-slate-800/50 leading-relaxed">
                        {src.substring(0, 200)}...
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isTyping && messages.length > 0 && messages[messages.length - 1].content === "" && (
            <div className="flex justify-start">
              <div className="bg-emerald-950/20 border-l-4 border-emerald-600 rounded-lg p-4 flex items-center gap-3 text-emerald-500 font-mono text-sm tracking-wider">
                <Loader2 className="animate-spin" size={16} /> ANALYSE EN COURS...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-6 bg-slate-900/80 border-t border-emerald-900/30 backdrop-blur-md relative z-10">
          <form onSubmit={sendMessage} className="flex gap-4 max-w-4xl mx-auto relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Entrez votre requête pour la mission ${currentSessionId}...`}
              disabled={isTyping}
              className="flex-1 bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-6 py-4 focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 transition-all font-mono text-sm disabled:opacity-50"
            />
            <button type="submit" disabled={isTyping || !input.trim()} className="bg-emerald-700 hover:bg-emerald-600 text-white px-6 rounded-lg flex items-center justify-center transition-colors disabled:opacity-50 shadow-lg shadow-emerald-900/20">
              <Send size={20} className={input.trim() ? "translate-x-1 transition-transform" : ""} />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default App