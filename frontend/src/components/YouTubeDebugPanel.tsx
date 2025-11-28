/**
 * YouTube Debug Panel
 * 
 * For debugging: paste YouTube URL with sales call recording
 * and analyze it without live recording
 */

import { useState } from 'react'
import './YouTubeDebugPanel.css'

interface YouTubeDebugPanelProps {
  selectedLanguage: string
  onClose: () => void
}

interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export default function YouTubeDebugPanel({ selectedLanguage, onClose }: YouTubeDebugPanelProps) {
  const [url, setUrl] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [status, setStatus] = useState<'idle' | 'processing' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [transcriptSegments, setTranscriptSegments] = useState<TranscriptSegment[]>([])

  const handleTimestampClick = (seconds: number) => {
    if (!url) return;
    const videoUrl = new URL(url);
    videoUrl.searchParams.set('t', `${Math.floor(seconds)}s`);
    window.open(videoUrl.toString(), '_blank');
  };

  // Always use Railway backend in production (Vercel deployment)
  const isProduction = window.location.hostname !== 'localhost'
  const API_HTTP = isProduction 
    ? 'https://salesbestfriend-production.up.railway.app'
    : (import.meta.env.VITE_API_HTTP || 'http://localhost:8000')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!url.trim()) {
      setStatus('error')
      setMessage('Please enter a YouTube URL')
      return
    }

    setIsProcessing(true)
    setStatus('processing')
    setMessage('Downloading and transcribing video...')
    setTranscriptSegments([])

    try {
      console.log('🔍 Connecting to backend:', API_HTTP)
      console.log('📤 Sending YouTube URL:', url)
      
      const formData = new FormData()
      formData.append('url', url)
      formData.append('language', selectedLanguage)

      const response = await fetch(`${API_HTTP}/api/process-youtube`, {
        method: 'POST',
        body: formData
      })

      console.log('📡 Response status:', response.status, response.statusText)

      // Check if response is OK
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Backend error (${response.status}): ${errorText.substring(0, 200)}`)
      }

      const data = await response.json()
      console.log('📦 Response data:', data)

      if (data.success) {
        setStatus('success')
        setMessage(
          `✅ Analysis complete!\n` +
          `Transcript: ${data.transcriptLength} chars\n` +
          `Stage: ${data.currentStage}\n` +
          `Completed: ${data.itemsCompleted}/${data.totalItems} items\n` +
          `Client info: ${data.clientCardFields} fields filled`
        )
        setTranscriptSegments(data.transcript_segments || [])
        
        // Clear URL after 2 seconds
        setTimeout(() => {
          setUrl('')
        }, 2000)
      } else {
        setStatus('error')
        setMessage(`❌ Error: ${data.error}`)
      }
    } catch (err: any) {
      console.error('❌ YouTube processing error:', err)
      setStatus('error')
      setMessage(
        `❌ Error: ${err.message || 'Failed to connect'}\n\n` +
        `Backend URL: ${API_HTTP}\n` +
        `Is the backend running? Check console for details.`
      )
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="youtube-debug-panel">
      <div className="debug-header">
        <div className="debug-title">
          <span className="debug-icon">🎬</span>
          <h3>YouTube Debug</h3>
        </div>
        <button className="close-debug-btn" onClick={onClose}>✕</button>
      </div>

      <form className="debug-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">
            YouTube URL (sales call recording)
          </label>
          <input
            type="text"
            className="form-input"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            disabled={isProcessing}
          />
        </div>

        <div className="form-actions">
          <button 
            type="submit" 
            className="btn-analyze"
            disabled={isProcessing || !url.trim()}
          >
            {isProcessing ? '⏳ Processing...' : '🔍 Analyze Video'}
          </button>
          
          <span className="language-badge">
            Language: {selectedLanguage.toUpperCase()}
          </span>
        </div>
      </form>

      {status !== 'idle' && (
        <div className={`status-message status-${status}`}>
          <pre>{message}</pre>
        </div>
      )}

      <div className="debug-info">
        <p className="info-text">
          ℹ️ Paste a YouTube URL with a recorded sales call. 
          The system will download, transcribe, and analyze it.
        </p>
        <p className="info-note">
          Note: Processing may take 1-2 minutes depending on video length.
        </p>
      </div>

      {transcriptSegments.length > 0 && (
        <div className="transcript-section">
          <h4>Full Transcript</h4>
          <div className="transcript-content">
            {transcriptSegments.map((segment, index) => (
              <p key={index}>
                <span
                  className="timestamp"
                  onClick={() => handleTimestampClick(segment.start)}
                >
                  [{formatTimestamp(segment.start)}]
                </span>
                {segment.text}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return h === '00' ? `${m}:${s}` : `${h}:${m}:${s}`;
}
