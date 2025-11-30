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

// Default configurations (v3.1 - synced with backend)
const DEFAULT_STAGES: CallStage[] = [
  {
    id: 'stage_greeting',
    name: 'Greeting & Preparation',
    time_budget_seconds: 180,
    items: [
      { id: 'opening_greeting', type: 'say', label: 'Sapa dengan hangat dan perkenalkan diri dari Algonova' },
      { id: 'confirm_child_parent', type: 'say', label: 'Konfirmasi nama anak dan orang tua' },
      { id: 'confirm_companion', type: 'ask', label: 'Konfirmasi bahwa orang tua akan mendampingi anak' },
      { id: 'explain_stages', type: 'say', label: 'Jelaskan tahapan dan agenda trial class' }
    ]
  },
  {
    id: 'stage_profiling',
    name: 'Profiling',
    time_budget_seconds: 420,
    items: [
      { id: 'profile_age', type: 'ask', label: 'Konfirmasi usia dan tingkat sekolah anak' },
      { id: 'profile_interests', type: 'ask', label: 'Tanyakan minat anak (game, aktivitas, pelajaran)' },
      { id: 'profile_learning_preferences', type: 'ask', label: 'Tanyakan preferensi belajar anak' },
      { id: 'profile_hobbies_activities', type: 'ask', label: 'Tanyakan aktivitas harian dan hobi anak' }
    ]
  },
  {
    id: 'stage_real_points',
    name: 'Real Points',
    time_budget_seconds: 300,
    items: [
      { id: 'explain_difference_from_school', type: 'say', label: 'Jelaskan perbedaan Algonova dengan sekolah' },
      { id: 'explain_coding_design', type: 'say', label: 'Jelaskan secara sederhana apa itu coding atau design' },
      { id: 'imagination_role', type: 'say', label: 'Ajak anak membayangkan menjadi gamedev/animator muda' },
      { id: 'ask_what_to_create', type: 'ask', label: 'Tanyakan anak ingin membuat apa' }
    ]
  },
  {
    id: 'stage_profiling_summary',
    name: 'Profiling Summary',
    time_budget_seconds: 180,
    items: [
      { id: 'summary_child', type: 'say', label: 'Ringkas profil anak berdasarkan jawaban' },
      { id: 'summary_parent', type: 'say', label: 'Ringkas sudut pandang dan harapan orang tua' },
      { id: 'recommend_course', type: 'say', label: 'Rekomendasikan course yang paling sesuai' }
    ]
  },
  {
    id: 'stage_practical',
    name: 'Practical Session',
    time_budget_seconds: 1200,
    items: [
      { id: 'guide_tasks', type: 'say', label: 'Pandu guide anak dalam menyelesaikan tugas' },
      { id: 'ask_what_learned', type: 'ask', label: 'Tanyakan apa yang anak pelajari' },
      { id: 'ask_parent_feedback', type: 'ask', label: 'Tanyakan feedback dari orang tua' }
    ]
  },
  {
    id: 'stage_presentation',
    name: 'Presentation',
    time_budget_seconds: 420,
    items: [
      { id: 'introduce_school', type: 'say', label: 'Perkenalkan Algonova sebagai sekolah internasional' },
      { id: 'share_achievements', type: 'say', label: 'Ceritakan prestasi dan hasil karya murid' },
      { id: 'explain_learning_path', type: 'say', label: 'Jelaskan course lain dan learning path jangka panjang' }
    ]
  },
  {
    id: 'stage_bridging',
    name: 'Bridging',
    time_budget_seconds: 300,
    items: [
      { id: 'bridge_needs', type: 'say', label: 'Hubungkan hasil profiling dengan kebutuhan anak' },
      { id: 'bridge_results', type: 'say', label: 'Hubungkan hasil sesi praktik dengan potensi anak' }
    ]
  },
  {
    id: 'stage_negotiation',
    name: 'Negotiation',
    time_budget_seconds: 600,
    items: [
      { id: 'recommend_class_type', type: 'say', label: 'Rekomendasikan tipe kelas (Private / Premium / Group)' },
      { id: 'handle_objections', type: 'ask', label: 'Tanyakan keberatan dan jawab dengan empati' },
      { id: 'clarify_policies', type: 'say', label: 'Jelaskan refund, jadwal, dan harga dengan jelas' }
    ]
  },
  {
    id: 'stage_closure',
    name: 'Closure',
    time_budget_seconds: 300,
    items: [
      { id: 'close_call', type: 'say', label: 'Akhiri panggilan dengan profesional' },
      { id: 'closure_positive_if_paid', type: 'say', label: 'Jika sudah bayar, sambut dengan hangat dan beri arahan selanjutnya' },
      { id: 'closure_if_not_paid', type: 'say', label: 'Jika belum bayar, tetap tinggalkan kesan positif' }
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

  const [showImportExport, setShowImportExport] = useState(false)
  const [importJson, setImportJson] = useState('')
  const [importError, setImportError] = useState('')

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
  
  // Get unique categories from fields
  const getActiveCategories = () => {
    const cats = new Set(fields.map(f => f.category))
    return Array.from(cats)
  }

  const addCategory = () => {
    // Show all available categories, add the first one that's not used yet
    const usedCategories = getActiveCategories()
    const availableCategory = CATEGORIES.find(cat => !usedCategories.includes(cat.id))
    
    if (availableCategory) {
      const newField: ClientField = {
        id: generateId(),
        label: 'New Field',
        category: availableCategory.id,
        multiline: false
      }
      setFields([...fields, newField])
    } else {
      alert('All categories are already in use!')
    }
  }

  const addFieldToCategory = (category: string) => {
    const newField: ClientField = {
      id: generateId(),
      label: 'New Field',
      category: category,
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

  const deleteCategory = (category: string) => {
    if (confirm(`Delete all fields in category "${CATEGORIES.find(c => c.id === category)?.label}"?`)) {
      setFields(fields.filter(f => f.category !== category))
    }
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

  // ===== IMPORT / EXPORT =====

  // Helper: Generate ID from text (kebab-case)
  const generateIdFromText = (text: string) => {
    return text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .substring(0, 50) || generateId()
  }

  const handleExportJSON = () => {
    // Simplify for export: remove IDs, use minutes instead of seconds
    const simplifiedStages = stages.map(stage => ({
      name: stage.name,
      time_minutes: Math.round(stage.time_budget_seconds / 60),
      items: stage.items.map(item => ({
        type: item.type,
        label: item.label
      }))
    }))

    // Group fields by category for simpler JSON
    const fieldsByCategory: Record<string, any[]> = {}
    fields.forEach(field => {
      if (!fieldsByCategory[field.category]) {
        fieldsByCategory[field.category] = []
      }
      fieldsByCategory[field.category].push({
        label: field.label,
        type: field.multiline ? 'textarea' : 'text',
        ...(field.hint && { hint: field.hint })
      })
    })

    const config = {
      call_structure: simplifiedStages,
      client_fields: fieldsByCategory
    }
    const json = JSON.stringify(config, null, 2)
    
    // Copy to clipboard
    navigator.clipboard.writeText(json).then(() => {
      alert('✅ Configuration copied to clipboard!')
    }).catch(() => {
      // Fallback: show JSON in textarea
      setImportJson(json)
      setShowImportExport(true)
      alert('📋 Configuration shown below. Copy it manually.')
    })
  }

  const handleImportJSON = () => {
    setImportError('')
    setImportJson('')
    setShowImportExport(true)
  }

  const handleImportConfirm = () => {
    try {
      const config = JSON.parse(importJson)
      
      // Validate structure
      if (!config.call_structure || !Array.isArray(config.call_structure)) {
        throw new Error('Invalid structure: call_structure must be an array')
      }
      if (!config.client_fields) {
        throw new Error('Invalid structure: client_fields is required')
      }
      // Accept both formats: array (old) or object (new, grouped by category)
      if (!Array.isArray(config.client_fields) && typeof config.client_fields !== 'object') {
        throw new Error('Invalid structure: client_fields must be an array or object')
      }

      // Convert simplified format to full format with auto-generated IDs
      const fullStages: CallStage[] = config.call_structure.map((stage: any) => {
        const stageId = stage.id || generateIdFromText(stage.name)
        
        return {
          id: stageId,
          name: stage.name,
          // Support both time_minutes (new) and time_budget_seconds (old)
          time_budget_seconds: stage.time_minutes 
            ? stage.time_minutes * 60 
            : (stage.time_budget_seconds || 180),
          items: (stage.items || []).map((item: any) => ({
            id: item.id || generateIdFromText(item.label),
            type: item.type || 'ask',
            label: item.label
          }))
        }
      })

      // Support both formats: grouped by category (new) or flat array (old)
      let fullFields: ClientField[] = []
      
      if (Array.isArray(config.client_fields)) {
        // Old format: flat array
        fullFields = config.client_fields.map((field: any) => ({
          id: field.id || generateIdFromText(field.label),
          label: field.label,
          category: field.category || 'notes',
          multiline: field.multiline !== undefined ? field.multiline : (field.type === 'textarea'),
          hint: field.hint
        }))
      } else {
        // New format: grouped by category
        Object.entries(config.client_fields).forEach(([category, categoryFields]: [string, any]) => {
          if (Array.isArray(categoryFields)) {
            categoryFields.forEach((field: any) => {
              fullFields.push({
                id: field.id || generateIdFromText(field.label),
                label: field.label,
                category: category,
                multiline: field.type === 'textarea' || field.multiline === true,
                hint: field.hint
              })
            })
          }
        })
      }

      // Apply configuration
      setStages(fullStages)
      setFields(fullFields)
      setShowImportExport(false)
      setImportJson('')
      alert('✅ Configuration imported successfully!')
      
    } catch (err: any) {
      setImportError(err.message || 'Invalid JSON format')
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
                <div className="header-actions">
                  <button className="btn-import" onClick={handleImportJSON}>
                    📥 Import JSON
                  </button>
                  <button className="btn-export" onClick={handleExportJSON}>
                    📤 Export JSON
                  </button>
                  <button className="btn-add" onClick={addStage}>
                    ➕ Add Stage
                  </button>
                </div>
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
                <div className="header-actions">
                  <button className="btn-import" onClick={handleImportJSON}>
                    📥 Import JSON
                  </button>
                  <button className="btn-export" onClick={handleExportJSON}>
                    📤 Export JSON
                  </button>
                  <button className="btn-add" onClick={addCategory}>
                    ➕ Add Category
                  </button>
                </div>
              </div>
              
              <div className="editor-container">
                {getActiveCategories().map((category, catIndex) => {
                  const categoryInfo = CATEGORIES.find(c => c.id === category)
                  const categoryFields = fields.filter(f => f.category === category)
                  
                  return (
                    <div key={category} className="stage-editor">
                      <div className="stage-editor-header">
                        <span className="stage-number">{catIndex + 1}</span>
                        <div className="stage-info">
                          <h4 className="stage-name">{categoryInfo?.label || category}</h4>
                        </div>
                        <button 
                          className="btn-delete-stage" 
                          onClick={() => deleteCategory(category)}
                          title="Delete category"
                        >
                          🗑️
                        </button>
                      </div>

                      <div className="items-list">
                        {categoryFields.map((field) => (
                          <div key={field.id} className="item-editor">
                            <select
                              className="item-type-select"
                              value={field.multiline ? 'textarea' : 'text'}
                              onChange={(e) => updateField(field.id, { multiline: e.target.value === 'textarea' })}
                            >
                              <option value="text">Text</option>
                              <option value="textarea">Textarea</option>
                            </select>
                            <input
                              type="text"
                              className="item-label-input"
                              value={field.label}
                              onChange={(e) => updateField(field.id, { label: e.target.value })}
                              placeholder="Field label..."
                            />
                            <input
                              type="text"
                              className="field-hint-inline"
                              value={field.hint || ''}
                              onChange={(e) => updateField(field.id, { hint: e.target.value })}
                              placeholder="Hint for AI (optional)"
                            />
                            <button
                              className="btn-delete-item"
                              onClick={() => deleteField(field.id)}
                              title="Delete field"
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                      </div>

                      <button 
                        className="btn-add-item" 
                        onClick={() => addFieldToCategory(category)}
                      >
                        + Add Field
                      </button>
                    </div>
                  )
                })}
              </div>

              {getActiveCategories().length === 0 && (
                <div className="empty-editor">
                  <p>No categories yet. Click "Add Category" to get started!</p>
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

      {/* Import/Export Modal */}
      {showImportExport && (
        <div className="import-export-modal" onClick={() => setShowImportExport(false)}>
          <div className="import-export-content" onClick={e => e.stopPropagation()}>
            <div className="import-export-header">
              <h3>Import / Export Configuration</h3>
              <button className="close-btn" onClick={() => setShowImportExport(false)}>✕</button>
            </div>
            
            <div className="import-export-body">
              <p className="import-export-info">
                {importJson && !importError 
                  ? '📋 Copy the JSON below or paste your own configuration:' 
                  : '📥 Paste your JSON configuration below:'}
              </p>
              
              <textarea
                className="json-textarea"
                value={importJson}
                onChange={(e) => setImportJson(e.target.value)}
                placeholder='{"call_structure": [...], "client_fields": [...]}'
                rows={15}
              />
              
              {importError && (
                <div className="import-error">
                  ❌ {importError}
                </div>
              )}
            </div>
            
            <div className="import-export-footer">
              <button className="btn-secondary" onClick={() => setShowImportExport(false)}>
                Cancel
              </button>
              <button className="btn-save" onClick={handleImportConfirm}>
                ✅ Import Configuration
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

