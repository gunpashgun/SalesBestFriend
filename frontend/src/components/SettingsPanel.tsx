/**
 * Settings Panel Component
 * 
 * Visual editor for:
 * - Call structure (stages, items, timing)
 * - Client card fields
 * - Language selection
 * 
 * Persists to localStorage, applies immediately
 */

import { useState } from 'react'
import './SettingsPanel.css'

interface ChecklistItem {
  id: string
  type: 'ask' | 'say'
  label: string
}

interface CallStage {
  id: string
  name: string
  time_budget_seconds: number
  items: ChecklistItem[]
}

interface ClientField {
  id: string
  label: string
  category: string
  multiline: boolean
  hint?: string
}

interface SettingsPanelProps {
  onClose: () => void
  selectedLanguage: string
  onLanguageChange: (lang: string) => void
  onConfigUpdate?: (stages: CallStage[], fields: ClientField[]) => void
}

const LANGUAGES = [
  { code: 'id', name: 'Bahasa Indonesia' },
  { code: 'en', name: 'English' },
  { code: 'ru', name: 'Русский' }
]

const CATEGORIES = [
  { id: 'child_info', label: '👶 Child Information' },
  { id: 'parent_info', label: '👨‍👩‍👧 Parent & Goals' },
  { id: 'needs', label: '🎯 Needs & Outcomes' },
  { id: 'concerns', label: '⚠️ Concerns' },
  { id: 'notes', label: '📝 Notes' }
]

// Default configurations
const DEFAULT_STAGES: CallStage[] = [
  {
    id: 'greeting',
    name: 'Greeting & Rapport',
    time_budget_seconds: 120,
    items: [
      { id: 'intro_self', type: 'ask', label: 'Introduce yourself & company' },
      { id: 'check_time', type: 'ask', label: 'Check client\'s availability' },
      { id: 'set_agenda', type: 'say', label: 'Set agenda for the call' }
    ]
  },
  {
    id: 'discovery',
    name: 'Discovery & Needs',
    time_budget_seconds: 300,
    items: [
      { id: 'child_age', type: 'ask', label: 'Ask about child\'s age' },
      { id: 'interests', type: 'ask', label: 'Explore child\'s interests' }
    ]
  }
]

const DEFAULT_FIELDS: ClientField[] = [
  { id: 'child_name', label: 'Child\'s Name', category: 'child_info', multiline: false },
  { id: 'child_interests', label: 'Child\'s Interests', category: 'child_info', multiline: true, hint: 'Games, subjects child likes' },
  { id: 'main_pain_point', label: 'Main Pain Point', category: 'needs', multiline: true, hint: 'Problem they\'re solving' }
]

export default function SettingsPanel({ onClose, selectedLanguage, onLanguageChange, onConfigUpdate }: SettingsPanelProps) {
  const [activeTab, setActiveTab] = useState<'general' | 'structure' | 'fields'>('general')
  
  // Load from localStorage or use defaults
  const [stages, setStages] = useState<CallStage[]>(() => {
    const saved = localStorage.getItem('call_structure')
    return saved ? JSON.parse(saved) : DEFAULT_STAGES
  })
  
  const [fields, setFields] = useState<ClientField[]>(() => {
    const saved = localStorage.getItem('client_fields')
    return saved ? JSON.parse(saved) : DEFAULT_FIELDS
  })

  // Helper to generate unique IDs
  const generateId = () => `item_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

  // ===== STAGE MANAGEMENT =====
  
  const addStage = () => {
    const newStage: CallStage = {
      id: generateId(),
      name: 'New Stage',
      time_budget_seconds: 180,
      items: []
    }
    setStages([...stages, newStage])
  }

  const updateStage = (stageId: string, updates: Partial<CallStage>) => {
    setStages(stages.map(s => s.id === stageId ? { ...s, ...updates } : s))
  }

  const deleteStage = (stageId: string) => {
    setStages(stages.filter(s => s.id !== stageId))
  }

  const addItemToStage = (stageId: string) => {
    const newItem: ChecklistItem = {
      id: generateId(),
      type: 'ask',
      label: 'New checklist item'
    }
    setStages(stages.map(s => 
      s.id === stageId 
        ? { ...s, items: [...s.items, newItem] }
        : s
    ))
  }

  const updateItem = (stageId: string, itemId: string, updates: Partial<ChecklistItem>) => {
    setStages(stages.map(s =>
      s.id === stageId
        ? {
            ...s,
            items: s.items.map(item =>
              item.id === itemId ? { ...item, ...updates } : item
            )
          }
        : s
    ))
  }

  const deleteItem = (stageId: string, itemId: string) => {
    setStages(stages.map(s =>
      s.id === stageId
        ? { ...s, items: s.items.filter(item => item.id !== itemId) }
        : s
    ))
  }

  // ===== FIELD MANAGEMENT =====
  
  const addField = () => {
    const newField: ClientField = {
      id: generateId(),
      label: 'New Field',
      category: 'notes',
      multiline: false
    }
    setFields([...fields, newField])
  }

  const updateField = (fieldId: string, updates: Partial<ClientField>) => {
    setFields(fields.map(f => f.id === fieldId ? { ...f, ...updates } : f))
  }

  const deleteField = (fieldId: string) => {
    setFields(fields.filter(f => f.id !== fieldId))
  }

  // ===== SAVE =====
  
  const handleSave = () => {
    localStorage.setItem('call_structure', JSON.stringify(stages))
    localStorage.setItem('client_fields', JSON.stringify(fields))
    
    if (onConfigUpdate) {
      onConfigUpdate(stages, fields)
    }
    
    alert('✅ Configuration saved!')
  }

  const handleReset = () => {
    if (confirm('Reset to default configuration? This will delete all your changes.')) {
      setStages(DEFAULT_STAGES)
      setFields(DEFAULT_FIELDS)
      localStorage.removeItem('call_structure')
      localStorage.removeItem('client_fields')
    }
  }

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="settings-header">
          <h2>Settings</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Tabs */}
        <div className="settings-tabs">
          <button 
            className={`tab ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            General
          </button>
          <button 
            className={`tab ${activeTab === 'structure' ? 'active' : ''}`}
            onClick={() => setActiveTab('structure')}
          >
            Call Structure
          </button>
          <button 
            className={`tab ${activeTab === 'fields' ? 'active' : ''}`}
            onClick={() => setActiveTab('fields')}
          >
            Client Fields
          </button>
        </div>

        {/* Content */}
        <div className="settings-content">
          {activeTab === 'general' && (
            <div className="settings-section">
              <h3>General Settings</h3>
              
              <div className="setting-item">
                <label className="setting-label">Conversation Language</label>
                <p className="setting-description">
                  Language spoken during the call (for transcription)
                </p>
                <select 
                  className="setting-select"
                  value={selectedLanguage}
                  onChange={(e) => onLanguageChange(e.target.value)}
                >
                  {LANGUAGES.map(lang => (
                    <option key={lang.code} value={lang.code}>
                      {lang.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="setting-item">
                <label className="setting-label">Interface Language</label>
                <p className="setting-description">
                  Interface is always in English (optimized for screen sharing)
                </p>
                <select className="setting-select" disabled>
                  <option>English</option>
                </select>
              </div>
            </div>
          )}

          {activeTab === 'structure' && (
            <div className="settings-section">
              <div className="section-header-row">
                <div>
                  <h3>Call Structure Configuration</h3>
                  <p className="section-info">
                    Configure stages and checklist items for your trial class flow.
                  </p>
                </div>
                <button className="btn-add" onClick={addStage}>
                  ➕ Add Stage
                </button>
              </div>
              
              <div className="editor-container">
                {stages.map((stage, stageIndex) => (
                  <div key={stage.id} className="stage-editor">
                    <div className="stage-editor-header">
                      <span className="stage-number">{stageIndex + 1}</span>
                      <input
                        type="text"
                        className="stage-name-input"
                        value={stage.name}
                        onChange={(e) => updateStage(stage.id, { name: e.target.value })}
                        placeholder="Stage name"
                      />
                      <div className="stage-time-input">
                        <input
                          type="number"
                          value={Math.floor(stage.time_budget_seconds / 60)}
                          onChange={(e) => updateStage(stage.id, { time_budget_seconds: parseInt(e.target.value) * 60 })}
                          min="1"
                          max="30"
                        />
                        <span>min</span>
                      </div>
                      <button 
                        className="btn-delete-stage" 
                        onClick={() => deleteStage(stage.id)}
                        title="Delete stage"
                      >
                        🗑️
                      </button>
                    </div>

                    <div className="items-list">
                      {stage.items.map((item) => (
                        <div key={item.id} className="item-editor">
                          <select
                            className="item-type-select"
                            value={item.type}
                            onChange={(e) => updateItem(stage.id, item.id, { type: e.target.value as 'ask' | 'say' })}
                          >
                            <option value="ask">Ask</option>
                            <option value="say">Say</option>
                          </select>
                          <input
                            type="text"
                            className="item-label-input"
                            value={item.label}
                            onChange={(e) => updateItem(stage.id, item.id, { label: e.target.value })}
                            placeholder="What to ask or say..."
                          />
                          <button
                            className="btn-delete-item"
                            onClick={() => deleteItem(stage.id, item.id)}
                            title="Delete item"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>

                    <button 
                      className="btn-add-item" 
                      onClick={() => addItemToStage(stage.id)}
                    >
                      + Add Item
                    </button>
                  </div>
                ))}
              </div>

              {stages.length === 0 && (
                <div className="empty-editor">
                  <p>No stages yet. Click "Add Stage" to get started!</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'fields' && (
            <div className="settings-section">
              <div className="section-header-row">
                <div>
                  <h3>Client Card Fields</h3>
                  <p className="section-info">
                    Configure which fields to track for client information.
                  </p>
                </div>
                <button className="btn-add" onClick={addField}>
                  ➕ Add Field
                </button>
              </div>
              
              <div className="editor-container">
                {fields.map((field) => (
                  <div key={field.id} className="field-editor">
                    <input
                      type="text"
                      className="field-label-input"
                      value={field.label}
                      onChange={(e) => updateField(field.id, { label: e.target.value })}
                      placeholder="Field label"
                    />
                    
                    <select
                      className="field-category-select"
                      value={field.category}
                      onChange={(e) => updateField(field.id, { category: e.target.value })}
                    >
                      {CATEGORIES.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.label}</option>
                      ))}
                    </select>

                    <label className="field-multiline-toggle">
                      <input
                        type="checkbox"
                        checked={field.multiline}
                        onChange={(e) => updateField(field.id, { multiline: e.target.checked })}
                      />
                      <span>Multiline</span>
                    </label>

                    <input
                      type="text"
                      className="field-hint-input"
                      value={field.hint || ''}
                      onChange={(e) => updateField(field.id, { hint: e.target.value })}
                      placeholder="Hint for AI (optional)"
                    />

                    <button
                      className="btn-delete-field"
                      onClick={() => deleteField(field.id)}
                      title="Delete field"
                    >
                      🗑️
                    </button>
                  </div>
                ))}
              </div>

              {fields.length === 0 && (
                <div className="empty-editor">
                  <p>No fields yet. Click "Add Field" to get started!</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="settings-footer">
          <button className="btn-reset" onClick={handleReset}>
            Reset to Default
          </button>
          <div className="footer-actions">
            <button className="btn-secondary" onClick={onClose}>
              Close
            </button>
            <button className="btn-save" onClick={handleSave}>
              💾 Save & Apply
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

