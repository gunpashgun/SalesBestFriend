/**
 * Trial Class Sales Assistant - Main App
 * 
 * Minimal, clean interface for real-time Zoom trial class coaching.
 * Designed to be unobtrusive during screen sharing.
 * 
 * Layout:
 * - Top: Call timer + Settings button
 * - Left: Stage checklist with timing
 * - Right: Client card
 */

import { useState, useEffect, useRef } from 'react'
import './App_TrialClass.css'
import StageChecklist from './components/StageChecklist'
import CallTimer from './components/CallTimer'
import ClientCard from './components/ClientCard'
import SettingsPanel from './components/SettingsPanel'
import YouTubeDebugPanel from './components/YouTubeDebugPanel'
import DebugLogPanel from './components/DebugLogPanel'

interface Stage {
  id: string
  name: string
  startOffsetSeconds: number
  durationSeconds: number
  items: ChecklistItem[]
  isCurrent: boolean
  timingStatus: 'not_started' | 'on_time' | 'slightly_late' | 'very_late'
  timingMessage: string
}

interface ChecklistItem {
  id: string
  type: 'discuss' | 'say'
  content: string
  completed: boolean
  evidence: string
  extended_description?: string  // Optional: detailed description for LLM
  semantic_keywords?: {  // Optional: for backend use
    required?: string[]
    forbidden?: string[]
  }
}

interface DebugLogEntry {
  timestamp: string
  type: string
  [key: string]: any
}

interface CoachMessage {
  type: 'initial' | 'update'
  callElapsedSeconds: number
  stageElapsedSeconds?: number
  currentStageId: string
  stages: Stage[]
  clientCard: Record<string, string>
  transcriptPreview?: string
  debugLog?: DebugLogEntry[]
}

function App_TrialClass() {
  const [isRecording, setIsRecording] = useState(false)
  const [status, setStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle')
  const [callElapsed, setCallElapsed] = useState(0)
  const [stageElapsed, setStageElapsed] = useState(0)
  const [currentStageId, setCurrentStageId] = useState<string>('')
  const [stages, setStages] = useState<Stage[]>([])
  const [clientCard, setClientCard] = useState<Record<string, string>>({})
  const [showSettings, setShowSettings] = useState(false)
  const [showYouTubeDebug, setShowYouTubeDebug] = useState(false)
  const [showDebugLog, setShowDebugLog] = useState(false)
  const [debugLogs, setDebugLogs] = useState<DebugLogEntry[]>([])
  const [selectedLanguage, setSelectedLanguage] = useState('id')
  
  const ingestWsRef = useRef<WebSocket | null>(null)
  const coachWsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const mediaRecorderRef = useRef<any>(null)
  const callStartTimeRef = useRef<number | null>(null)
  const timerIntervalRef = useRef<number | null>(null)

  // Always use Railway backend in production (Vercel deployment)
  const isProduction = window.location.hostname !== 'localhost'
  const API_WS = isProduction 
    ? 'wss://salesbestfriend-production.up.railway.app'
    : (import.meta.env.VITE_API_WS || 'ws://localhost:8000')

  // Connect WebSockets on mount
  useEffect(() => {
    connectWebSockets()
    return () => {
      if (isRecording) {
        stopRecording()
      }
    }
  }, [])

  // Local ticking timer (updates display every second)
  useEffect(() => {
    if (isRecording && callStartTimeRef.current) {
      // Start local timer
      timerIntervalRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - callStartTimeRef.current!) / 1000)
        setCallElapsed(elapsed)
      }, 1000)
    } else {
      // Stop local timer
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
        timerIntervalRef.current = null
      }
    }

    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
        timerIntervalRef.current = null
      }
    }
  }, [isRecording])

  const connectWebSockets = () => {
    setStatus('connecting')

    // /coach WebSocket for receiving updates
    const coachWs = new WebSocket(`${API_WS}/coach`)
    
    coachWs.onopen = () => {
      console.log('✅ /coach connected')
      setStatus('connected')
      // Send language setting
      coachWs.send(JSON.stringify({ type: 'set_language', language: selectedLanguage }))
    }

    coachWs.onmessage = (e) => {
      try {
        const data: CoachMessage = JSON.parse(e.data)
        console.log('📨 Received update:', data.type)
        
        // Update call start time reference when we get server time
        if (data.callElapsedSeconds > 0) {
          callStartTimeRef.current = Date.now() - (data.callElapsedSeconds * 1000)
        }
        
        setCallElapsed(data.callElapsedSeconds)
        setStageElapsed(data.stageElapsedSeconds || 0)
        setCurrentStageId(data.currentStageId)
        setStages(data.stages)
        setClientCard(data.clientCard)
        
        // Update debug logs if present
        if (data.debugLog) {
          console.log('🐛 Debug logs received:', data.debugLog.length, 'entries')
          if (data.debugLog.length > 0) {
            console.log('Latest log:', data.debugLog[data.debugLog.length - 1])
          }
          setDebugLogs(data.debugLog)
        } else {
          console.log('⚠️ No debugLog in message')
        }
      } catch (err) {
        console.error('❌ Parse error:', err)
      }
    }

    coachWs.onerror = (err) => {
      console.error('❌ /coach error:', err)
      setStatus('error')
    }

    coachWs.onclose = () => {
      console.log('🔌 /coach closed')
      if (status === 'connected') {
        setStatus('idle')
      }
    }

    coachWsRef.current = coachWs

    // /ingest WebSocket for sending audio
    const ingestWs = new WebSocket(`${API_WS}/ingest`)
    
    ingestWs.onopen = () => {
      console.log('✅ /ingest connected')
      ingestWs.send(JSON.stringify({ type: 'set_language', language: selectedLanguage }))
    }

    ingestWs.onerror = (err) => {
      console.error('❌ /ingest error:', err)
    }

    ingestWs.onclose = () => {
      console.log('🔌 /ingest closed')
    }

    ingestWsRef.current = ingestWs
  }

  const startRecording = async () => {
    try {
      setStatus('connecting')
      
      console.log('🎤 Requesting audio capture...')
      
      // Capture audio from Zoom window
      const stream = await navigator.mediaDevices.getDisplayMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        },
        video: true  // Required for Chrome
      })
      
      // Check audio tracks
      const audioTracks = stream.getAudioTracks()
      if (audioTracks.length === 0) {
        stream.getTracks().forEach(track => track.stop())
        throw new Error('No audio track. Please check "Share audio"')
      }

      console.log('✅ Audio stream captured')
      console.log(`   Audio tracks: ${audioTracks.length}`)
      console.log(`   Video tracks: ${stream.getVideoTracks().length}`)
      
      // Keep video tracks alive (Chrome requirement for tab audio)
      // If we stop video, Chrome closes the entire stream including audio!
      
      streamRef.current = stream

      // Handle track end
      audioTracks[0].onended = () => {
        console.log('⏹️ Audio track ended')
        stopRecording()
      }

      // Connect WebSockets if not connected
      if (!ingestWsRef.current || ingestWsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSockets()
      }

      // Web Audio API for PCM conversion
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000  // Whisper requirement
      })
      
      const source = audioContext.createMediaStreamSource(stream)
      const processor = audioContext.createScriptProcessor(4096, 1, 1)
      
      let audioBuffer = new Float32Array(0)
      
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0)
        const newBuffer = new Float32Array(audioBuffer.length + inputData.length)
        newBuffer.set(audioBuffer)
        newBuffer.set(inputData, audioBuffer.length)
        audioBuffer = newBuffer
        
        // Send 8KB chunks
        if (audioBuffer.length >= 8192) {
          const chunk = audioBuffer.slice(0, 8192)
          audioBuffer = audioBuffer.slice(8192)
          
          // Convert Float32 → Int16
          const int16Chunk = new Int16Array(chunk.length)
          for (let i = 0; i < chunk.length; i++) {
            int16Chunk[i] = chunk[i] < 0 
              ? chunk[i] * 0x8000 
              : chunk[i] * 0x7FFF
          }
          
          if (ingestWsRef.current?.readyState === WebSocket.OPEN) {
            ingestWsRef.current.send(int16Chunk.buffer)
          }
        }
      }
      
      source.connect(processor)
      processor.connect(audioContext.destination)
      
      // Save for cleanup
      mediaRecorderRef.current = {
        stop: () => {
          processor.disconnect()
          source.disconnect()
          audioContext.close()
        }
      }

      // Initialize call start time for local timer
      callStartTimeRef.current = Date.now()
      
      setIsRecording(true)
      setStatus('connected')
      
      console.log('🎙️ Recording started')

    } catch (err: any) {
      console.error('❌ Recording error:', err)
      setStatus('error')
      
      let errorMessage = 'Audio capture failed. '
      
      if (err.name === 'NotAllowedError') {
        errorMessage += 'Permission denied. Please allow screen/audio sharing.'
      } else if (err.name === 'NotFoundError') {
        errorMessage += 'No audio source. Check "Share audio" checkbox.'
      } else {
        errorMessage += err.message || 'Please try again.'
      }
      
      alert(errorMessage)
    }
  }

  const stopRecording = () => {
    console.log('⏹️ Stopping recording...')

    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current = null
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }

    // Reset timer
    callStartTimeRef.current = null
    setCallElapsed(0)

    setIsRecording(false)
  }

  const handleManualToggle = (itemId: string) => {
    if (coachWsRef.current?.readyState === WebSocket.OPEN) {
      coachWsRef.current.send(JSON.stringify({
        type: 'manual_toggle_item',
        item_id: itemId
      }))
    }
  }

  // Client card is now automatically filled by AI (read-only)
  // No manual update handler needed

  // Handle config update from Settings
  const handleConfigUpdate = (newStages: any[], newFields: any[]) => {
    // Send updated config to backend via coach WebSocket
    if (coachWsRef.current?.readyState === WebSocket.OPEN) {
      coachWsRef.current.send(JSON.stringify({
        type: 'update_config',
        call_structure: newStages,
        client_fields: newFields
      }))
      console.log('📤 Sent new configuration to backend')
    } else {
      console.warn('⚠️ Coach WebSocket not ready, config will be used on next connection')
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'connected': return '#10b981'
      case 'connecting': return '#f59e0b'
      case 'error': return '#ef4444'
      default: return '#9ca3af'
    }
  }

  return (
    <div className="trial-class-app">
      {/* Top Bar */}
      <div className="top-bar">
        <div className="app-title">
          <h1>Trial Class Assistant</h1>
          <div className="status-indicator" style={{ backgroundColor: getStatusColor() }} />
        </div>
        
        <div className="top-controls">
          <CallTimer elapsedSeconds={callElapsed} />
          
          {!isRecording ? (
            <button className="btn-primary" onClick={startRecording}>
              🎤 Start Session
            </button>
          ) : (
            <button className="btn-danger" onClick={stopRecording}>
              ⏹️ Stop
            </button>
          )}
          
          <button 
            className="btn-settings"
            onClick={() => setShowSettings(true)}
            title="Settings"
          >
            ⚙️
          </button>
          
          <button 
            className="btn-debug"
            onClick={() => setShowYouTubeDebug(!showYouTubeDebug)}
            title="YouTube Debug"
          >
            🎬
          </button>
          
          <button 
            className="btn-debug-log"
            onClick={() => setShowDebugLog(true)}
            title="Debug Log - AI Decisions"
          >
            🐛
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        {/* Left: Stage Checklist */}
        <div className="left-panel">
          <StageChecklist
            stages={stages}
            currentStageId={currentStageId}
            callElapsed={callElapsed}
            stageElapsed={stageElapsed}
            onManualToggle={handleManualToggle}
          />
        </div>

        {/* Right: Client Card */}
        <div className="right-panel">
          <ClientCard
            data={clientCard}
          />
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <SettingsPanel
          onClose={() => setShowSettings(false)}
          selectedLanguage={selectedLanguage}
          onLanguageChange={setSelectedLanguage}
          onConfigUpdate={handleConfigUpdate}
        />
      )}

      {/* YouTube Debug Panel */}
      {showYouTubeDebug && (
        <YouTubeDebugPanel
          selectedLanguage={selectedLanguage}
          onClose={() => setShowYouTubeDebug(false)}
        />
      )}

      {/* Debug Log Panel */}
      <DebugLogPanel
        logs={debugLogs}
        isVisible={showDebugLog}
        onClose={() => setShowDebugLog(false)}
      />

      {/* Instructions (shown when idle) */}
      {!isRecording && status === 'idle' && (
        <div className="instructions-overlay">
          <div className="instructions-content">
            <h2>Getting Started</h2>
            <ol>
              <li>Start your Zoom trial class</li>
              <li>Click "🎤 Start Session" above</li>
              <li>Select the Zoom window</li>
              <li>✅ Check "Share audio"</li>
              <li>Click "Share"</li>
            </ol>
            <p className="note">Use Chrome, Edge, or Brave browser</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default App_TrialClass

