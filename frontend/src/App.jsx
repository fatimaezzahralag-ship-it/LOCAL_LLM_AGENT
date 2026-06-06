import { useState, useRef, useEffect } from 'react'
import { Send, FileText, UploadCloud, Terminal, Loader2, ShieldCheck } from 'lucide-react'

const API_URL = "http://127.0.0.1:8000"

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const [fileStatus, setFileStatus] = useState("Aucun document classifié chargé.")
  const messagesEndRef = useRef(null)

  // Auto-scroll vers le bas
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    setFileStatus("Chiffrement et indexation en cours...")
    const formData = new FormData()
    formData.append("file", file)

    try {
      const res = await fetch(`${API_URL}/upload`, { method: "POST", body: formData })
      if (res.ok) setFileStatus(`✔️ Document sécurisé : ${file.name}`)
      else setFileStatus("❌ Échec de l'indexation.")
    } catch (err) {
      setFileStatus("❌ Erreur de connexion au serveur central.")
    }
  }

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!input.trim() || isTyping) return

    const userMessage = { role: "user", content: input }
    setMessages(prev => [...prev, userMessage])
    setInput("")
    setIsTyping(true)

    // On prépare le message vide de l'agent
    setMessages(prev => [...prev, { role: "assistant", content: "", sources: [] }])

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [...messages, userMessage], temperature: 0.1 })
      })

      if (!response.ok) throw new Error("Erreur serveur")

      // --- LECTURE DU STREAM (Le cœur de la machine à écrire) ---
      const reader = response.body.getReader()
      const decoder = new TextDecoder("utf-8")
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() // On garde la dernière ligne incomplète dans le buffer

        for (const line of lines) {
          if (line.trim()) {
            const data = JSON.parse(line)
            
            setMessages(prev => {
              const newMessages = [...prev]
              const lastIndex = newMessages.length - 1
              
              // LA CORRECTION EST ICI : On clone l'objet message pour bloquer le StrictMode
              const lastMessage = { ...newMessages[lastIndex] }
              
              if (data.sources) {
                lastMessage.sources = data.sources
              } else if (data.chunk) {
                lastMessage.content += data.chunk
              }
              
              newMessages[lastIndex] = lastMessage
              return newMessages
            })
          }
        }
      }
    } catch (error) {
      setMessages(prev => {
        const newMessages = [...prev]
        newMessages[newMessages.length - 1].content = "⚠️ ERREUR SYSTÈME : " + error.message
        return newMessages
      })
    } finally {
      setIsTyping(false)
    }
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-300 font-sans">
      
      {/* SIDEBAR TACTIQUE */}
      <div className="w-80 bg-slate-900 border-r border-emerald-900/30 p-6 flex flex-col shadow-2xl">
        <div className="flex items-center gap-3 mb-10 text-emerald-500">
          <ShieldCheck size={32} />
          <h1 className="text-xl font-bold tracking-wider">LOCAL_LLM_AGENT<br/><span className="text-sm text-slate-500 font-mono">SECURE AGENT v3.0</span></h1>
        </div>

        <div className="flex-1">
          <h2 className="text-xs font-bold text-slate-500 tracking-widest mb-4 uppercase">Base Documentaire</h2>
          
          <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-emerald-900/50 rounded-lg cursor-pointer bg-slate-950/50 hover:bg-emerald-900/20 transition-colors">
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <UploadCloud className="w-8 h-8 mb-3 text-emerald-600" />
              <p className="text-sm text-slate-400">Uploader un PDF</p>
            </div>
            <input type="file" className="hidden" accept=".pdf" onChange={handleFileUpload} />
          </label>
          <p className="mt-4 text-xs font-mono text-emerald-600/70">{fileStatus}</p>
        </div>
      </div>

      {/* ZONE DE CHAT */}
      <div className="flex-1 flex flex-col h-full relative">
        {/* En-tête */}
        <header className="h-16 bg-slate-900/50 border-b border-emerald-900/30 flex items-center px-8 backdrop-blur-sm">
          <Terminal size={18} className="text-emerald-500 mr-3" />
          <span className="font-mono text-sm tracking-widest text-emerald-500/80">TERMINAL DE COMMANDEMENT ACTIF</span>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-8 space-y-6 scroll-smooth">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-4">
              <ShieldCheck size={64} className="opacity-20" />
              <p className="font-mono tracking-widest uppercase">En attente de directives...</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-3xl rounded-lg p-5 ${
                msg.role === 'user' 
                  ? 'bg-slate-800 text-slate-200 border border-slate-700 shadow-lg' 
                  : 'bg-emerald-950/20 border-l-4 border-emerald-600 text-emerald-50 shadow-md'
              }`}>
                {/* L'icône du rôle */}
                <div className="flex items-center gap-2 mb-2 opacity-50">
                  {msg.role === 'user' ? <Terminal size={14}/> : <ShieldCheck size={14}/>}
                  <span className="text-xs font-mono uppercase tracking-wider">
                    {msg.role === 'user' ? 'Opérateur' : 'Système IA'}
                  </span>
                </div>
                
                {/* Le texte */}
                <div className="whitespace-pre-wrap leading-relaxed">
                  {msg.content}
                </div>

                {/* Les sources (si l'agent a fini de parler et qu'il y a des sources) */}
                {msg.sources && msg.sources.length > 0 && !isTyping && (
                  <div className="mt-4 pt-4 border-t border-emerald-900/30">
                    <p className="text-xs font-mono text-emerald-600 mb-2 flex items-center gap-2">
                      <FileText size={12}/> SOURCES IDENTIFIÉES :
                    </p>
                    {msg.sources.map((src, i) => (
                      <div key={i} className="text-xs text-slate-400 bg-slate-900/50 p-2 rounded mb-1 font-mono border border-slate-800/50">
                        {src.substring(0, 150)}...
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* L'indicateur "En cours de réflexion" */}
          {isTyping && messages.length > 0 && messages[messages.length - 1].content === "" && (
            <div className="flex justify-start">
              <div className="bg-emerald-950/20 border-l-4 border-emerald-600 rounded-lg p-4 flex items-center gap-3 text-emerald-500 font-mono text-sm tracking-wider">
                <Loader2 className="animate-spin" size={16} />
                ANALYSE EN COURS...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Zone de saisie */}
        <div className="p-6 bg-slate-900/80 border-t border-emerald-900/30 backdrop-blur-md">
          <form onSubmit={sendMessage} className="flex gap-4 max-w-4xl mx-auto relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Entrez votre requête opérationnelle..."
              disabled={isTyping}
              className="flex-1 bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-6 py-4 focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 transition-all font-mono text-sm disabled:opacity-50"
            />
            <button 
              type="submit" 
              disabled={isTyping || !input.trim()}
              className="bg-emerald-700 hover:bg-emerald-600 text-white px-6 rounded-lg flex items-center justify-center transition-colors disabled:opacity-50 shadow-lg shadow-emerald-900/20"
            >
              <Send size={20} className={input.trim() ? "translate-x-1 transition-transform" : ""} />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default App