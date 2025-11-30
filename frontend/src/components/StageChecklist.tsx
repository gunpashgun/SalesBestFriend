/**
 * Stage Checklist Component
 * 
 * Shows call stages with:
 * - Time budget per stage
 * - Progress indicators
 * - Timing status (on time / late)
 * - Checklist items with manual override
 */

import { useState } from 'react'
import './StageChecklist.css'

interface ChecklistItem {
  id: string
  type: 'discuss' | 'say'
  content: string
  completed: boolean
  evidence: string
  confidence?: number
  extended_description?: string  // Optional: detailed description for LLM
  semantic_keywords?: {  // Optional: for backend use
    required?: string[]
    forbidden?: string[]
  }
}

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

interface StageChecklistProps {
  stages: Stage[]
  currentStageId: string
  callElapsed: number
  stageElapsed: number
  onManualToggle: (itemId: string) => void
}

export default function StageChecklist({ stages, stageElapsed, onManualToggle }: StageChecklistProps) {
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set())
  const [detailsModal, setDetailsModal] = useState<{ item: ChecklistItem; stageName: string } | null>(null)

  const toggleStage = (stageId: string) => {
    setExpandedStages(prev => {
      const next = new Set(prev)
      if (next.has(stageId)) {
        next.delete(stageId)
      } else {
        next.add(stageId)
      }
      return next
    })
  }

  const showDetails = (item: ChecklistItem, stageName: string) => {
    setDetailsModal({ item, stageName })
  }

  const closeDetails = () => {
    setDetailsModal(null)
  }

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getTimingBadgeColor = (status: string): string => {
    switch (status) {
      case 'on_time': return '#10b981'
      case 'slightly_late': return '#f59e0b'
      case 'very_late': return '#ef4444'
      default: return '#9ca3af'
    }
  }

  const getStageProgress = (stage: Stage) => {
    const completed = stage.items.filter(item => item.completed).length
    const total = stage.items.length
    return { completed, total, percentage: total > 0 ? Math.round((completed / total) * 100) : 0 }
  }

  return (
    <div className="stage-checklist">
      <h2 className="checklist-title">Call Structure</h2>
      
      <div className="stages-container">
        {stages.map((stage, index) => {
          const progress = getStageProgress(stage)
          const isExpanded = expandedStages.has(stage.id) || stage.isCurrent
          const stageStart = formatTime(stage.startOffsetSeconds)
          const stageEnd = formatTime(stage.startOffsetSeconds + stage.durationSeconds)

          return (
            <div 
              key={stage.id}
              className={`stage-block ${stage.isCurrent ? 'current' : ''}`}
            >
              {/* Stage Header */}
              <div 
                className="stage-header"
                onClick={() => toggleStage(stage.id)}
              >
                <div className="stage-header-left">
                  <span className="stage-number">{index + 1}</span>
                  <div className="stage-info">
                    <h3 className="stage-name">{stage.name}</h3>
                    <div className="stage-time-container">
                      <span className="stage-time">{stageStart} – {stageEnd}</span>
                      {stage.isCurrent && (
                        <span className="stage-timer">
                          ⏱️ {formatTime(stageElapsed)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="stage-header-right">
                  <span 
                    className="timing-badge"
                    style={{ backgroundColor: getTimingBadgeColor(stage.timingStatus) }}
                  >
                    {stage.timingMessage}
                  </span>
                  
                  <div className="progress-indicator">
                    <span className="progress-text">{progress.completed}/{progress.total}</span>
                    <div className="progress-bar-small">
                      <div 
                        className="progress-fill-small"
                        style={{ width: `${progress.percentage}%` }}
                      />
                    </div>
                  </div>

                  <button className="expand-btn">
                    {isExpanded ? '▼' : '▶'}
                  </button>
                </div>
              </div>

              {/* Stage Items (collapsible) */}
              {isExpanded && (
                <div className="stage-items">
                  {stage.items.map(item => (
                    <div 
                      key={item.id}
                      className={`checklist-item ${item.completed ? 'completed' : ''}`}
                    >
                      <label className="checkbox-wrapper">
                        <input 
                          type="checkbox"
                          checked={item.completed}
                          onChange={() => onManualToggle(item.id)}
                          className="checkbox-input"
                        />
                        <span className="checkbox-custom">
                          {item.completed && <span className="checkmark">✓</span>}
                        </span>
                      </label>

                      <div className="item-content">
                        <span className="item-type-badge">
                          {item.type === 'discuss' ? '💬 Discuss' : '💡 Say'}
                        </span>
                        <span className="item-text">{item.content}</span>
                      </div>

                      {item.completed && item.evidence && (
                        <button 
                          className="details-btn"
                          onClick={() => showDetails(item, stage.name)}
                          title="Show reasoning"
                        >
                          Details
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {stages.length === 0 && (
        <div className="empty-state">
          <p>⏳ Waiting for session to start...</p>
        </div>
      )}

      {/* Details Modal */}
      {detailsModal && (
        <div className="modal-overlay" onClick={closeDetails}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Item Details</h3>
              <button className="modal-close" onClick={closeDetails}>✕</button>
            </div>
            
            <div className="modal-body">
              <div className="detail-section">
                <label>Stage:</label>
                <div className="detail-value">{detailsModal.stageName}</div>
              </div>

              <div className="detail-section">
                <label>Item:</label>
                <div className="detail-value">{detailsModal.item.content}</div>
              </div>

              <div className="detail-section">
                <label>Type:</label>
                <div className="detail-value">
                  <span className="item-type-badge">
                    {detailsModal.item.type === 'discuss' ? '💬 Discuss' : '💡 Say'}
                  </span>
                </div>
              </div>

              <div className="detail-section">
                <label>Status:</label>
                <div className="detail-value">
                  <span className={`status-badge ${detailsModal.item.completed ? 'completed' : 'pending'}`}>
                    {detailsModal.item.completed ? '✓ Completed' : '⏳ Pending'}
                  </span>
                </div>
              </div>

              {detailsModal.item.confidence !== undefined && (
                <div className="detail-section">
                  <label>Confidence:</label>
                  <div className="detail-value">
                    <div className="confidence-bar">
                      <div 
                        className="confidence-fill"
                        style={{ width: `${(detailsModal.item.confidence || 0) * 100}%` }}
                      />
                    </div>
                    <span className="confidence-text">
                      {Math.round((detailsModal.item.confidence || 0) * 100)}%
                    </span>
                  </div>
                </div>
              )}

              <div className="detail-section">
                <label>Evidence / Reasoning:</label>
                <div className="detail-value evidence-box">
                  {detailsModal.item.evidence || 'No evidence available'}
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-close" onClick={closeDetails}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

