import { useCallback, useEffect, useRef, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ||
  (API_BASE_URL.startsWith('https://')
    ? API_BASE_URL.replace('https://', 'wss://')
    : API_BASE_URL.replace('http://', 'ws://'))

function App() {
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

  const [isRunning, setIsRunning] = useState(false)
  const [count, setCount] = useState(0)
  const [imageSrc, setImageSrc] = useState('')
  const [sessions, setSessions] = useState([])
  const [stats, setStats] = useState(null)
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

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/sessions/history`)
      if (!res.ok) {
        throw new Error(await parseError(res, `History request failed (${res.status})`))
      }
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (err) {
      setError(err.message || 'Failed to load session history')
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/dashboard/stats`)
      if (!res.ok) {
        throw new Error(await parseError(res, `Stats request failed (${res.status})`))
      }
      const data = await res.json()
      setStats(data.stats || null)
    } catch (err) {
      setError(err.message || 'Failed to load dashboard stats')
    }
  }, [])

  useEffect(() => {
    fetchHistory()
    fetchStats()
    return () => {
      closeWebSocket()
    }
  }, [closeWebSocket, fetchHistory, fetchStats])

  const connectWebSocket = () => {
    closeWebSocket()
    const ws = new WebSocket(`${WS_BASE_URL}/ws/live-feed`)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.frame) {
          setImageSrc(`data:image/jpeg;base64,${data.frame}`)
        }
        if (data.count !== undefined) {
          setCount(data.count)
        }
      } catch (e) {
        console.warn('WS parse error:', e)
      }
    }

    ws.onclose = () => {
      setIsRunning(false)
    }

    wsRef.current = ws
  }

  const startSession = async () => {
    setError('')
    setStatus('')

    if (!videoSource) {
      setError('Please enter a video source path/URL before starting session.')
      return
    }

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
          small_label_keyword: countMode === 'roi_current' ? smallLabelKeyword : null
        })
      })

      if (!res.ok) {
        throw new Error(await parseError(res, `Failed to start session (${res.status})`))
      }

      setIsRunning(true)
      setCount(0)
      setStatus('Session started')
      connectWebSocket()
    } catch (err) {
      setError(err.message || 'Failed to start session')
    }
  }

  const stopSession = async () => {
    setError('')
    setStatus('')

    try {
      const res = await fetch(`${API_BASE_URL}/api/sessions/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operator_id: operatorId, batch_id: batchId, final_count: count })
      })

      if (!res.ok) {
        throw new Error(await parseError(res, `Failed to stop session (${res.status})`))
      }

      const data = await res.json()
      setStatus(`Session stopped. Final count: ${data.final_count}`)
      await Promise.all([fetchHistory(), fetchStats()])
      return data
    } catch (err) {
      setError(err.message || 'Failed to stop session')
      return null
    } finally {
      setIsRunning(false)
      setImageSrc('')
      closeWebSocket()
    }
  }

  const downloadChallan = (sessionId) => {
    window.open(`${API_BASE_URL}/api/challans/${sessionId}`, '_blank')
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white p-4">
      <h1 className="text-3xl font-bold text-center mb-8 text-cyan-400">NexusTrace</h1>

      <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-slate-800 p-4 rounded-lg">
          <p className="text-sm text-slate-300">Total Sessions</p>
          <p className="text-2xl text-cyan-400">{stats?.total_sessions ?? 0}</p>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg">
          <p className="text-sm text-slate-300">Total Count</p>
          <p className="text-2xl text-cyan-400">{stats?.total_count ?? 0}</p>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg">
          <p className="text-sm text-slate-300">Today Sessions</p>
          <p className="text-2xl text-cyan-400">{stats?.today_sessions ?? 0}</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
          <div className="bg-slate-800 p-6 rounded-lg mb-6">
            <h2 className="text-xl mb-4">Start Session</h2>
            <input
              type="text"
              placeholder="Operator ID"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              className="w-full p-2 mb-2 bg-slate-700 rounded"
            />
            <input
              type="text"
              placeholder="Batch ID"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              className="w-full p-2 mb-2 bg-slate-700 rounded"
            />
            <input
              type="text"
              placeholder="Video Source path or URL"
              value={videoSource}
              onChange={(e) => setVideoSource(e.target.value)}
              className="w-full p-2 mb-2 bg-slate-700 rounded"
            />
            <input
              type="text"
              placeholder="Model path (e.g., box_detection.pt)"
              value={modelPath}
              onChange={(e) => setModelPath(e.target.value)}
              className="w-full p-2 mb-2 bg-slate-700 rounded"
            />
            <select
              value={countMode}
              onChange={(e) => setCountMode(e.target.value)}
              className="w-full p-2 mb-2 bg-slate-700 rounded"
            >
              <option value="roi_current">ROI Current Count (run_yolo4 style)</option>
              <option value="track_unique">Tracking Mode</option>
            </select>

            {countMode === 'roi_current' ? (
              <>
                <input
                  type="text"
                  placeholder="YOLOv5 repo path (e.g., D:\\Nexus\\yolov5)"
                  value={yolov5RepoPath}
                  onChange={(e) => setYolov5RepoPath(e.target.value)}
                  className="w-full p-2 mb-2 bg-slate-700 rounded"
                />
                <div className="grid grid-cols-3 gap-2 mb-2">
                  <input
                    type="number"
                    step="0.01"
                    value={confThreshold}
                    onChange={(e) => setConfThreshold(e.target.value)}
                    className="w-full p-2 bg-slate-700 rounded"
                    placeholder="Conf"
                  />
                  <input
                    type="number"
                    step="0.01"
                    value={iouThreshold}
                    onChange={(e) => setIouThreshold(e.target.value)}
                    className="w-full p-2 bg-slate-700 rounded"
                    placeholder="IOU"
                  />
                  <input
                    type="number"
                    step="1"
                    value={roiPadding}
                    onChange={(e) => setRoiPadding(e.target.value)}
                    className="w-full p-2 bg-slate-700 rounded"
                    placeholder="ROI Padding"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2 mb-4">
                  <input
                    type="text"
                    value={roiLabelKeyword}
                    onChange={(e) => setRoiLabelKeyword(e.target.value)}
                    className="w-full p-2 bg-slate-700 rounded"
                    placeholder="ROI keyword"
                  />
                  <input
                    type="text"
                    value={smallLabelKeyword}
                    onChange={(e) => setSmallLabelKeyword(e.target.value)}
                    className="w-full p-2 bg-slate-700 rounded"
                    placeholder="Small box keyword"
                  />
                </div>
              </>
            ) : (
              <div className="mb-4 text-xs text-slate-300">
                Final saved count uses stable final-check logic (median of recent frames).
              </div>
            )}

            {status ? <p className="mb-2 text-green-300">{status}</p> : null}
            {error ? <p className="mb-2 text-red-300">{error}</p> : null}

            <button
              onClick={isRunning ? stopSession : startSession}
              className={`w-full p-2 rounded ${isRunning ? 'bg-red-600' : 'bg-green-600'}`}
            >
              {isRunning ? 'Stop Session' : 'Start Session'}
            </button>
          </div>

          <div className="bg-slate-800 p-6 rounded-lg">
            <h2 className="text-xl mb-4">Live Feed</h2>
            {imageSrc && <img src={imageSrc} alt="Live Feed" className="w-full" />}
            {isRunning && <p className="mt-2 text-cyan-400">Processing...</p>}
          </div>
        </div>

        <div>
          <div className="bg-slate-800 p-6 rounded-lg mb-6">
            <h2 className="text-xl mb-4">Real-time Count</h2>
            <p className="text-4xl text-cyan-400">{count}</p>
          </div>

          <div className="bg-slate-800 p-6 rounded-lg">
            <h2 className="text-xl mb-4">Session History</h2>
            <table className="w-full">
              <thead>
                <tr>
                  <th className="text-left">ID</th>
                  <th className="text-left">Operator</th>
                  <th className="text-left">Batch</th>
                  <th className="text-left">Count</th>
                  <th className="text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {sessions.length > 0 ? (
                  sessions.map((session) => (
                    <tr key={session[0]}>
                      <td>{session[0]}</td>
                      <td>{session[2]}</td>
                      <td>{session[3]}</td>
                      <td>{session[4]}</td>
                      <td>
                        <button
                          onClick={() => downloadChallan(session[0])}
                          className="bg-cyan-600 p-1 rounded text-sm"
                        >
                          Download
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="text-slate-400 pt-2">
                      No sessions yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
