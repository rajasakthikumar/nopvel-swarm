<template>
  <div class="snowflake-page">

    <!-- ── Header ── -->
    <div class="sf-header">
      <div class="sf-header-left">
        <span class="sf-logo">❄️ Snowflake Method</span>
        <span class="sf-subtitle">Webnovel Planner — 4 Arcs × 3 Beats × 10 Steps</span>
      </div>
      <div class="sf-header-right">
        <span class="sf-progress-label">
          {{ completedCount }} / {{ totalFields }} fields filled
        </span>
        <div class="sf-progress-bar">
          <div class="sf-progress-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
        <button class="sf-btn sf-btn-ghost" @click="clearAll" title="Clear all saved data">🗑 Reset</button>
      </div>
    </div>

    <div class="sf-body">

      <!-- ── Left: Arc + Step sidebar ── -->
      <aside class="sf-sidebar">

        <!-- Arc selector -->
        <div class="sf-arc-list">
          <div
            v-for="arc in arcs"
            :key="arc.num"
            class="sf-arc-item"
            :class="{ active: currentArc === arc.num }"
            @click="selectArc(arc.num)"
          >
            <div class="sf-arc-header">
              <span class="sf-arc-badge">ARC {{ arc.num }}</span>
              <span class="sf-arc-name">{{ arc.name }}</span>
              <span class="sf-arc-fill">{{ arcCompletedCount(arc.num) }}/{{ arcTotalFields(arc.num) }}</span>
            </div>
            <div class="sf-arc-progress">
              <div
                class="sf-arc-prog-fill"
                :style="{ width: arcProgressPct(arc.num) + '%', background: arc.color }"
              ></div>
            </div>
          </div>
        </div>

        <!-- Step list -->
        <div class="sf-step-list">
          <div class="sf-step-list-title">STEPS</div>
          <div
            v-for="step in steps"
            :key="step.step"
            class="sf-step-item"
            :class="{
              active: currentStep === step.step,
              done: isStepFilled(currentArc, currentBeat, step.step),
            }"
            @click="goToStep(step.step)"
          >
            <span class="sf-step-num">{{ step.step }}</span>
            <span class="sf-step-icon">{{ step.icon }}</span>
            <span class="sf-step-name">{{ step.title }}</span>
            <span class="sf-step-check" v-if="isStepFilled(currentArc, currentBeat, step.step)">✓</span>
          </div>
        </div>

      </aside>

      <!-- ── Main: Step card ── -->
      <main class="sf-main">

        <!-- Beat selector (steps 6-10 are beat-level) -->
        <div class="sf-beat-bar" :class="{ visible: currentStep >= 6 }">
          <span class="sf-beat-label">PLOT BEAT:</span>
          <button
            v-for="beat in beats"
            :key="beat.num"
            class="sf-beat-btn"
            :class="{ active: currentBeat === beat.num }"
            @click="selectBeat(beat.num)"
          >
            <span class="sf-beat-num">{{ beat.num }}</span>
            {{ beat.name }}
          </button>
        </div>

        <!-- Step card -->
        <div class="sf-card">

          <!-- Card header -->
          <div class="sf-card-header">
            <div class="sf-card-title-row">
              <span class="sf-step-badge">Step {{ currentStep }}/10</span>
              <span class="sf-arc-tag" :style="{ background: arcColor(currentArc) }">
                Arc {{ currentArc }} — {{ arcName(currentArc) }}
              </span>
              <span v-if="currentStep >= 6" class="sf-beat-tag">
                Beat {{ currentBeat }} — {{ beatName(currentBeat) }}
              </span>
            </div>
            <h2 class="sf-card-title">
              {{ currentStepMeta.icon }} {{ currentStepMeta.title }}
            </h2>
          </div>

          <!-- Instruction box -->
          <div class="sf-instruction">
            <div class="sf-instruction-label">WHAT TO DO</div>
            <div class="sf-instruction-text" v-html="formatInstruction(currentStepMeta.instruction)"></div>
          </div>

          <!-- Arc-specific note (shown for arcs 2-4) -->
          <div class="sf-arc-note" v-if="currentArcNote">
            <span class="sf-arc-note-icon">💡</span>
            <span>{{ currentArcNote }}</span>
          </div>

          <!-- Textarea -->
          <div class="sf-field">
            <div class="sf-field-header">
              <span class="sf-field-label">YOUR CONTENT</span>
              <span class="sf-field-count">{{ currentValue.length }} chars</span>
            </div>
            <textarea
              class="sf-textarea"
              v-model="currentValue"
              :placeholder="currentStepMeta.placeholder"
              @input="onInput"
              rows="12"
            ></textarea>
          </div>

          <!-- AI Suggest -->
          <div class="sf-suggest-row">
            <button
              class="sf-btn sf-btn-suggest"
              @click="getSuggestion"
              :disabled="isSuggesting"
            >
              <span v-if="!isSuggesting">✨ AI Suggest</span>
              <span v-else class="sf-loading">
                <span class="sf-dot-anim"></span> Generating...
              </span>
            </button>
            <span v-if="suggestError" class="sf-error">{{ suggestError }}</span>
          </div>

          <!-- AI suggestion output -->
          <div v-if="suggestion" class="sf-suggestion-box">
            <div class="sf-suggestion-header">
              <span>✨ AI Suggestion</span>
              <div class="sf-suggestion-actions">
                <button class="sf-btn sf-btn-small" @click="useSuggestion">Use this ↑</button>
                <button class="sf-btn sf-btn-small sf-btn-ghost" @click="appendSuggestion">Append ↓</button>
                <button class="sf-btn sf-btn-small sf-btn-ghost" @click="suggestion = ''">✕ Dismiss</button>
              </div>
            </div>
            <div class="sf-suggestion-text">{{ suggestion }}</div>
          </div>

          <!-- Navigation -->
          <div class="sf-nav-row">
            <button
              class="sf-btn sf-btn-ghost"
              @click="prevStep"
              :disabled="currentStep === 1 && currentArc === 1"
            >
              ← Previous
            </button>
            <div class="sf-step-dots">
              <span
                v-for="s in 10"
                :key="s"
                class="sf-dot"
                :class="{
                  active: s === currentStep,
                  filled: isStepFilled(currentArc, currentBeat, s),
                }"
                @click="goToStep(s)"
              ></span>
            </div>
            <button
              class="sf-btn sf-btn-primary"
              @click="nextStep"
              :disabled="currentStep === 10 && currentArc === 4"
            >
              {{ isLastStep ? '🎉 Arc Complete' : 'Next →' }}
            </button>
          </div>

        </div>

        <!-- Arc completion banner -->
        <div v-if="showArcComplete" class="sf-arc-complete">
          <div class="sf-arc-complete-inner">
            <div class="sf-arc-complete-icon">🎉</div>
            <h3>Arc {{ currentArc }} Complete!</h3>
            <p>
              You've finished all 10 steps for Arc {{ currentArc }} — {{ arcName(currentArc) }}.
              <span v-if="currentArc < 4">Ready to expand into Arc {{ currentArc + 1 }}?</span>
              <span v-else>You've completed all 4 arcs of your webnovel!</span>
            </p>
            <div class="sf-arc-complete-actions">
              <button v-if="currentArc < 4" class="sf-btn sf-btn-primary" @click="startNextArc">
                Start Arc {{ currentArc + 1 }} — {{ arcName(currentArc + 1) }} →
              </button>
              <button class="sf-btn sf-btn-ghost" @click="showArcComplete = false">
                Keep editing Arc {{ currentArc }}
              </button>
            </div>
          </div>
        </div>

      </main>

    </div>
  </div>
</template>

<script>
const ARC_META = [
  { num: 1, name: 'Opening Arc',    color: '#0984E3', shortName: 'Opening'    },
  { num: 2, name: 'Rising Arc',     color: '#e17055', shortName: 'Rising'     },
  { num: 3, name: 'Escalation Arc', color: '#6c5ce7', shortName: 'Escalation' },
  { num: 4, name: 'Climax Arc',     color: '#d63031', shortName: 'Climax'     },
]

const BEAT_META = [
  { num: 1, name: 'Setup & Inciting Incident'    },
  { num: 2, name: 'Rising Action & Confrontation' },
  { num: 3, name: 'Climax & Resolution'           },
]

const STEPS = [
  { step: 1,  icon: '🎯', title: 'One-Sentence Hook',           arcLevel: true  },
  { step: 2,  icon: '📄', title: 'One-Paragraph Summary',       arcLevel: true  },
  { step: 3,  icon: '🎭', title: 'Character Summaries',         arcLevel: true  },
  { step: 4,  icon: '📝', title: 'Expanded 4-Para Summary',     arcLevel: true  },
  { step: 5,  icon: '🧬', title: 'Full Character Descriptions',  arcLevel: true  },
  { step: 6,  icon: '📖', title: 'Full Beat Synopsis',          arcLevel: false },
  { step: 7,  icon: '📊', title: 'Character Charts',            arcLevel: false },
  { step: 8,  icon: '🎬', title: 'Scene List',                  arcLevel: false },
  { step: 9,  icon: '✍️', title: 'Scene Narratives',            arcLevel: false },
  { step: 10, icon: '🖊️', title: 'First Draft',                 arcLevel: false },
]

export default {
  name: 'SnowflakeView',

  data() {
    return {
      currentArc: 1,
      currentBeat: 1,
      currentStep: 1,
      inputs: {},          // keyed by fieldKey()
      suggestion: '',
      isSuggesting: false,
      suggestError: '',
      showArcComplete: false,
      arcs: ARC_META,
      beats: BEAT_META,
      steps: STEPS,
      stepMeta: [],        // loaded from /api/snowflake/steps
    }
  },

  computed: {
    // The full metadata for the current step (from API or fallback to STEPS)
    currentStepMeta() {
      const fromApi = this.stepMeta.find(s => s.step === this.currentStep)
      if (fromApi) return { ...fromApi, icon: STEPS[this.currentStep - 1].icon }
      return STEPS[this.currentStep - 1]
    },

    // Current field key
    currentKey() {
      return this.fieldKey(this.currentArc, this.currentBeat, this.currentStep)
    },

    // Two-way binding for the current textarea
    currentValue: {
      get() { return this.inputs[this.currentKey] || '' },
      set(v) { this.inputs = { ...this.inputs, [this.currentKey]: v } },
    },

    // Arc-specific note for current step (arcs 2-4)
    currentArcNote() {
      const meta = this.stepMeta.find(s => s.step === this.currentStep)
      if (!meta || !meta.arc_note) return ''
      return meta.arc_note[this.currentArc] || ''
    },

    isLastStep() {
      return this.currentStep === 10 && this.currentArc === 4
    },

    // Overall progress
    totalFields() {
      // Steps 1-5: 1 field per arc (4 arcs)
      // Steps 6-10: 1 field per arc × per beat (4 arcs × 3 beats)
      return 4 * 5 + 4 * 3 * 5
    },
    completedCount() {
      return Object.values(this.inputs).filter(v => v && v.trim().length > 0).length
    },
    progressPct() {
      return Math.round((this.completedCount / this.totalFields) * 100)
    },
  },

  methods: {
    // ── Key helpers ───────────────────────────────────────────────────

    fieldKey(arc, beat, step) {
      // Steps 1-5 are arc-level (beat-independent)
      if (step <= 5) return `arc${arc}_step${step}`
      return `arc${arc}_beat${beat}_step${step}`
    },

    isStepFilled(arc, beat, step) {
      const v = this.inputs[this.fieldKey(arc, beat, step)]
      return !!(v && v.trim().length > 0)
    },

    // ── Arc helpers ───────────────────────────────────────────────────

    arcName(arcNum) {
      return ARC_META.find(a => a.num === arcNum)?.name || `Arc ${arcNum}`
    },

    arcColor(arcNum) {
      return ARC_META.find(a => a.num === arcNum)?.color || '#333'
    },

    beatName(beatNum) {
      return BEAT_META.find(b => b.num === beatNum)?.name || `Beat ${beatNum}`
    },

    arcTotalFields(arc) {
      return 5 + 3 * 5  // 5 arc-level + 15 beat-level
    },

    arcCompletedCount(arc) {
      let count = 0
      for (let s = 1; s <= 5; s++) {
        if (this.isStepFilled(arc, 1, s)) count++
      }
      for (let b = 1; b <= 3; b++) {
        for (let s = 6; s <= 10; s++) {
          if (this.isStepFilled(arc, b, s)) count++
        }
      }
      return count
    },

    arcProgressPct(arc) {
      return Math.round((this.arcCompletedCount(arc) / this.arcTotalFields(arc)) * 100)
    },

    // ── Navigation ────────────────────────────────────────────────────

    selectArc(arcNum) {
      this.currentArc = arcNum
      this.suggestion = ''
      this.showArcComplete = false
    },

    selectBeat(beatNum) {
      this.currentBeat = beatNum
      this.suggestion = ''
    },

    goToStep(stepNum) {
      this.currentStep = stepNum
      this.suggestion = ''
      // When switching to step 6+, ensure we're on a beat
      if (stepNum >= 6 && this.currentBeat < 1) this.currentBeat = 1
    },

    nextStep() {
      this.suggestion = ''
      if (this.currentStep < 10) {
        this.currentStep++
        // Auto-switch to beat-relevant context when entering beat steps
        if (this.currentStep === 6) this.currentBeat = 1
      } else {
        // End of arc
        if (this.currentArc < 4) {
          this.showArcComplete = true
        } else {
          this.showArcComplete = true
        }
      }
    },

    prevStep() {
      this.suggestion = ''
      if (this.currentStep > 1) {
        this.currentStep--
      } else if (this.currentArc > 1) {
        this.currentArc--
        this.currentStep = 10
        this.currentBeat = 3
      }
    },

    startNextArc() {
      this.showArcComplete = false
      this.currentArc++
      this.currentStep = 1
      this.currentBeat = 1
      this.suggestion = ''
    },

    // ── Input handling ────────────────────────────────────────────────

    onInput() {
      this.saveToStorage()
    },

    // ── AI Suggest ────────────────────────────────────────────────────

    async getSuggestion() {
      this.isSuggesting = true
      this.suggestError = ''
      this.suggestion = ''
      try {
        const res = await fetch('/api/snowflake/suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            arc: this.currentArc,
            beat: this.currentBeat,
            step: this.currentStep,
            all_inputs: this.inputs,
          }),
        })
        const data = await res.json()
        if (data.error) {
          this.suggestError = data.error
        } else {
          this.suggestion = data.suggestion || ''
        }
      } catch (e) {
        this.suggestError = `Request failed: ${e.message}`
      } finally {
        this.isSuggesting = false
      }
    },

    useSuggestion() {
      this.currentValue = this.suggestion
      this.suggestion = ''
      this.saveToStorage()
    },

    appendSuggestion() {
      const sep = this.currentValue.trim() ? '\n\n' : ''
      this.currentValue = this.currentValue + sep + this.suggestion
      this.suggestion = ''
      this.saveToStorage()
    },

    // ── Persistence ───────────────────────────────────────────────────

    saveToStorage() {
      try {
        localStorage.setItem('snowflake_inputs', JSON.stringify(this.inputs))
      } catch (_) {}
    },

    loadFromStorage() {
      try {
        const raw = localStorage.getItem('snowflake_inputs')
        if (raw) this.inputs = JSON.parse(raw)
      } catch (_) {}
    },

    clearAll() {
      if (!confirm('Clear all your saved Snowflake content? This cannot be undone.')) return
      this.inputs = {}
      localStorage.removeItem('snowflake_inputs')
    },

    // ── Step meta from API ────────────────────────────────────────────

    async loadStepMeta() {
      try {
        const res = await fetch('/api/snowflake/steps')
        if (res.ok) this.stepMeta = await res.json()
      } catch (_) {}
    },

    // ── Formatting ────────────────────────────────────────────────────

    formatInstruction(text) {
      if (!text) return ''
      return text
        .split('\n')
        .map(line => {
          if (line.startsWith('•')) return `<span class="sf-bullet">${line}</span>`
          if (/^\d+\./.test(line)) return `<span class="sf-numbered">${line}</span>`
          return line
        })
        .join('<br>')
    },
  },

  created() {
    this.loadFromStorage()
    this.loadStepMeta()
  },
}
</script>

<style scoped>
/* ── Layout ── */
.snowflake-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--bg-primary);
  font-family: var(--font-sans);
}

/* ── Header ── */
.sf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
  gap: 16px;
}

.sf-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sf-logo {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 0.5px;
}

.sf-subtitle {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.sf-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sf-progress-label {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.sf-progress-bar {
  width: 120px;
  height: 4px;
  background: var(--border-light);
  border-radius: 2px;
  overflow: hidden;
}

.sf-progress-fill {
  height: 100%;
  background: var(--accent-green);
  transition: width 0.3s ease;
}

/* ── Body ── */
.sf-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Sidebar ── */
.sf-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-light);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* Arc list */
.sf-arc-list {
  padding: 12px;
  border-bottom: 1px solid var(--border-light);
}

.sf-arc-item {
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  border: 1px solid transparent;
  transition: all 0.15s;
}

.sf-arc-item:hover {
  background: var(--bg-primary);
}

.sf-arc-item.active {
  background: var(--bg-primary);
  border-color: var(--border-light);
}

.sf-arc-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.sf-arc-badge {
  font-size: 9px;
  font-weight: 700;
  font-family: var(--font-mono);
  background: #000;
  color: #fff;
  padding: 2px 5px;
  border-radius: 3px;
  flex-shrink: 0;
}

.sf-arc-name {
  font-size: 12px;
  font-weight: 600;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sf-arc-fill {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.sf-arc-progress {
  height: 3px;
  background: var(--border-light);
  border-radius: 2px;
  overflow: hidden;
}

.sf-arc-prog-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}

/* Step list */
.sf-step-list {
  padding: 12px;
  flex: 1;
}

.sf-step-list-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-family: var(--font-mono);
}

.sf-step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.1s;
}

.sf-step-item:hover {
  background: var(--bg-primary);
}

.sf-step-item.active {
  background: #000;
  color: #fff;
}

.sf-step-item.done:not(.active) {
  color: var(--accent-green);
}

.sf-step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--border-light);
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-family: var(--font-mono);
}

.sf-step-item.active .sf-step-num {
  background: rgba(255,255,255,0.2);
  color: #fff;
}

.sf-step-item.done:not(.active) .sf-step-num {
  background: var(--accent-green);
  color: #fff;
}

.sf-step-icon {
  font-size: 13px;
  flex-shrink: 0;
}

.sf-step-name {
  font-size: 12px;
  font-weight: 500;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sf-step-check {
  font-size: 11px;
  color: var(--accent-green);
  flex-shrink: 0;
}

.sf-step-item.active .sf-step-check {
  color: #7effc4;
}

/* ── Main panel ── */
.sf-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
}

/* Beat bar */
.sf-beat-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
  flex-wrap: wrap;
}

.sf-beat-bar.visible {
  opacity: 1;
  pointer-events: all;
}

.sf-beat-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.sf-beat-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--border-light);
  border-radius: 20px;
  background: var(--bg-primary);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.sf-beat-btn:hover {
  border-color: #888;
  color: var(--text-main);
}

.sf-beat-btn.active {
  background: #000;
  color: #fff;
  border-color: #000;
}

.sf-beat-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(0,0,0,0.1);
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sf-beat-btn.active .sf-beat-num {
  background: rgba(255,255,255,0.2);
}

/* ── Step Card ── */
.sf-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.sf-card-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sf-card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sf-step-badge {
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-muted);
  background: var(--bg-primary);
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-light);
}

.sf-arc-tag {
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  padding: 3px 8px;
  border-radius: 4px;
}

.sf-beat-tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-primary);
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-light);
}

.sf-card-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-main);
  margin: 0;
}

/* Instruction */
.sf-instruction {
  background: #f8f9fa;
  border: 1px solid var(--border-light);
  border-left: 3px solid #000;
  border-radius: 4px;
  padding: 14px 16px;
}

.sf-instruction-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-family: var(--font-mono);
}

.sf-instruction-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

/* Arc note */
.sf-arc-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #fffbf0;
  border: 1px solid #f6d860;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 13px;
  color: #7a5c00;
  line-height: 1.5;
}

.sf-arc-note-icon {
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

/* Field */
.sf-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sf-field-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sf-field-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.sf-field-count {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.sf-textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-main);
  font-size: 13px;
  line-height: 1.7;
  font-family: var(--font-sans);
  resize: vertical;
  min-height: 220px;
  transition: border-color 0.15s;
}

.sf-textarea:focus {
  outline: none;
  border-color: #000;
}

.sf-textarea::placeholder {
  color: #bbb;
  font-style: italic;
}

/* Suggest row */
.sf-suggest-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sf-error {
  font-size: 12px;
  color: var(--accent-red);
}

/* Suggestion box */
.sf-suggestion-box {
  background: #f0f7ff;
  border: 1px solid #b8d9f8;
  border-radius: 8px;
  overflow: hidden;
}

.sf-suggestion-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #e3f0fd;
  border-bottom: 1px solid #b8d9f8;
  font-size: 12px;
  font-weight: 600;
  color: #1565c0;
  gap: 8px;
}

.sf-suggestion-actions {
  display: flex;
  gap: 6px;
}

.sf-suggestion-text {
  padding: 14px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-main);
  white-space: pre-wrap;
}

/* Navigation row */
.sf-nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 4px;
}

.sf-step-dots {
  display: flex;
  gap: 6px;
  align-items: center;
}

.sf-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border-light);
  cursor: pointer;
  transition: all 0.15s;
}

.sf-dot.active {
  background: #000;
  transform: scale(1.3);
}

.sf-dot.filled:not(.active) {
  background: var(--accent-green);
}

/* ── Buttons ── */
.sf-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  white-space: nowrap;
}

.sf-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.sf-btn-primary {
  background: #000;
  color: #fff;
  border-color: #000;
}

.sf-btn-primary:hover:not(:disabled) {
  background: #222;
}

.sf-btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--border-light);
}

.sf-btn-ghost:hover:not(:disabled) {
  border-color: #888;
  color: var(--text-main);
}

.sf-btn-suggest {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-color: transparent;
  min-width: 140px;
  justify-content: center;
}

.sf-btn-suggest:hover:not(:disabled) {
  opacity: 0.9;
}

.sf-btn-small {
  padding: 4px 10px;
  font-size: 11px;
}

/* Loading animation */
.sf-loading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sf-dot-anim {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.7);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.4; transform: scale(0.7); }
}

/* ── Arc complete banner ── */
.sf-arc-complete {
  position: absolute;
  inset: 0;
  background: rgba(248,249,250,0.96);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.sf-arc-complete-inner {
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  padding: 40px 48px;
  text-align: center;
  max-width: 480px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.08);
}

.sf-arc-complete-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.sf-arc-complete-inner h3 {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 12px;
}

.sf-arc-complete-inner p {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
}

.sf-arc-complete-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

/* Instruction text helpers */
:deep(.sf-bullet) {
  display: block;
  padding-left: 8px;
}

:deep(.sf-numbered) {
  display: block;
  padding-left: 8px;
  font-weight: 500;
}
</style>
