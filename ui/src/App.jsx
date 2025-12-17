import { useState, useRef, useEffect } from 'react'
import {
  MessageSquare,
  Eye,
  Brain,
  Monitor,
  DollarSign,
  Send,
  Sparkles,
  Image as ImageIcon,
  FileText,
  Zap,
  Activity
} from 'lucide-react'
import './App.css'
import DocumentViewer from './components/DocumentViewer'
import ExtractedDataSidebar from './components/ExtractedDataSidebar'

function App() {
  const [activeTab, setActiveTab] = useState('chat')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [stats, setStats] = useState({
    tokensToday: 0,
    costToday: 0,
    requestsToday: 0
  })
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/costs/summary?period=today')
      const data = await response.json()
      setStats({
        tokensToday: 0,
        costToday: data.total_cost,
        requestsToday: data.requests
      })
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [...messages, userMessage],
          model: 'auto',
          temperature: 1.0
        })
      })

      if (!response.ok) throw new Error('Chat request failed')

      const data = await response.json()
      const assistantMessage = {
        role: 'assistant',
        content: data.content
      }
      setMessages(prev => [...prev, assistantMessage])
      fetchStats()
    } catch (error) {
      console.error('Error:', error)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error: Failed to get response'
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const features = [
    { id: 'chat', icon: MessageSquare, label: 'Chat', color: '#007aff' },
    { id: 'vision', icon: Eye, label: 'Vision', color: '#ff9f0a' },
    { id: 'reasoning', icon: Brain, label: 'Reasoning', color: '#bf5af2' },
    { id: 'computer', icon: Monitor, label: 'Computer Use', color: '#30d158' },
    { id: 'costs', icon: DollarSign, label: 'Costs', color: '#ff453a' },
  ]

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <Sparkles size={24} className="logo" />
          <h1>Assistant</h1>
        </div>

        <nav className="nav">
          {features.map(feature => (
            <button
              key={feature.id}
              className={`nav-item ${activeTab === feature.id ? 'active' : ''}`}
              onClick={() => setActiveTab(feature.id)}
            >
              <feature.icon size={20} />
              <span>{feature.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="stat">
            <Activity size={14} />
            <span>{stats.requestsToday} requests</span>
          </div>
          <div className="stat">
            <Zap size={14} />
            <span>${stats.costToday.toFixed(4)}</span>
          </div>
        </div>
      </aside>

      <main className="main">
        {activeTab === 'chat' && <ChatView messages={messages} isLoading={isLoading} messagesEndRef={messagesEndRef} />}
        {activeTab === 'vision' && <VisionView />}
        {activeTab === 'reasoning' && <ReasoningView />}
        {activeTab === 'computer' && <ComputerView />}
        {activeTab === 'costs' && <CostsView />}

        {activeTab === 'chat' && (
          <div className="input-container">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Message assistant..."
              disabled={isLoading}
            />
            <button
              className="send-button"
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
            >
              <Send size={18} />
            </button>
          </div>
        )}
      </main>
    </div>
  )
}

function ChatView({ messages, isLoading, messagesEndRef }) {
  return (
    <div className="chat-view">
      {messages.length === 0 ? (
        <div className="empty-state">
          <Sparkles size={48} />
          <h2>Start a conversation</h2>
          <p>Ask me anything or test other features</p>
        </div>
      ) : (
        <div className="messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-content">{msg.content}</div>
            </div>
          ))}
          {isLoading && (
            <div className="message assistant">
              <div className="message-content typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}
    </div>
  )
}

function VisionView() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [extractType, setExtractType] = useState('invoice')
  const [includeBBox, setIncludeBBox] = useState(true)
  const [isProcessing, setIsProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [extractedData, setExtractedData] = useState(null)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [hoveredField, setHoveredField] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [viewMode, setViewMode] = useState('upload') // 'upload' or 'viewer'
  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      // Create object URL for PDF preview
      if (file.type === 'application/pdf') {
        setPdfUrl(URL.createObjectURL(file))
      }
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) {
      setSelectedFile(file)
      if (file.type === 'application/pdf') {
        setPdfUrl(URL.createObjectURL(file))
      }
    }
  }

  const handleExtract = async () => {
    if (!selectedFile) return

    setIsProcessing(true)
    setResult(null)
    setExtractedData(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('extract_type', extractType)
      formData.append('detail', 'auto')
      formData.append('include_bbox', includeBBox)

      const response = await fetch('/api/vision/extract', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) throw new Error('Vision extraction failed')

      const data = await response.json()
      setResult(data)

      // Parse extracted data for viewer
      if (extractType === 'invoice' && data.content) {
        try {
          const parsed = JSON.parse(data.content)
          console.log('📄 Extracted Data:', parsed)
          console.log('📦 Prepared Bounding Boxes:', prepareBoundingBoxes(parsed))
          setExtractedData(parsed)
          setViewMode('viewer')
        } catch (e) {
          console.error('❌ Failed to parse invoice data:', e)
        }
      }
    } catch (error) {
      console.error('Error:', error)
      setResult({ error: error.message })
    } finally {
      setIsProcessing(false)
    }
  }

  const handleBackToUpload = () => {
    setViewMode('upload')
  }

  const prepareBoundingBoxes = (data) => {
    if (!data) return []

    const boxes = []

    // Process top-level fields
    Object.entries(data).forEach(([fieldName, fieldValue]) => {
      if (fieldValue && typeof fieldValue === 'object' && fieldValue.bbox) {
        boxes.push({
          fieldName,
          bbox: fieldValue.bbox
        })
      }
    })

    // Process Items array (line items)
    if (data.Items && Array.isArray(data.Items)) {
      data.Items.forEach((item, idx) => {
        Object.entries(item).forEach(([key, value]) => {
          if (value && typeof value === 'object' && value.bbox) {
            boxes.push({
              fieldName: `Items[${idx}].${key}`,
              bbox: value.bbox
            })
          }
        })
      })
    }

    return boxes
  }

  // Viewer mode - show document with interactive bounding boxes
  if (viewMode === 'viewer' && pdfUrl && extractedData) {
    const handleFieldHover = (fieldName) => {
      console.log('🔍 Hovering field:', fieldName)
      setHoveredField(fieldName)
    }

    return (
      <div className="document-viewer-container">
        <div className="viewer-header">
          <button onClick={handleBackToUpload} className="back-button">
            ← Back to Upload
          </button>
          <div className="viewer-stats">
            <span>Pages: {result?.pages_processed}</span>
            <span>Cost: ${result?.cost.toFixed(4)}</span>
            <span>Model: {result?.model}</span>
          </div>
        </div>
        <div className="viewer-content">
          <div className="viewer-document">
            <DocumentViewer
              pdfUrl={pdfUrl}
              boundingBoxes={prepareBoundingBoxes(extractedData)}
              hoveredField={hoveredField}
              onFieldHover={handleFieldHover}
            />
          </div>
          <div className="viewer-sidebar">
            <ExtractedDataSidebar
              extractedData={extractedData}
              hoveredField={hoveredField}
              onFieldHover={handleFieldHover}
            />
          </div>
        </div>
      </div>
    )
  }

  // Upload mode - show upload form
  return (
    <div className="feature-view">
      <div className="feature-header">
        <Eye size={24} />
        <h2>Vision Service</h2>
        <p>Extract data from documents and images</p>
      </div>

      <div className="card">
        <h3>Upload Document</h3>
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileChange}
          accept=".pdf,.png,.jpg,.jpeg"
          style={{ display: 'none' }}
        />
        <div
          className={`upload-zone ${isDragging ? 'dragging' : ''}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <ImageIcon size={32} />
          <p>{selectedFile ? selectedFile.name : 'Click or drag PDF, image, or invoice here'}</p>
          <button
            className="button-secondary"
            onClick={(e) => {
              e.stopPropagation()
              fileInputRef.current?.click()
            }}
          >
            Browse Files
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Extraction Type</h3>
        <div className="radio-group">
          {['structured', 'invoice', 'ocr', 'tables'].map(type => (
            <label key={type} className="radio-label">
              <input
                type="radio"
                name="extractType"
                value={type}
                checked={extractType === type}
                onChange={(e) => setExtractType(e.target.value)}
              />
              <span>{type.charAt(0).toUpperCase() + type.slice(1)}</span>
            </label>
          ))}
        </div>
        {extractType === 'invoice' && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px' }}>
            <input
              type="checkbox"
              checked={includeBBox}
              onChange={(e) => setIncludeBBox(e.target.checked)}
            />
            <span>Include bounding boxes for interactive viewer</span>
          </label>
        )}
      </div>

      <button
        className="button-primary"
        onClick={handleExtract}
        disabled={!selectedFile || isProcessing}
      >
        {isProcessing ? 'Processing...' : 'Extract Data'}
      </button>

      {result && !extractedData && (
        <div className="card">
          <h3>Result</h3>
          {result.error ? (
            <p style={{ color: 'var(--error)' }}>{result.error}</p>
          ) : (
            <>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px' }}>{result.content}</pre>
              <p style={{ marginTop: '12px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Pages: {result.pages_processed} | Cost: ${result.cost.toFixed(4)} | Model: {result.model}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ReasoningView() {
  const [problem, setProblem] = useState('')
  const [maxSteps, setMaxSteps] = useState(10)
  const [detail, setDetail] = useState('medium')
  const [isReasoning, setIsReasoning] = useState(false)
  const [result, setResult] = useState(null)

  const handleReason = async () => {
    if (!problem.trim()) return

    setIsReasoning(true)
    setResult(null)

    try {
      const response = await fetch('/api/reasoning/solve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          problem,
          max_steps: maxSteps,
          detail
        })
      })

      if (!response.ok) throw new Error('Reasoning request failed')

      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Error:', error)
      setResult({ error: error.message })
    } finally {
      setIsReasoning(false)
    }
  }

  return (
    <div className="feature-view">
      <div className="feature-header">
        <Brain size={24} />
        <h2>Reasoning Service</h2>
        <p>Multi-step problem solving with o1-mini</p>
      </div>

      <div className="card">
        <h3>Problem Statement</h3>
        <textarea
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          placeholder="Describe a complex problem to solve..."
          rows={8}
          className="textarea"
        />
      </div>

      <div className="card">
        <h3>Reasoning Settings</h3>
        <div className="setting">
          <label>Max Steps</label>
          <input
            type="number"
            value={maxSteps}
            onChange={(e) => setMaxSteps(parseInt(e.target.value))}
            className="input"
          />
        </div>
        <div className="setting">
          <label>Detail Level</label>
          <select
            className="select"
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>

      <button
        className="button-primary"
        onClick={handleReason}
        disabled={!problem.trim() || isReasoning}
      >
        {isReasoning ? 'Reasoning...' : 'Start Reasoning'}
      </button>

      {result && (
        <div className="card">
          <h3>Solution</h3>
          {result.error ? (
            <p style={{ color: 'var(--error)' }}>{result.error}</p>
          ) : (
            <>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px' }}>{result.solution}</pre>
              <p style={{ marginTop: '12px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Steps: {result.steps} | Cost: ${result.cost.toFixed(4)} | Model: {result.model}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ComputerView() {
  const [instruction, setInstruction] = useState('')
  const [environment, setEnvironment] = useState('browser')
  const [requireConfirmation, setRequireConfirmation] = useState(true)
  const [audit, setAudit] = useState(true)
  const [isExecuting, setIsExecuting] = useState(false)
  const [result, setResult] = useState(null)

  const handleExecute = async () => {
    if (!instruction.trim()) return

    setIsExecuting(true)
    setResult(null)

    try {
      const response = await fetch('/api/computer/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instruction,
          environment,
          require_confirmation: requireConfirmation,
          audit
        })
      })

      if (!response.ok) throw new Error('Computer use request failed')

      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Error:', error)
      setResult({ error: error.message })
    } finally {
      setIsExecuting(false)
    }
  }

  return (
    <div className="feature-view">
      <div className="feature-header">
        <Monitor size={24} />
        <h2>Computer Use</h2>
        <p>Automate browser and desktop tasks</p>
      </div>

      <div className="card">
        <h3>Instruction</h3>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="e.g., Search for Python tutorials on Google"
          rows={4}
          className="textarea"
        />
      </div>

      <div className="card">
        <h3>Environment</h3>
        <div className="radio-group">
          {['browser', 'desktop_mac', 'desktop_windows'].map(env => (
            <label key={env} className="radio-label">
              <input
                type="radio"
                name="environment"
                value={env}
                checked={environment === env}
                onChange={(e) => setEnvironment(e.target.value)}
              />
              <span>{env.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="card safety">
        <h3>Safety Settings</h3>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={requireConfirmation}
            onChange={(e) => setRequireConfirmation(e.target.checked)}
          />
          <span>Require confirmation for sensitive actions</span>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={audit}
            onChange={(e) => setAudit(e.target.checked)}
          />
          <span>Enable audit logging</span>
        </label>
      </div>

      <button
        className="button-primary"
        onClick={handleExecute}
        disabled={!instruction.trim() || isExecuting}
      >
        {isExecuting ? 'Executing...' : 'Execute Task'}
      </button>

      {result && (
        <div className="card">
          <h3>Result</h3>
          {result.error ? (
            <p style={{ color: 'var(--error)' }}>{result.error}</p>
          ) : (
            <>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px' }}>{result.result}</pre>
              <p style={{ marginTop: '12px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Actions: {result.actions_taken.length} | Cost: ${result.cost.toFixed(4)} | Model: {result.model}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function CostsView() {
  const [summary, setSummary] = useState({ total_cost: 0, requests: 0, avg_cost: 0 })
  const [breakdown, setBreakdown] = useState([])
  const [limits, setLimits] = useState({})

  useEffect(() => {
    fetchCostData()
  }, [])

  const fetchCostData = async () => {
    try {
      const [summaryRes, breakdownRes, limitsRes] = await Promise.all([
        fetch('/api/costs/summary?period=today'),
        fetch('/api/costs/breakdown'),
        fetch('/api/costs/limits')
      ])

      const summaryData = await summaryRes.json()
      const breakdownData = await breakdownRes.json()
      const limitsData = await limitsRes.json()

      setSummary(summaryData)
      setBreakdown(breakdownData)
      setLimits(limitsData)
    } catch (error) {
      console.error('Failed to fetch cost data:', error)
    }
  }

  return (
    <div className="feature-view">
      <div className="feature-header">
        <DollarSign size={24} />
        <h2>Cost Tracking</h2>
        <p>Monitor spending across all services</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">Today</span>
          <span className="stat-value">${summary.total_cost.toFixed(2)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">This Week</span>
          <span className="stat-value">$23.14</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Requests</span>
          <span className="stat-value">{summary.requests}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Avg Cost</span>
          <span className="stat-value">${summary.avg_cost.toFixed(3)}</span>
        </div>
      </div>

      <div className="card">
        <h3>Breakdown by Service</h3>
        <div className="cost-table">
          {breakdown.map((item, i) => (
            <div key={i} className="cost-row">
              <div className="cost-info">
                <span className="cost-service">{item.service}</span>
                <span className="cost-model">{item.model}</span>
              </div>
              <div className="cost-stats">
                <span className="cost-requests">{item.requests} req</span>
                <span className="cost-amount">${item.cost.toFixed(2)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Cost Limits</h3>
        <div className="limit-item">
          <span>Per Request</span>
          <span>${limits.per_request?.max || '1.00'}</span>
        </div>
        <div className="limit-item">
          <span>Per Hour</span>
          <span>${limits.per_hour?.max || '10.00'}</span>
        </div>
        <div className="limit-item">
          <span>Per Day</span>
          <span>${limits.per_day?.max || '50.00'}</span>
        </div>
      </div>
    </div>
  )
}

export default App
