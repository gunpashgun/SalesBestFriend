import React, { useState, useEffect, useRef } from 'react'
import './InCallAssist.css'

export interface Trigger {
  id: string
  title: string
  hint: string
  priority: number
  isPositive?: boolean
}

interface InCallAssistProps {
  trigger: Trigger | null
}

export const InCallAssist: React.FC<InCallAssistProps> = ({ trigger }) => {
  const [displayedTrigger, setDisplayedTrigger] = useState<Trigger | null>(null)
  const [isVisible, setIsVisible] = useState(false)
  const [fadeOut, setFadeOut] = useState(false)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)
  const dismissRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    // New trigger arrived
    if (trigger) {
      // Clear any pending dismissals
      if (dismissRef.current) clearTimeout(dismissRef.current)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)

      // Show new trigger
      setFadeOut(false)
      setDisplayedTrigger(trigger)
      setIsVisible(true)

      // Auto-dismiss after 10 seconds
      dismissRef.current = setTimeout(() => {
        handleClose()
      }, 10000)
    }
  }, [trigger])

  const handleClose = () => {
    setFadeOut(true)
    timeoutRef.current = setTimeout(() => {
      setIsVisible(false)
      setDisplayedTrigger(null)
      setFadeOut(false)
    }, 300) // Wait for fade-out animation
  }

  if (!isVisible || !displayedTrigger) {
    return null
  }

  const isPositive = displayedTrigger.isPositive || false

  return (
    <div
      className={`in-call-assist ${isPositive ? 'positive' : 'attention'} ${
        fadeOut ? 'fade-out' : 'fade-in'
      }`}
    >
      <div className="assist-header">
        <span className="assist-title">{displayedTrigger.title}</span>
        <button
          className="assist-close"
          onClick={handleClose}
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <div className="assist-body">
        <p className="assist-hint">{displayedTrigger.hint}</p>
      </div>

      <div className="assist-footer">
        <button className="assist-ok-btn" onClick={handleClose}>
          OK
        </button>
      </div>

      {/* Visual timer */}
      <div className="assist-timer"></div>
    </div>
  )
}
