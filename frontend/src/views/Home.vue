<template>
  <div class="home">
    <div class="hero">
      <div class="hero-icon">🐟</div>
      <h1 class="hero-title">NOVEL SWARM</h1>
      <p class="hero-sub">SWARM INTELLIGENCE STORY ENGINE</p>
      <p class="hero-desc">
        Upload your lore. Spawn autonomous agents grounded in your world.
        Watch them debate, argue, expand, and synthesize through emergent social interaction.
      </p>
    </div>

    <div class="form-container">
      <!-- Project Name -->
      <div class="field">
        <label>PROJECT NAME</label>
        <input v-model="projectName" placeholder="The Sovereignty of Ash" />
      </div>

      <!-- Mode -->
      <div class="field">
        <label>WORKSHOP MODE</label>
        <div class="mode-grid">
          <button @click="mode = 'lore'" :class="{ active: mode === 'lore' }">
            <span class="mode-icon">🌍</span>
            <span class="mode-label">Lore Enhancement</span>
            <span class="mode-desc">Deepen your world</span>
          </button>
          <button @click="mode = 'outline'" :class="{ active: mode === 'outline' }">
            <span class="mode-icon">📋</span>
            <span class="mode-label">Outline Generation</span>
            <span class="mode-desc">Build chapter structure</span>
          </button>
        </div>
      </div>

      <!-- Lore Input -->
      <div class="field">
        <label>SEED MATERIAL — Your Lore</label>
        <textarea v-model="lore" rows="12"
          placeholder="Paste your world lore, story bible, magic systems, character notes, setting details — everything the swarm should know..."></textarea>
      </div>

      <!-- Config -->
      <div class="config-grid">
        <div class="field">
          <label>SWARM SIZE: {{ agentCount }} AGENTS</label>
          <input type="range" min="4" max="30" v-model.number="agentCount" />
          <div class="range-labels"><span>4 (focused)</span><span>30 (swarm)</span></div>
        </div>
        <div class="field">
          <label>ROUNDS: {{ rounds }}</label>
          <input type="range" min="5" max="40" v-model.number="rounds" />
          <div class="range-labels"><span>5 (quick)</span><span>40 (deep)</span></div>
        </div>
        <div class="field">
          <label>CRITICS RATIO: {{ Math.round(criticsRatio * 100) }}%</label>
          <input type="range" min="20" max="80" v-model.number="criticsPercent" />
          <div class="range-labels"><span>20% critics</span><span>80% critics</span></div>
        </div>
      </div>

      <!-- Status -->
      <div v-if="status" class="status-bar" :class="{ error: isError }">
        <div v-if="loading" class="spinner"></div>
        {{ status }}
      </div>

      <!-- Action -->
      <button @click="startPipeline" :disabled="!lore.trim() || loading" class="cta-button">
        🐟 SPAWN SWARM
      </button>
      <p class="cta-hint">
        ~{{ agentCount * rounds }} LLM calls • Entity extraction via GraphRAG • Neo4j knowledge graph
      </p>
    </div>

    <!-- History -->
    <div v-if="projects.length" class="history">
      <h3>Previous Projects</h3>
      <div v-for="p in projects" :key="p.id" class="history-item" @click="$router.push(`/graph/${p.id}`)">
        <span class="history-name">{{ p.name }}</span>
        <span class="history-mode">{{ p.mode }}</span>
        <span class="history-date">{{ new Date(p.created_at * 1000).toLocaleDateString() }}</span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      projectName: '',
      mode: 'lore',
      lore: '',
      agentCount: 12,
      rounds: 20,
      criticsPercent: 50,
      loading: false,
      status: '',
      isError: false,
      projects: [],
    }
  },
  computed: {
    criticsRatio() { return this.criticsPercent / 100 }
  },
  async mounted() {
    try {
      const res = await fetch('/api/projects/')
      this.projects = await res.json()
    } catch {}
  },
  methods: {
    async startPipeline() {
      this.loading = true
      this.isError = false

      try {
        // Stage 0: Create project
        this.status = 'Creating project...'
        const projRes = await fetch('/api/projects/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.projectName || 'Untitled',
            mode: this.mode,
            lore_text: this.lore,
          }),
        })
        const project = await projRes.json()

        // Stage 1a: Extract entities
        this.status = 'Extracting entities from lore (GraphRAG)...'
        const extractRes = await fetch('/api/graph/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lore_text: this.lore }),
        })
        const extraction = await extractRes.json()
        this.status = `Found ${extraction.entity_count} entities, ${extraction.relationship_count} relationships`

        // Stage 1b: Build knowledge graph in Neo4j
        this.status = 'Building knowledge graph in Neo4j...'
        await fetch('/api/graph/build', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: project.id,
            entities: extraction.entities,
            relationships: extraction.relationships,
          }),
        })

        this.status = 'Done! Navigating to graph view...'
        setTimeout(() => {
          this.$router.push(`/graph/${project.id}`)
        }, 500)

      } catch (err) {
        this.status = `Error: ${err.message}`
        this.isError = true
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.home {
  padding: 48px 20px;
  max-width: 720px;
  margin: 0 auto;
}

.hero { text-align: center; margin-bottom: 48px; }
.hero-icon { font-size: 56px; margin-bottom: 12px; }
.hero-title {
  font-family: var(--font-display);
  font-size: 42px;
  font-weight: 900;
  background: linear-gradient(135deg, var(--accent-gold), var(--accent-rose), var(--accent-purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 4px;
  margin-bottom: 6px;
}
.hero-sub {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 3px;
}
.hero-desc {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 16px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.7;
}

.form-container { display: flex; flex-direction: column; gap: 24px; }

.field label {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 2px;
  margin-bottom: 8px;
}

.field input[type="text"], .field input:not([type]), .field textarea {
  width: 100%;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 18px;
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.8;
  resize: vertical;
}
.field input:focus, .field textarea:focus {
  outline: none;
  border-color: var(--accent-gold);
  box-shadow: 0 0 20px rgba(232, 168, 56, 0.1);
}
.field textarea::placeholder { color: #2a2a35; }

.field input[type="range"] {
  width: 100%;
  accent-color: var(--accent-gold);
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 9px;
  color: #2a2a35;
  margin-top: 4px;
}

.mode-grid { display: flex; gap: 10px; }
.mode-grid button {
  flex: 1;
  padding: 18px;
  border-radius: 14px;
  cursor: pointer;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-muted);
  text-align: center;
  transition: all 0.25s;
}
.mode-grid button.active {
  border-color: rgba(232, 168, 56, 0.3);
  color: var(--text-primary);
  box-shadow: 0 0 30px rgba(232, 168, 56, 0.08);
}
.mode-icon { display: block; font-size: 28px; margin-bottom: 8px; }
.mode-label { display: block; font-family: var(--font-mono); font-size: 12px; font-weight: 600; }
.mode-desc { display: block; font-size: 11px; color: var(--text-muted); margin-top: 4px; }

.config-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }

.status-bar {
  padding: 12px 16px;
  border-radius: 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-gold);
  display: flex;
  align-items: center;
  gap: 10px;
}
.status-bar.error { color: var(--accent-red); border-color: rgba(214, 48, 49, 0.3); }

.spinner {
  width: 16px; height: 16px;
  border: 2px solid var(--border);
  border-top: 2px solid var(--accent-gold);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.cta-button {
  width: 100%;
  padding: 18px;
  border-radius: 14px;
  border: none;
  cursor: pointer;
  background: linear-gradient(135deg, var(--accent-gold), var(--accent-rose));
  color: #fff;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 3px;
  transition: all 0.3s;
  box-shadow: 0 4px 30px rgba(232, 168, 56, 0.2);
}
.cta-button:disabled {
  background: var(--bg-elevated);
  color: var(--text-muted);
  box-shadow: none;
  cursor: default;
}
.cta-hint {
  text-align: center;
  font-family: var(--font-mono);
  font-size: 10px;
  color: #2a2a35;
  margin-top: 8px;
}

.history { margin-top: 48px; }
.history h3 {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 2px;
  margin-bottom: 12px;
}
.history-item {
  display: flex;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  font-family: var(--font-mono);
  font-size: 12px;
}
.history-item:hover { background: var(--bg-elevated); }
.history-name { color: var(--text-primary); flex: 1; }
.history-mode { color: var(--accent-gold); }
.history-date { color: var(--text-muted); }
</style>
