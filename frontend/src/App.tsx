import { useState, useEffect, useRef } from 'react'
import './App.css'
import NextStepCard from './components/NextStepCard'
import ClientInfoSummary from './components/ClientInfoSummary'
import CallChecklist from './components/CallChecklist'
import DebugPanel from './components/DebugPanel'
import LanguageSelector from './components/LanguageSelector'
import { InCallAssist, Trigger } from './components/InCallAssist'

interface CoachMessage {
  hint: string
  prob: number
  client_insight?: any
  next_step?: string
  current_stage?: string
  checklist_progress?: Record<string, boolean>
  transcript_preview?: string
  assist_trigger?: Trigger | null
}

function App() {
  const [isRecording, setIsRecording] = useState(false)
  const [, setHint] = useState('Нажмите "Начать запись" для старта коучинга')
  const [probability, setProbability] = useState(0)
  const [status, setStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle')
  const [selectedLanguage, setSelectedLanguage] = useState('id')
  const [transcriptLines, setTranscriptLines] = useState<string[]>([])  // Debug: transcript lines
  const [assistTrigger, setAssistTrigger] = useState<Trigger | null>(null)  // In-call assist trigger
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const ingestWsRef = useRef<WebSocket | null>(null)
  const coachWsRef = useRef<WebSocket | null>(null)
  const lastUpdateRef = useRef<number>(0)
  const streamRef = useRef<MediaStream | null>(null)

  const API_WS = import.meta.env.VITE_API_WS || 'ws://localhost:8000'
  const API_HTTP = import.meta.env.VITE_API_HTTP || 'http://localhost:8000'

  const handleTranscriptSubmit = async (transcript: string) => {
    try {
      setStatus('connecting')
      setHint('Обработка текста...')

      const formData = new FormData()
      formData.append('transcript', transcript)
      formData.append('language', selectedLanguage)

      const response = await fetch(`${API_HTTP}/api/process-transcript`, {
        method: 'POST',
        body: formData
      })

      const data = await response.json()

      if (data.success) {
        setStatus('connected')
        setHint(data.hint || 'Текст обработан успешно')
        setProbability(data.prob || 0)
        console.log('✅ Transcript processed:', data)
      } else {
        setStatus('error')
        setHint(`Ошибка: ${data.error}`)
      }
    } catch (err: any) {
      console.error('❌ Ошибка отправки transcript:', err)
      setStatus('error')
      setHint(`Ошибка: ${err.message}`)
    }
  }

  const handleVideoUpload = async (file: File) => {
    try {
      setStatus('connecting')
      setHint('Загрузка видео...')

      const formData = new FormData()
      formData.append('file', file)
      formData.append('language', selectedLanguage)  // Add language parameter

      const response = await fetch(`${API_HTTP}/api/process-video`, {
        method: 'POST',
        body: formData
      })

      const data = await response.json()

      if (data.success) {
        setStatus('connected')
        setHint(data.hint || 'Видео обработано успешно')
      } else {
        setStatus('error')
        setHint(`${data.error}\n\n${data.hint || ''}`)
      }
    } catch (err: any) {
      console.error('❌ Ошибка загрузки видео:', err)
      setStatus('error')
      setHint(`Ошибка: ${err.message}`)
    }
  }

  const handleYouTubeSubmit = async (url: string) => {
    try {
      setStatus('connecting')
      setHint('Загрузка с YouTube...')

      const formData = new FormData()
      formData.append('url', url)
      formData.append('language', selectedLanguage)
      formData.append('real_time', 'false') // Fast processing mode (no delays)

      const response = await fetch(`${API_HTTP}/api/process-youtube`, {
        method: 'POST',
        body: formData
      })

      const data = await response.json()

      if (data.success) {
        setStatus('connected')
        setHint(data.hint || 'YouTube видео обработано')
      } else {
        setStatus('error')
        setHint(`${data.error}\n\n${data.hint || ''}`)
      }
    } catch (err: any) {
      console.error('❌ Ошибка YouTube:', err)
      setStatus('error')
      setHint(`Ошибка: ${err.message}`)
    }
  }

  // Connect WebSockets on page load (for all modes)
  useEffect(() => {
    connectWebSockets()
  }, [])

  const connectWebSockets = () => {
    setStatus('connecting')

    // Подключение к /coach для получения подсказок
    const coachWs = new WebSocket(`${API_WS}/coach`)
    
    coachWs.onopen = () => {
      console.log('✅ /coach подключен')
      setStatus('connected')
      // Отправляем настройку языка
      coachWs.send(JSON.stringify({ type: 'set_language', language: selectedLanguage }))
    }

    coachWs.onmessage = (e) => {
      try {
        const data: CoachMessage = JSON.parse(e.data)
        
        // Rate limiting: не чаще 1 раз в секунду
        const now = Date.now()
        if (now - lastUpdateRef.current < 1000) {
          console.log('⏱️ Rate limit, пропускаем обновление')
          return
        }
        
        lastUpdateRef.current = now
        console.log('📨 Получено:', data)
        
        setHint(data.hint || 'Нет подсказки')
        setProbability(data.prob || 0)
        
        // Update assist trigger if present
        if (data.assist_trigger) {
          console.log('🎯 In-Call Assist trigger:', data.assist_trigger)
          setAssistTrigger(data.assist_trigger)
        }
        
        // Debug: обновляем транскрипт
        if (data.transcript_preview) {
          // Разбиваем на строки и берем последние 5
          const lines = data.transcript_preview.split('\n').filter(line => line.trim())
          setTranscriptLines(lines.slice(-5))
        }
      } catch (err) {
        console.error('❌ Ошибка парсинга сообщения:', err)
      }
    }

    coachWs.onerror = (err) => {
      console.error('❌ /coach ошибка:', err)
      setStatus('error')
    }

    coachWs.onclose = () => {
      console.log('🔌 /coach отключен')
      if (status === 'connected') {
        setStatus('idle')
      }
    }

    coachWsRef.current = coachWs

    // Подключение к /ingest для отправки аудио
    const ingestWs = new WebSocket(`${API_WS}/ingest`)
    
    ingestWs.onopen = () => {
      console.log('✅ /ingest подключен')
      // Отправляем настройку языка первым сообщением
      ingestWs.send(JSON.stringify({ type: 'set_language', language: selectedLanguage }))
    }

    ingestWs.onerror = (err) => {
      console.error('❌ /ingest ошибка:', err)
    }

    ingestWs.onclose = () => {
      console.log('🔌 /ingest отключен')
    }

    ingestWsRef.current = ingestWs
  }

  const startRecording = async () => {
    try {
      setStatus('connecting')
      setHint('Выбирайте вкладку с Google Meet и включите "Share audio"...')
      
      // Детальная диагностика
      console.log('🔍 === ДИАГНОСТИКА БРАУЗЕРА ===')
      console.log('  User Agent:', navigator.userAgent)
      console.log('  URL:', window.location.href)
      console.log('  Protocol:', window.location.protocol)
      console.log('  navigator.mediaDevices:', navigator.mediaDevices ? '✅ Есть' : '❌ Нет')
      console.log('  getDisplayMedia:', typeof navigator.mediaDevices?.getDisplayMedia === 'function' ? '✅ Есть' : '❌ Нет')
      console.log('  MediaRecorder:', typeof MediaRecorder !== 'undefined' ? '✅ Есть' : '❌ Нет')
      console.log('🔍 === КОНЕЦ ДИАГНОСТИКИ ===\n')
      
      // Проверка поддержки браузера
      if (!navigator.mediaDevices) {
        throw new Error('navigator.mediaDevices недоступен. Проверьте, что страница открыта через http://localhost:3000')
      }
      
      if (!navigator.mediaDevices.getDisplayMedia) {
        throw new Error('getDisplayMedia не поддерживается. Обновите Chrome или используйте другой браузер.')
      }

      // Захват аудио из таба Meet
      // ВАЖНО: Chrome требует video: true, даже если нам нужно только аудио
      console.log('🎤 Запрос захвата аудио+видео...')
      const stream = await navigator.mediaDevices.getDisplayMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        },
        video: true  // Обязательно для Chrome! Остановим видео позже
      })
      
      // Проверка, что действительно получили аудио-трек
      const audioTracks = stream.getAudioTracks()
      if (audioTracks.length === 0) {
        stream.getTracks().forEach(track => track.stop())
        throw new Error('Не удалось получить аудио-трек. Убедитесь, что выбрали "Share audio" при захвате.')
      }

      console.log('✅ Медиа-поток получен:', {
        audioTracks: audioTracks.length,
        videoTracks: stream.getVideoTracks().length,
        audioSettings: audioTracks[0].getSettings()
      })
      
      // Останавливаем видео-трек (он нам не нужен, нужно только аудио)
      const videoTracks = stream.getVideoTracks()
      videoTracks.forEach(track => {
        track.stop()
        stream.removeTrack(track)
        console.log('⏹️ Видео-трек остановлен (нам нужно только аудио)')
      })
      
      streamRef.current = stream

      // Обработка остановки трека (если пользователь нажал "Stop sharing")
      audioTracks[0].onended = () => {
        console.log('⏹️ Аудио-трек остановлен пользователем')
        stopRecording()
      }

      // Подключаем WebSocket'ы
      connectWebSockets()

      // ===== WEB AUDIO API APPROACH (более стабильный) =====
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000  // Whisper требует 16kHz
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
        
        // Отправляем по 16KB chunks (примерно каждые 0.5 сек при 16kHz)
        if (audioBuffer.length >= 8192) {
          const chunk = audioBuffer.slice(0, 8192)
          audioBuffer = audioBuffer.slice(8192)
          
          // Конвертируем Float32 → Int16
          const int16Chunk = new Int16Array(chunk.length)
          for (let i = 0; i < chunk.length; i++) {
            int16Chunk[i] = chunk[i] < 0 
              ? chunk[i] * 0x8000 
              : chunk[i] * 0x7FFF
          }
          
          if (ingestWsRef.current?.readyState === WebSocket.OPEN) {
            ingestWsRef.current.send(int16Chunk.buffer)
            console.log(`📤 Отправлен PCM chunk: ${int16Chunk.length} samples (${int16Chunk.buffer.byteLength} bytes)`)
          }
        }
      }
      
      source.connect(processor)
      processor.connect(audioContext.destination)
      
      // Сохраняем для остановки
      mediaRecorderRef.current = {
        stop: () => {
          processor.disconnect()
          source.disconnect()
          audioContext.close()
          console.log('🛑 Web Audio API stopped')
        }
      } as any

      setIsRecording(true)
      setHint('Захват аудио активен (Web Audio API 16kHz PCM). Ожидание подсказок от AI...')
      
      console.log('🎙️ Web Audio API запись началась (16kHz mono PCM)')

    } catch (err: any) {
      console.error('❌ Ошибка старта записи:', err)
      setStatus('error')
      
      // Более детальные сообщения об ошибках
      let errorMessage = 'Ошибка захвата аудио. '
      
      if (err.name === 'NotAllowedError') {
        errorMessage += 'Вы отклонили доступ к экрану/аудио. Попробуйте снова и разрешите доступ.'
      } else if (err.name === 'NotFoundError') {
        errorMessage += 'Не найден аудио-источник. Убедитесь, что выбрали "Share audio".'
      } else if (err.name === 'NotSupportedError') {
        errorMessage += 'Ваш браузер не поддерживает эту функцию. Используйте Chrome/Edge.'
      } else if (err.message) {
        errorMessage += err.message
      } else {
        errorMessage += 'Попробуйте ещё раз.'
      }
      
      setHint(errorMessage)
    }
  }

  const stopRecording = () => {
    console.log('⏹️ Остановка записи...')

    // Остановка MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current = null
    }

    // Остановка stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }

    // Закрытие WebSocket'ов
    if (ingestWsRef.current) {
      ingestWsRef.current.close()
      ingestWsRef.current = null
    }

    if (coachWsRef.current) {
      coachWsRef.current.close()
      coachWsRef.current = null
    }

    setIsRecording(false)
    setStatus('idle')
    setHint('Запись остановлена')
    setProbability(0)
  }

  // Cleanup при размонтировании
  useEffect(() => {
    return () => {
      if (isRecording) {
        stopRecording()
      }
    }
  }, [])

  const getStatusColor = () => {
    switch (status) {
      case 'connected': return '#10b981'
      case 'connecting': return '#f59e0b'
      case 'error': return '#ef4444'
      default: return '#6b7280'
    }
  }

  const getStatusText = () => {
    switch (status) {
      case 'connected': return 'Подключено'
      case 'connecting': return 'Подключение...'
      case 'error': return 'Ошибка'
      default: return 'Не подключено'
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🎯 Sales Best Friend</h1>
        <p className="subtitle">AI Voice Coach for Sales Calls</p>
        <div className="status-bar">
          <div className="status-indicator" style={{ backgroundColor: getStatusColor() }} />
          <span className="status-text">{getStatusText()}</span>
        </div>
      </header>

      <div className="main-container">
        {/* In-Call Assist or Next Step - Top */}
        {assistTrigger ? (
          <InCallAssist trigger={assistTrigger} />
        ) : (
          <NextStepCard coachWs={coachWsRef.current} />
        )}

        {/* Client Information Summary */}
        <ClientInfoSummary coachWs={coachWsRef.current} />

        {/* Call Checklist */}
        <CallChecklist coachWs={coachWsRef.current} />

        {/* Success Probability Card */}
        <div className="probability-card">
          <h3 className="probability-title">Deal Success Probability</h3>
          <div className="probability-display">
            <div className="probability-value">{Math.round(probability * 100)}%</div>
            <div className="probability-bar">
              <div 
                className="probability-fill" 
                style={{ 
                  width: `${probability * 100}%`,
                  backgroundColor: probability > 0.7 ? '#10b981' : probability > 0.4 ? '#f59e0b' : '#ef4444'
                }}
              />
            </div>
          </div>
        </div>

        {/* Debug Panel - Bottom */}
        <div className="debug-section">
          <h3 className="debug-title">Debug & Input Modes</h3>
          
          {/* Debug Transcript Block - 5 lines with scroll */}
          <div className="debug-transcript">
            <h4 className="transcript-label">📝 Live Transcript (Last 5 lines):</h4>
            <div className="transcript-box">
              {transcriptLines.length === 0 ? (
                <div className="transcript-empty">
                  <p>⏳ Waiting for transcription...</p>
                </div>
              ) : (
                <div className="transcript-content">
                  {transcriptLines.map((line, idx) => (
                    <div key={idx} className="transcript-line">
                      <span className="transcript-line-number">{transcriptLines.length - idx}</span>
                      <span className="transcript-line-text">{line}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          {/* Language Selector */}
          <LanguageSelector 
            selectedLanguage={selectedLanguage}
            onLanguageChange={setSelectedLanguage}
          />
          
          <DebugPanel
            onTranscriptSubmit={handleTranscriptSubmit}
            onVideoUpload={handleVideoUpload}
            onYouTubeSubmit={handleYouTubeSubmit}
          />

          <div className="controls">
            {!isRecording ? (
              <button className="btn btn-primary" onClick={startRecording}>
                🎤 Start Live Recording
              </button>
            ) : (
              <button className="btn btn-danger" onClick={stopRecording}>
                ⏹️ Stop Recording
              </button>
            )}
          </div>

          <div className="instructions">
            <p><strong>📋 Live Recording Instructions:</strong></p>
            <ol>
              <li>Click "🎤 Start Live Recording"</li>
              <li>Select <strong>the tab with Google Meet / YouTube</strong></li>
              <li>⚠️ <strong>IMPORTANT:</strong> Check <strong>"Share audio"</strong> checkbox</li>
              <li>Click "Share"</li>
              <li>💡 Video preview will appear and disappear - this is normal (we only need audio)</li>
            </ol>
            <p className="browser-hint">🌐 Use Chrome, Edge or Brave (Firefox doesn't support audio capture)</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

