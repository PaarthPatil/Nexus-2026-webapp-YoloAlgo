import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ||
  (API_BASE_URL.startsWith('https://')
    ? API_BASE_URL.replace('https://', 'wss://')
    : API_BASE_URL.replace('http://', 'ws://'))

const NAV_ITEMS = ['Dashboard', 'Sessions', 'History', 'Settings']

const parseProducts = (value) =>
  String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

const formatDuration = (seconds) => {
  const total = Number(seconds || 0)
  const hh = String(Math.floor(total / 3600)).padStart(2, '0')
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

const formatDateTime = (isoText) => {
  if (!isoText) return '-'
  const date = new Date(isoText)
  if (Number.isNaN(date.getTime())) return isoText
  return date.toLocaleString()
}

function App() {
  const [activeNav, setActiveNav] = useState('Dashboard')

  const [operatorId, setOperatorId] = useState('')
  const [batchId, setBatchId] = useState('')
  const [videoSource, setVideoSource] = useState('')
  const [modelPath, setModelPath] = useState('box_detection.pt')
  const [countMode, setCountMode] = useState('roi_current')
  const [yolov5RepoPath, setYolov5RepoPath] = useState('D:\\Nexus\\yolov5')
  const [confThreshold, setConfThreshold] = useState('0.50')
  const [iouThreshold, setIouThreshold] = useState('0.65')
  const [roiPadding, setRoiPadding] = useState('5')
  const [roiLabelKeyword, setRoiLabelKeyword] = useState('bigger')
  const [smallLabelKeyword, setSmallLabelKeyword] = useState('box')
  const [productsInput, setProductsInput] = useState('')
  const [addProductsInput, setAddProductsInput] = useState('')
  const [challanProductsInput, setChallanProductsInput] = useState('')

  const [isRunning, setIsRunning] = useState(false)
  const [count, setCount] = useState(0)
  const [fps, setFps] = useState(0)
  const [confidence, setConfidence] = useState(0)
  const [sessionDuration, setSessionDuration] = useState(0)
  const [sessionProducts, setSessionProducts] = useState([])
  const [productCounts, setProductCounts] = useState({})
  const [imageSrc, setImageSrc] = useState('')

  const [sessions, setSessions] = useState([])
  const [stats, setStats] = useState(null)
  const [historyFilters, setHistoryFilters] = useState({
    search: '',
    operator_id: '',
    product_name: '',
    date_from: '',
    date_to: ''
  })
  const [historyOptions, setHistoryOptions] = useState({ operators: [], products: [] })
  const [rowSelectedProducts, setRowSelectedProducts] = useState({})
  const [selectedSessionIds, setSelectedSessionIds] = useState([])
  const [lastSessionId, setLastSessionId] = useState(null)

  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const wsRef = useRef(null)

  const parseError = async (res, fallback) => {
    let detail = fallback
    try {
      const data = await res.json()
      if (data?.detail) detail = data.detail
    } catch (_) {
      const text = await res.text()
      if (text) detail = text
    }
    return detail
  }

  const closeWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/dashboard/stats`)
      if (!res.ok) throw new Error(await parseError(res, `Stats failed (${res.status})`))
      const data = await res.json()
      setStats(data.stats || null)
    } catch (err) {
      setError(err.message || 'Failed to fetch dashboard stats')
    }
  }, [])

  const fetchHistoryOptions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/sessions/history/filters`)
      if (!res.ok) return
      const data = await res.json()
      setHistoryOptions({
        operators: data.operators || [],
        products: data.products || []
      })
    } catch (_) {
      // no-op
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      Object.entries(historyFilters).forEach(([key, value]) => {
        if (value) params.set(key, value)
      })
      const query = params.toString()
      const res = await fetch(
        `${API_BASE_URL}/api/sessions/history/detailed${query ? `?${query}` : ''}`
      )
      if (!res.ok) throw new Error(await parseError(res, `History failed (${res.status})`))
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (err) {
      setError(err.message || 'Failed to fetch session history')
    }
  }, [historyFilters])

  const fetchCurrentSession = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/sessions/current`)
      if (!res.ok) return
      const data = await res.json()
      const session = data.session || {}
      setIsRunning(Boolean(session.is_running))
      setCount(Number(session.count || 0))
      setFps(Number(session.fps || 0))
      setConfidence(Number(session.detection_confidence || 0))
      setSessionDuration(Number(session.duration_seconds || 0))
      setProductCounts(session.product_counts || {})
      setSessionProducts(session.products || [])
      if (session.operator_id) setOperatorId(session.operator_id)
      if (session.batch_id) setBatchId(session.batch_id)
    } catch (_) {
      // no-op
    }
  }, [])

  const connectWebSocket = useCallback(() => {
    closeWebSocket()
    const ws = new WebSocket(`${WS_BASE_URL}/ws/live-feed`)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.frame) setImageSrc(`data:image/jpeg;base64,${data.frame}`)
        if (data.count !== undefined) setCount(Number(data.count || 0))
        if (data.product_counts) setProductCounts(data.product_counts)
        if (data.fps !== undefined) setFps(Number(data.fps || 0))
        if (data.detection_confidence !== undefined) setConfidence(Number(data.detection_confidence || 0))
        if (data.duration_seconds !== undefined) setSessionDuration(Number(data.duration_seconds || 0))
        if (data.is_running !== undefined) setIsRunning(Boolean(data.is_running))
      } catch (_) {
        // no-op
      }
    }

    ws.onclose = () => {
      setIsRunning(false)
    }

    wsRef.current = ws
  }, [closeWebSocket])

  useEffect(() => {
    fetchStats()
    fetchHistory()
    fetchHistoryOptions()
    fetchCurrentSession()
    const timer = setInterval(fetchCurrentSession, 1000)
    return () => {
      clearInterval(timer)
      closeWebSocket()
    }
  }, [closeWebSocket, fetchCurrentSession, fetchHistory, fetchHistoryOptions, fetchStats])

  useEffect(() => {
    const timeout = setTimeout(() => {
      fetchHistory()
    }, 250)
    return () => clearTimeout(timeout)
  }, [fetchHistory])

  useEffect(() => {
    if (isRunning) connectWebSocket()
    else closeWebSocket()
  }, [connectWebSocket, closeWebSocket, isRunning])

  const startSession = async () => {
    setError('')
    setStatus('')
    if (!videoSource.trim()) {
      setError('Video source is required before starting session.')
      return
    }
    const parsedProducts = parseProducts(productsInput)
    try {
      const res = await fetch(`${API_BASE_URL}/api/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operator_id: operatorId,
          batch_id: batchId,
          video_source: videoSource,
          model_path: modelPath,
          count_mode: countMode,
          yolov5_repo_path: yolov5RepoPath || null,
          conf_threshold: countMode === 'roi_current' ? Number(confThreshold) : null,
          iou_threshold: countMode === 'roi_current' ? Number(iouThreshold) : null,
          roi_padding: countMode === 'roi_current' ? Number(roiPadding) : null,
          roi_label_keyword: countMode === 'roi_current' ? roiLabelKeyword : null,
          small_label_keyword: countMode === 'roi_current' ? smallLabelKeyword : null,
          product_type: parsedProducts[0] || null,
          products: parsedProducts
        })
      })
      if (!res.ok) throw new Error(await parseError(res, `Failed to start session (${res.status})`))
      const data = await res.json()
      setSessionProducts(data.products || parsedProducts)
      setCount(0)
      setProductCounts({})
      setSessionDuration(0)
      setIsRunning(true)
      setStatus('Session started')
      setActiveNav('Dashboard')
      await Promise.all([fetchStats(), fetchHistory(), fetchHistoryOptions()])
    } catch (err) {
      setError(err.message || 'Failed to start session')
    }
  }

  const stopSession = async () => {
    setError('')
    setStatus('')
    const selected = parseProducts(challanProductsInput)
    try {
      const res = await fetch(`${API_BASE_URL}/api/sessions/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operator_id: operatorId,
          batch_id: batchId,
          final_count: count,
          challan_products: selected.length ? selected : null
        })
      })
      if (!res.ok) throw new Error(await parseError(res, `Failed to stop session (${res.status})`))
      const data = await res.json()
      setStatus(`Session stopped. Final count: ${data.final_count}`)
      setLastSessionId(data.session_id)
      setIsRunning(false)
      setImageSrc('')
      await Promise.all([fetchStats(), fetchHistory(), fetchHistoryOptions(), fetchCurrentSession()])
      if (data.challan_file) {
        window.open(`${API_BASE_URL}/api/challans/files/${encodeURIComponent(data.challan_file)}`, '_blank')
      } else if (data.session_id) {
        window.open(`${API_BASE_URL}/api/challans/${data.session_id}`, '_blank')
      }
    } catch (err) {
      setError(err.message || 'Failed to stop session')
    }
  }

  const addProductsToActiveSession = async () => {
    const parsed = parseProducts(addProductsInput)
    if (!parsed.length) {
      setError('Enter at least one product to add.')
      return
    }
    setError('')
    try {
      const res = await fetch(`${API_BASE_URL}/api/sessions/products`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ products: parsed })
      })
      if (!res.ok) throw new Error(await parseError(res, `Failed to add products (${res.status})`))
      const data = await res.json()
      setSessionProducts(data.products || [])
      setAddProductsInput('')
      setStatus('Products updated for active session')
    } catch (err) {
      setError(err.message || 'Failed to add products')
    }
  }

  const generateChallan = async (sessionId, productsText = '') => {
    setError('')
    const parsed = parseProducts(productsText)
    const payload = { session_id: sessionId }
    if (productsText.trim()) payload.products = parsed

    try {
      const res = await fetch(`${API_BASE_URL}/api/challans/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!res.ok) throw new Error(await parseError(res, `Failed challan generation (${res.status})`))
      const data = await res.json()
      if (data.challan_file) {
        window.open(`${API_BASE_URL}/api/challans/files/${encodeURIComponent(data.challan_file)}`, '_blank')
      } else {
        window.open(`${API_BASE_URL}/api/challans/${sessionId}`, '_blank')
      }
      setStatus(`Challan generated for session ${sessionId}`)
    } catch (err) {
      setError(err.message || 'Failed to generate challan')
    }
  }

  const generateForSelected = async () => {
    if (!selectedSessionIds.length) {
      setError('Select at least one history row.')
      return
    }
    setError('')
    try {
      await Promise.all(
        selectedSessionIds.map((id) => generateChallan(id, rowSelectedProducts[id] || ''))
      )
      setStatus(`Generated challans for ${selectedSessionIds.length} session(s).`)
    } catch (_) {
      // errors are handled in generateChallan
    }
  }

  const toggleSessionSelection = (sessionId) => {
    setSelectedSessionIds((prev) =>
      prev.includes(sessionId) ? prev.filter((id) => id !== sessionId) : [...prev, sessionId]
    )
  }

  const productRows = useMemo(
    () => Object.entries(productCounts).sort((a, b) => b[1] - a[1]),
    [productCounts]
  )

  const renderDashboard = () => (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <section className="xl:col-span-12 grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard title="Total Sessions" value={stats?.total_sessions ?? 0} accent="text-cyan-300" />
        <MetricCard title="Total Count" value={stats?.total_count ?? 0} accent="text-emerald-300" />
        <MetricCard title="Today Sessions" value={stats?.today_sessions ?? 0} accent="text-indigo-300" />
        <MetricCard title="Latest Session" value={formatDateTime(stats?.latest_timestamp)} accent="text-amber-300" />
      </section>

      <section className="xl:col-span-8 rounded-xl border border-slate-800 bg-slate-900/80 p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold tracking-wide text-cyan-300">Live Inspection Feed</h2>
          <span className="text-xs px-2 py-1 rounded bg-slate-800 text-slate-300">
            {isRunning ? 'LIVE' : 'IDLE'}
          </span>
        </div>
        <div className="aspect-video rounded-lg border border-slate-800 bg-slate-950 flex items-center justify-center overflow-hidden">
          {imageSrc ? (
            <img src={imageSrc} alt="Live Feed" className="w-full h-full object-contain" />
          ) : (
            <p className="text-slate-500 text-sm">Waiting for live stream...</p>
          )}
        </div>
      </section>

      <section className="xl:col-span-4 rounded-xl border border-slate-800 bg-slate-900/80 p-4">
        <h2 className="text-lg font-semibold tracking-wide text-cyan-300 mb-3">Live Analytics</h2>
        <div className="grid grid-cols-2 gap-3">
          <MetricCard title="Current Count" value={count} accent="text-cyan-300" />
          <MetricCard title="FPS" value={fps.toFixed(1)} accent="text-green-300" />
          <MetricCard title="Confidence" value={`${(confidence * 100).toFixed(1)}%`} accent="text-amber-300" />
          <MetricCard title="Duration" value={formatDuration(sessionDuration)} accent="text-indigo-300" />
        </div>
        <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/70 p-3">
          <h3 className="text-sm uppercase tracking-wider text-slate-300 mb-2">Product-wise Count</h3>
          <div className="max-h-44 overflow-y-auto pr-1 space-y-1">
            {productRows.length ? (
              productRows.map(([name, value]) => (
                <div key={name} className="flex items-center justify-between rounded bg-slate-900 px-2 py-1">
                  <span className="text-sm text-slate-200">{name}</span>
                  <span className="text-sm font-semibold text-cyan-300">{value}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500">No product detections yet.</p>
            )}
          </div>
        </div>
      </section>

      <section className="xl:col-span-12 rounded-xl border border-slate-800 bg-slate-900/80 p-4">
        <h2 className="text-lg font-semibold tracking-wide text-cyan-300 mb-3">Session Control Console</h2>
        <SessionControl
          operatorId={operatorId}
          setOperatorId={setOperatorId}
          batchId={batchId}
          setBatchId={setBatchId}
          videoSource={videoSource}
          setVideoSource={setVideoSource}
          modelPath={modelPath}
          setModelPath={setModelPath}
          countMode={countMode}
          setCountMode={setCountMode}
          yolov5RepoPath={yolov5RepoPath}
          setYolov5RepoPath={setYolov5RepoPath}
          confThreshold={confThreshold}
          setConfThreshold={setConfThreshold}
          iouThreshold={iouThreshold}
          setIouThreshold={setIouThreshold}
          roiPadding={roiPadding}
          setRoiPadding={setRoiPadding}
          roiLabelKeyword={roiLabelKeyword}
          setRoiLabelKeyword={setRoiLabelKeyword}
          smallLabelKeyword={smallLabelKeyword}
          setSmallLabelKeyword={setSmallLabelKeyword}
          productsInput={productsInput}
          setProductsInput={setProductsInput}
          addProductsInput={addProductsInput}
          setAddProductsInput={setAddProductsInput}
          challanProductsInput={challanProductsInput}
          setChallanProductsInput={setChallanProductsInput}
          isRunning={isRunning}
          startSession={startSession}
          stopSession={stopSession}
          addProductsToActiveSession={addProductsToActiveSession}
          sessionProducts={sessionProducts}
        />
      </section>
    </div>
  )

  const renderHistory = () => (
    <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="flex flex-wrap items-end gap-2 mb-4">
        <input
          type="text"
          placeholder="Search session/operator/batch"
          value={historyFilters.search}
          onChange={(e) => setHistoryFilters((prev) => ({ ...prev, search: e.target.value }))}
          className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm min-w-[220px]"
        />
        <select
          value={historyFilters.operator_id}
          onChange={(e) => setHistoryFilters((prev) => ({ ...prev, operator_id: e.target.value }))}
          className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm"
        >
          <option value="">All Operators</option>
          {historyOptions.operators.map((operator) => (
            <option key={operator} value={operator}>
              {operator}
            </option>
          ))}
        </select>
        <select
          value={historyFilters.product_name}
          onChange={(e) => setHistoryFilters((prev) => ({ ...prev, product_name: e.target.value }))}
          className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm"
        >
          <option value="">All Products</option>
          {historyOptions.products.map((product) => (
            <option key={product} value={product}>
              {product}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={historyFilters.date_from}
          onChange={(e) => setHistoryFilters((prev) => ({ ...prev, date_from: e.target.value }))}
          className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm"
        />
        <input
          type="date"
          value={historyFilters.date_to}
          onChange={(e) => setHistoryFilters((prev) => ({ ...prev, date_to: e.target.value }))}
          className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm"
        />
        <button onClick={generateForSelected} className="bg-cyan-700 hover:bg-cyan-600 px-3 py-2 rounded text-sm">
          Generate Challans (Selected)
        </button>
      </div>

      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-300 bg-slate-950">
            <tr>
              <th className="text-left p-2">Select</th>
              <th className="text-left p-2">Session</th>
              <th className="text-left p-2">Operator</th>
              <th className="text-left p-2">Batch</th>
              <th className="text-left p-2">Products</th>
              <th className="text-left p-2">Total</th>
              <th className="text-left p-2">Timestamp</th>
              <th className="text-left p-2">Challan Products</th>
              <th className="text-left p-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {sessions.length ? (
              sessions.map((session) => (
                <tr key={session.id} className="border-b border-slate-800">
                  <td className="p-2">
                    <input
                      type="checkbox"
                      checked={selectedSessionIds.includes(session.id)}
                      onChange={() => toggleSessionSelection(session.id)}
                    />
                  </td>
                  <td className="p-2">{session.id}</td>
                  <td className="p-2">{session.operator_id || '-'}</td>
                  <td className="p-2">{session.batch_id || '-'}</td>
                  <td className="p-2 text-slate-300">{session.products_label || '-'}</td>
                  <td className="p-2">{session.final_count}</td>
                  <td className="p-2">{formatDateTime(session.timestamp)}</td>
                  <td className="p-2">
                    <input
                      type="text"
                      placeholder="ABC,XYZ"
                      value={rowSelectedProducts[session.id] || ''}
                      onChange={(e) =>
                        setRowSelectedProducts((prev) => ({ ...prev, [session.id]: e.target.value }))
                      }
                      className="bg-slate-950 border border-slate-800 rounded px-2 py-1 w-40"
                    />
                  </td>
                  <td className="p-2">
                    <button
                      onClick={() => generateChallan(session.id, rowSelectedProducts[session.id] || '')}
                      className="bg-cyan-700 hover:bg-cyan-600 px-2 py-1 rounded"
                    >
                      Generate
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={9} className="p-4 text-slate-500">
                  No sessions match the selected filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )

  return (
    <div className="min-h-screen bg-[#0b1220] text-slate-100 flex">
      <aside className="w-64 border-r border-slate-800 bg-slate-950/90 p-4">
        <div className="mb-6">
          <h1 className="text-2xl font-bold tracking-wider text-cyan-300">NexusTrace</h1>
          <p className="text-xs text-slate-400 mt-1">Warehouse Audit Console</p>
        </div>
        <nav className="space-y-2">
          {NAV_ITEMS.map((item) => (
            <button
              key={item}
              onClick={() => setActiveNav(item)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
                activeNav === item
                  ? 'bg-cyan-700/60 text-white'
                  : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
              }`}
            >
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex-1 flex flex-col">
        <header className="border-b border-slate-800 bg-slate-900/80 px-5 py-3 flex flex-wrap items-center gap-3">
          <div className="text-sm text-slate-300">
            Operator: <span className="text-white">{operatorId || '-'}</span>
          </div>
          <div className="text-sm text-slate-300">
            Batch: <span className="text-white">{batchId || '-'}</span>
          </div>
          <div className="text-sm text-slate-300">
            Status:{' '}
            <span className={isRunning ? 'text-emerald-300 font-semibold' : 'text-slate-300'}>
              {isRunning ? 'Running' : 'Idle'}
            </span>
          </div>
          <div className="text-sm text-slate-300">
            Duration: <span className="text-white">{formatDuration(sessionDuration)}</span>
          </div>
          {lastSessionId ? (
            <button
              onClick={() => window.open(`${API_BASE_URL}/api/challans/${lastSessionId}`, '_blank')}
              className="ml-auto bg-indigo-700 hover:bg-indigo-600 px-3 py-1.5 rounded text-sm"
            >
              Open Latest Challan
            </button>
          ) : null}
        </header>

        <div className="p-4 space-y-4">
          {status ? <div className="rounded border border-emerald-700 bg-emerald-950/50 px-3 py-2 text-sm">{status}</div> : null}
          {error ? <div className="rounded border border-red-700 bg-red-950/50 px-3 py-2 text-sm">{error}</div> : null}

          {(activeNav === 'Dashboard' || activeNav === 'Sessions') && renderDashboard()}
          {activeNav === 'History' && renderHistory()}
          {activeNav === 'Settings' && (
            <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
              <h2 className="text-lg font-semibold tracking-wide text-cyan-300 mb-3">System Settings</h2>
              <p className="text-sm text-slate-300 mb-3">
                Configure detection profile parameters before starting a new session.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <Input label="Model Path" value={modelPath} onChange={setModelPath} />
                <Input label="YOLOv5 Repo" value={yolov5RepoPath} onChange={setYolov5RepoPath} />
                <Input label="Conf Threshold" value={confThreshold} onChange={setConfThreshold} />
                <Input label="IOU Threshold" value={iouThreshold} onChange={setIouThreshold} />
                <Input label="ROI Padding" value={roiPadding} onChange={setRoiPadding} />
                <Input label="ROI Keyword" value={roiLabelKeyword} onChange={setRoiLabelKeyword} />
                <Input label="Small Label Keyword" value={smallLabelKeyword} onChange={setSmallLabelKeyword} />
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  )
}

function MetricCard({ title, value, accent }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <p className={`text-xl font-semibold mt-1 ${accent}`}>{value}</p>
    </div>
  )
}

function Input({ label, value, onChange }) {
  return (
    <label className="block">
      <span className="text-xs text-slate-400 uppercase tracking-wide">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm"
      />
    </label>
  )
}

function SessionControl(props) {
  const {
    operatorId,
    setOperatorId,
    batchId,
    setBatchId,
    videoSource,
    setVideoSource,
    modelPath,
    setModelPath,
    countMode,
    setCountMode,
    yolov5RepoPath,
    setYolov5RepoPath,
    confThreshold,
    setConfThreshold,
    iouThreshold,
    setIouThreshold,
    roiPadding,
    setRoiPadding,
    roiLabelKeyword,
    setRoiLabelKeyword,
    smallLabelKeyword,
    setSmallLabelKeyword,
    productsInput,
    setProductsInput,
    addProductsInput,
    setAddProductsInput,
    challanProductsInput,
    setChallanProductsInput,
    isRunning,
    startSession,
    stopSession,
    addProductsToActiveSession,
    sessionProducts
  } = props

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
      <div className="space-y-3">
        <Input label="Operator ID" value={operatorId} onChange={setOperatorId} />
        <Input label="Batch ID" value={batchId} onChange={setBatchId} />
        <Input label="Video Source" value={videoSource} onChange={setVideoSource} />
        <Input label="Products (comma separated)" value={productsInput} onChange={setProductsInput} />
      </div>

      <div className="space-y-3">
        <Input label="Model Path" value={modelPath} onChange={setModelPath} />
        <label className="block">
          <span className="text-xs text-slate-400 uppercase tracking-wide">Count Mode</span>
          <select
            value={countMode}
            onChange={(e) => setCountMode(e.target.value)}
            className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-sm"
          >
            <option value="roi_current">ROI Current Count</option>
            <option value="track_unique">Tracking Mode</option>
          </select>
        </label>
        {countMode === 'roi_current' ? (
          <>
            <Input label="YOLOv5 Repo Path" value={yolov5RepoPath} onChange={setYolov5RepoPath} />
            <div className="grid grid-cols-3 gap-2">
              <Input label="Conf" value={confThreshold} onChange={setConfThreshold} />
              <Input label="IOU" value={iouThreshold} onChange={setIouThreshold} />
              <Input label="Padding" value={roiPadding} onChange={setRoiPadding} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input label="ROI Label" value={roiLabelKeyword} onChange={setRoiLabelKeyword} />
              <Input label="Small Label" value={smallLabelKeyword} onChange={setSmallLabelKeyword} />
            </div>
          </>
        ) : null}
      </div>

      <div className="space-y-3">
        <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Session Products</p>
          <div className="min-h-16 text-sm text-slate-200">
            {sessionProducts.length ? sessionProducts.join(', ') : 'All detected classes'}
          </div>
          <Input label="Add Products Live" value={addProductsInput} onChange={setAddProductsInput} />
          <button
            onClick={addProductsToActiveSession}
            disabled={!isRunning}
            className="mt-2 w-full bg-indigo-700 hover:bg-indigo-600 disabled:opacity-40 px-3 py-2 rounded"
          >
            Add to Running Session
          </button>
        </div>

        <Input
          label="Challan Products On Stop (optional)"
          value={challanProductsInput}
          onChange={setChallanProductsInput}
        />

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={startSession}
            disabled={isRunning}
            className="bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 px-3 py-2 rounded"
          >
            Start Session
          </button>
          <button
            onClick={stopSession}
            disabled={!isRunning}
            className="bg-red-700 hover:bg-red-600 disabled:opacity-40 px-3 py-2 rounded"
          >
            Stop Session
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
