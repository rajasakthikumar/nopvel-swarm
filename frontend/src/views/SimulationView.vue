<template>
  <div class="sim-view">
    <!-- Left: Agent Roster -->
    <div class="roster">
      <div class="roster-header">
        <span class="roster-title">🐟 AGENTS</span>
        <span class="roster-stat">{{ agents.length }} • {{ posts.length }} posts</span>
      </div>
      <button @click="filterAgent = null" :class="{ active: !filterAgent }" class="filter-btn">
        ALL ({{ posts.length }})
      </button>
      <div class="agent-list">
        <div v-for="a in agents" :key="a.id" class="agent-row"
             :class="{ active: filterAgent === a.id, speaking: currentAgent?.agent_id === a.id }"
             @click="filterAgent = filterAgent === a.id ? null : a.id">
          <span class="agent-avatar">{{ a.avatar }}</span>
          <div class="agent-info">
            <div class="agent-name">{{ a.name }}</div>
            <div class="agent-meta">
              {{ a.role }} • {{ a.location_id || 'root' }}
            </div>
            <div v-if="a.health !== undefined" class="agent-health-mini">
              <div class="health-track">
                <div class="health-fill" :style="{ width: a.health + '%', background: getHealthColor(a.health) }"></div>
              </div>
            </div>
            <div v-if="a.current_goal" class="agent-goal-mini">🎯 {{ a.current_goal }}</div>
          </div>
          <div class="stance-dot" :style="{ background: stanceColor(a.stance) }"></div>
        </div>
      </div>
    </div>

    <!-- Main Feed -->
    <div class="feed-area">
      <div class="feed-header">
        <div class="feed-status">
          <span class="status-badge" :class="{ live: running, paused: paused }">
            {{ running ? (paused ? '⏸ PAUSED' : '● LIVE') : '○ IDLE' }}
          </span>
          <span class="status-text">R{{ currentRound + 1 }}/{{ rounds }} • {{ statusMsg }}</span>
        </div>
        <div class="feed-controls">
          <template v-if="!started">
            <button @click="prepareAndStart('lore')" :disabled="preparing" class="ctrl-btn start">
              {{ preparing ? 'Preparing...' : '🐟 START SIMULATION' }}
            </button>
            <button @click="prepareAndStart('event_tick')" :disabled="preparing" class="ctrl-btn event-tick" title="Agents take physical actions in the world">
              {{ preparing ? 'Preparing...' : '⚔️ IN-WORLD SIMULATION' }}
            </button>
          </template>
          <template v-else-if="running">
            <button @click="togglePause" class="ctrl-btn">{{ paused ? '▶ RESUME' : '⏸ PAUSE' }}</button>
            <button @click="branchReality" class="ctrl-btn synth" :disabled="branching">
              {{ branching ? 'BRANCHING...' : '🌌 BRANCH REALITY' }}
            </button>
            <button @click="stopSim" class="ctrl-btn stop">⏹ STOP</button>
          </template>
          <template v-else>
            <button @click="synthesize" :disabled="synthesizing" class="ctrl-btn synth">
              {{ synthesizing ? '✨ SYNTHESIZING...' : '✨ SYNTHESIZE' }}
            </button>
          </template>
        </div>
      </div>

      <!-- Platform Tabs -->
      <div class="platform-tabs">
        <button @click="platformFilter = null; showMap = false" :class="{ active: !platformFilter && !showMap }">ALL</button>
        <button @click="platformFilter = 'critics_forum'; showMap = false" :class="{ active: platformFilter === 'critics_forum' }">
          📖 Critics' Forum
        </button>
        <button @click="platformFilter = 'inworld_forum'; showMap = false" :class="{ active: platformFilter === 'inworld_forum' }">
          🌍 In-World Forum
        </button>
        <button @click="showWorldBuilder = !showWorldBuilder" class="ctrl-btn event-tick">
          🛠️ WORLD BUILDER
        </button>
        <button @click="paused = !paused" :class="{ 'ctrl-btn pause': true, 'active': paused }">
          {{ paused ? '▶️ RESUME' : '⏸️ PAUSE' }}
        </button>
      </div>

      <!-- Chronicle Modal -->
      <div v-if="showChronicle" class="chronicle-overlay">
        <div class="chronicle-modal">
          <h2>📜 Chronicle of the Age</h2>
          <div class="chronicle-text">{{ chronicleContent }}</div>
          <button @click="showChronicle = false" class="ctrl-btn">CLOSE</button>
        </div>
      </div>

      <!-- World Builder Panel -->
      <div v-if="showWorldBuilder" class="world-builder-panel">
        <h3>🌍 Insert World Entity</h3>
        <select v-model="worldInsert.type">
          <option value="character">Character</option>
          <option value="kingdom">Kingdom/Nation</option>
          <option value="religion">Religion/Cult</option>
          <option value="fauna">Fauna/Creature</option>
        </select>
        <input v-model="worldInsert.name" placeholder="Entity Name" />
        <textarea v-model="worldInsert.description" placeholder="Short description..."></textarea>
        <button @click="insertWorldEntity" class="ctrl-btn start">INSERT INTO REALITY</button>
      </div>

      <!-- World Map Overlay -->
      <div v-if="showMap" class="world-map">
        <div class="map-grid">
          <div v-for="loc in uniqueLocations" :key="loc" class="map-node">
            <div class="loc-name">{{ loc || 'Wilderness' }}</div>
            <div class="loc-agents">
              <span v-for="a in getAgentsAt(loc)" :key="a.id" class="map-agent" :title="a.name">
                {{ a.avatar }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Posts -->
      <div class="post-feed" ref="feed">
        <div v-for="p in filteredPosts" :key="p.id" class="post"
             :style="{ borderLeftColor: p.is_injection ? '#FFD93D' : actionColor(p.action) }">
          <div class="post-header">
            <span v-if="p.is_injection" class="post-author injection">⚡ Author Injection</span>
            <template v-else>
              <span class="post-author">{{ p.author_name }}</span>
              <span class="action-badge" :style="{ color: actionColor(p.action), background: actionColor(p.action) + '18' }">
                {{ p.action }}
              </span>
              <span class="post-platform">{{ p.platform === 'critics_forum' ? '📖' : '🌍' }}</span>
              <span class="post-round">R{{ p.round + 1 }}</span>
            </template>
          </div>
          <div v-if="p.is_injection" class="post-text injection-text">{{ p.text }}</div>
          <div v-else class="post-text">{{ p.text }}</div>
        </div>

        <div v-for="(dev, idx) in directorEvents" :key="idx" class="director-card">
          <div class="director-header">🎬 DIRECTORS NOTE — ROUND {{ currentRound }}</div>
          <div class="director-body">{{ dev.summary }}</div>
          <div class="director-event">{{ dev.event }}</div>
          <div v-if="dev.cliffhanger" class="director-cliff">⚡ CLIFFHANGER: {{ dev.cliffhanger }}</div>
          <div v-if="dev.progression_unlock" class="director-prog">📈 PROGRESSION: {{ dev.progression_unlock }}</div>
          <div v-if="dev.new_mystery" class="director-mystery">🔍 MYSTERY: {{ dev.new_mystery }}</div>
        </div>

        <div v-if="currentAgent && running" class="typing-indicator">
          <span>{{ currentAgent.avatar }} {{ currentAgent.agent_name }}</span>
          <span class="typing-action">{{ currentAgent.action }}</span>
          <span class="typing-dots">✍️</span>
        </div>
        <div ref="feedEnd"></div>
      </div>

      <!-- Injection Bar -->
      <div class="injection-bar">
        <div class="inject-dot" :class="{ live: running && !paused, paused, idle: !running }"></div>
        <input v-model="injectionText" @keydown.enter="inject"
               placeholder="⚡ God's Eye — inject a variable, redirect the swarm..." />
        <button @click="inject" :disabled="!injectionText.trim()">INJECT ⚡</button>
      </div>
    </div>
  </div>
</template>

<script>
const ACTION_COLORS = {
  post: '#E8A838', reply: '#0984E3', agree: '#00B894', disagree: '#E17055',
  expand: '#6C5CE7', challenge: '#D63031', synthesize: '#C75B7A',
  foreshadow: '#FDCB6E', callback: '#636E72', worldbuild: '#00B894',
  characterize: '#E8A838', conflict: '#D63031', resolve: '#00B894',
  theme: '#6C5CE7', outline: '#0984E3', injection: '#FFD93D',
}
const STANCE_COLORS = {
  strongly_positive: '#00B894', positive: '#55EFC4', neutral: '#636E72',
  negative: '#E17055', strongly_negative: '#D63031',
}

export default {
  name: 'SimulationView',
  props: ['projectId'],
  data() {
    return {
      agents: [], posts: [], started: false, running: false, paused: false,
      currentAgent: null, currentRound: 0, rounds: 20,
      statusMsg: '', filterAgent: null, platformFilter: null,
      injectionText: '', preparing: false, synthesizing: false, branching: false,
      eventSource: null, loreText: '', mode: 'lore',
      showMap: false, locations: [],
      directorEvents: [], showChronicle: false, chronicleContent: '',
      showHeatmap: false, heatmapData: { nodes: [], links: [] },
      worldInsert: { type: 'kingdom', name: '', description: '' },
      showWorldBuilder: false,
    }
  },
  computed: {
    uniqueLocations() {
      const locs = new Set(this.agents.map(a => a.location_id))
      return Array.from(locs)
    },
    filteredPosts() {
      let p = this.posts
      if (this.filterAgent) p = p.filter(x => x.author_id === this.filterAgent || x.is_injection)
      if (this.platformFilter) p = p.filter(x => x.platform === this.platformFilter || x.is_injection)
      return p
    }
  },
  async mounted() {
    // Load project data
    try {
      const res = await fetch(`/api/projects/${this.projectId}`)
      const proj = await res.json()
      this.loreText = proj.lore_text || ''
      this.mode = proj.mode || 'lore'
    } catch {}
  },
  beforeUnmount() {
    if (this.eventSource) this.eventSource.close()
  },
  methods: {
    getAgentsAt(locId) {
      return this.agents.filter(a => a.location_id === locId)
    },
    getHealthColor(h) {
      if (h > 70) return '#00B894'
      if (h > 30) return '#FFD93D'
      return '#E17055'
    },
    actionColor(a) { return ACTION_COLORS[a] || '#636E72' },
    stanceColor(s) { return STANCE_COLORS[s] || '#636E72' },
    async insertWorldEntity() {
      if (!this.worldInsert.name) return
      try {
        await fetch('/api/simulation/world-insert', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: this.projectId,
            ...this.worldInsert
          })
        })
        this.worldInsert.name = ''
        this.worldInsert.description = ''
        this.showWorldBuilder = false
      } catch (e) {
        alert('Failed to insert: ' + e)
      }
    },
    scrollToBottom() {
      this.$nextTick(() => this.$refs.feedEnd?.scrollIntoView({ behavior: 'smooth' }))
    },
    async prepareAndStart(simMode = 'lore') {
      this.preparing = true
      this.statusMsg = 'Generating agent personas...'
      this.mode = simMode

      // Prepare agents
      const prepRes = await fetch('/api/simulation/prepare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: this.projectId, agent_count: 12, critics_ratio: 0.5 }),
      })
      const prep = await prepRes.json()
      this.agents = prep.agents
      this.statusMsg = `${prep.count} agents ready (${prep.critics} critics, ${prep.inworld} in-world)`

      // Start simulation
      await fetch('/api/simulation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: this.projectId,
          mode: this.mode,
          rounds: this.rounds,
          lore_text: this.loreText,
          agents: this.agents,
        }),
      })

      this.started = true
      this.preparing = false
      this.connectSSE()
    },
    connectSSE() {
      if (this.eventSource) this.eventSource.close()
      this.eventSource = new EventSource('/api/simulation/events')
      this.eventSource.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        switch (msg.type) {
          case 'sim_start': this.running = true; break
          case 'round_start': this.currentRound = msg.data.round; break
          case 'agent_start':
            this.currentAgent = msg.data
            this.statusMsg = `${msg.data.agent_name} → ${msg.data.action}`
            break
          case 'agent_post':
            this.posts.push(msg.data.post)
            if (msg.data.agent_update) {
              const idx = this.agents.findIndex(a => a.id === msg.data.agent_update.id)
              if (idx >= 0) Object.assign(this.agents[idx], msg.data.agent_update)
            }
            this.scrollToBottom()
            break
          case 'injection': this.posts.push(msg.data.post || msg.data); this.scrollToBottom(); break
          case 'director_event':
            this.directorEvents.push(msg.data)
            this.statusMsg = `🎬 DIRECTOR: ${msg.data.summary}`
            break
          case 'chronicle_ready':
            this.chronicleContent = msg.data.content
            this.showChronicle = true
            break
          case 'round_end': this.statusMsg = `Round ${msg.data.round + 1} complete`; break
          case 'sim_end':
            this.running = false; this.currentAgent = null
            this.statusMsg = `Done — ${msg.data.total_posts} posts`
            break
        }
      }
    },
    async togglePause() {
      try {
        await fetch('/api/simulation/pause', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: this.projectId })
        })
        this.paused = !this.paused
      } catch {}
    },
    async inject() {
      if (!this.injectionText.trim()) return
      await fetch('/api/simulation/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: this.injectionText }),
      })
      this.injectionText = ''
    },
    async togglePause() {
      const res = await fetch('/api/simulation/pause', { method: 'POST' })
      const data = await res.json()
      this.paused = data.paused
    },
    async stopSim() {
      await fetch('/api/simulation/stop', { method: 'POST' })
      this.running = false
    },
    async branchReality() {
      if (this.branching) return;
      this.branching = true;
      try {
        const res = await fetch('/api/simulation/branch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: this.projectId })
        });
        const data = await res.json();
        if (data.new_project_id) {
          // Navigate to the new project simulation
          this.$router.push(`/sim/${data.new_project_id}`);
          window.location.reload(); // Force full reload to disconnect old SSE and start fresh
        }
      } catch (e) {
        console.error("Failed to branch reality:", e);
      } finally {
        this.branching = false;
      }
    },
    async synthesize() {
      this.synthesizing = true
      this.statusMsg = 'ReportAgent analyzing all interactions...'
      const res = await fetch('/api/report/synthesize', { method: 'POST' })
      const data = await res.json()
      this.synthesizing = false
      this.statusMsg = `Report generated (${data.sections?.length || 0} sections, ${data.tool_calls || 0} tool calls)`
      this.$router.push(`/report/${this.projectId}`)
    },
  },
  watch: {
    posts() { this.scrollToBottom() }
  }
}
</script>

<style scoped>
.sim-view { 
  display: flex; 
  height: calc(100vh - 50px); 
  overflow: hidden;
  max-width: 100vw;
}

.roster {
  width: 230px; 
  border-right: 1px solid var(--border); 
  display: flex;
  flex-direction: column; 
  background: var(--bg-secondary); 
  flex-shrink: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}
.roster-header { padding: 12px 14px; border-bottom: 1px solid var(--border); }
.roster-title { font-family: var(--font-display); font-size: 13px; color: var(--accent-gold); }
.roster-stat { display: block; font-family: var(--font-mono); font-size: 9px; color: var(--text-muted); margin-top: 2px; }
.filter-btn {
  margin: 8px 10px; padding: 6px 10px; border-radius: 6px; border: none;
  background: transparent; color: var(--text-muted); cursor: pointer;
  font-family: var(--font-mono); font-size: 10px; text-align: left;
}
.filter-btn.active { background: var(--bg-elevated); color: var(--accent-gold); }
.agent-list { flex: 1; overflow-y: auto; padding: 4px 6px; }
.agent-row {
  display: flex; align-items: center; gap: 6px; padding: 5px 8px;
  border-radius: 6px; cursor: pointer; transition: background 0.2s;
  border-left: 2px solid transparent;
}
.agent-row:hover { background: var(--bg-elevated); }
.agent-row.active { background: var(--bg-elevated); border-left-color: var(--accent-gold); }
.agent-row.speaking { border-left-color: var(--accent-green); }
.agent-avatar { font-size: 14px; }
.agent-info { flex: 1; min-width: 0; }
.agent-name { font-family: var(--font-mono); font-size: 10px; font-weight: 600; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-meta { font-size: 8px; color: var(--text-muted); opacity: 0.8; }
.agent-health-mini { margin-top: 3px; height: 2px; background: rgba(0,0,0,0.2); border-radius: 2px; overflow: hidden; }
.health-fill { height: 100%; transition: width 0.3s; }
.agent-goal-mini { font-size: 8px; color: var(--accent-gold); font-style: italic; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stance-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }

.feed-area { 
  flex: 1; 
  display: flex; 
  flex-direction: column; 
  min-width: 0; 
  height: 100%;
  overflow: hidden;
}

.feed-header {
  padding: 10px 20px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
}
.feed-status { display: flex; align-items: center; gap: 10px; }
.status-badge {
  font-family: var(--font-mono); font-size: 10px; padding: 3px 10px;
  border-radius: 10px; background: var(--bg-elevated); color: var(--text-muted);
  border: 1px solid var(--border);
}
.status-badge.live { color: var(--accent-gold); border-color: rgba(232,168,56,0.3); }
.status-badge.paused { color: var(--accent-orange); }
.status-text { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); }

.feed-controls { display: flex; gap: 6px; }
.ctrl-btn {
  padding: 6px 14px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg-elevated); color: var(--text-secondary); cursor: pointer;
  font-family: var(--font-mono); font-size: 10px; font-weight: 600;
}
.ctrl-btn.start { background: linear-gradient(135deg, var(--accent-gold), var(--accent-rose)); color: #fff; border: none; }
.ctrl-btn.event-tick { background: linear-gradient(135deg, #0984E3, #6C5CE7); color: #fff; border: none; }
.ctrl-btn.stop { color: var(--accent-red); border-color: rgba(214,48,49,0.3); }
.ctrl-btn.synth { background: linear-gradient(135deg, var(--accent-gold), var(--accent-rose)); color: #fff; border: none; }

.platform-tabs {
  padding: 6px 20px; border-bottom: 1px solid var(--border); display: flex; gap: 4px;
}
.platform-tabs button {
  padding: 4px 12px; border-radius: 6px; border: none;
  background: transparent; color: var(--text-muted); cursor: pointer;
  font-family: var(--font-mono); font-size: 10px;
}
.platform-tabs button.active { background: var(--bg-elevated); color: var(--accent-gold); }

.post-feed { 
  flex: 1; 
  overflow-y: auto; 
  overflow-x: hidden;
  padding: 14px 20px; 
  display: flex; 
  flex-direction: column; 
  gap: 10px; 
  min-height: 0;
}
.post {
  padding: 12px 16px; border-radius: 12px; background: var(--bg-secondary);
  border-left: 3px solid var(--text-muted);
}
.post-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.post-author { font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--text-primary); }
.post-author.injection { color: #FFD93D; }
.action-badge {
  font-family: var(--font-mono); font-size: 9px; font-weight: 600;
  padding: 2px 8px; border-radius: 10px;
}
.post-platform { font-size: 12px; }
.post-round { font-family: var(--font-mono); font-size: 9px; color: var(--text-muted); }
.post-text { font-size: 13.5px; line-height: 1.8; color: #c8c8d0; white-space: pre-wrap; }
.injection-text { color: #FFD93D; }

.typing-indicator {
  padding: 10px 16px; border-radius: 12px; background: var(--bg-secondary);
  border-left: 3px solid var(--accent-gold); display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono); font-size: 12px; color: var(--accent-gold);
}
.typing-action { font-size: 9px; color: var(--text-muted); }
.typing-dots { animation: pulse 0.8s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.injection-bar {
  padding: 12px 20px; border-top: 1px solid var(--border);
  display: flex; gap: 10px; align-items: center;
}
.inject-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-muted); flex-shrink: 0; }
.inject-dot.live { background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); }
.inject-dot.paused { background: var(--accent-orange); }
.injection-bar input {
  flex: 1; background: var(--bg-secondary); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 14px; color: var(--text-primary);
  font-family: var(--font-body); font-size: 13px;
}
.injection-bar button {
  padding: 10px 18px; border-radius: 10px; border: none;
  background: #FFD93D; color: #000; font-family: var(--font-mono);
  font-size: 11px; font-weight: 700; cursor: pointer; letter-spacing: 1px;
}
.injection-bar button:disabled { background: var(--bg-elevated); color: var(--text-muted); }

/* World Map Styles */
.world-map {
  flex: 1;
  background: var(--bg-secondary);
  overflow-y: auto;
  padding: 20px;
}
.map-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 15px;
}
.map-node {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-height: 80px;
  transition: transform 0.2s;
}
.map-node:hover { transform: translateY(-2px); border-color: var(--accent-gold); }
.loc-name { font-family: var(--font-display); font-size: 11px; color: var(--accent-gold); text-align: center; }
.loc-agents { display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; }
.map-agent { font-size: 16px; cursor: help; }

/* Chronicle & World Builder Styles */
.chronicle-overlay {
  position: absolute; top:0; left:0; right:0; bottom:0;
  background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 1000;
  backdrop-filter: blur(10px);
}
.chronicle-modal {
  width: 80%; max-width: 800px; background: var(--bg-elevated); padding: 40px;
  border-radius: 20px; border: 1px solid var(--accent-gold); max-height: 80vh; overflow-y: auto;
}
.chronicle-text {
  font-family: var(--font-display); font-size: 18px; line-height: 1.6; color: var(--text-primary);
  white-space: pre-wrap; margin: 20px 0;
}
.world-builder-panel {
  padding: 20px; background: var(--bg-elevated); border-bottom: 2px solid var(--accent-gold);
  display: flex; gap: 10px; align-items: center;
}
.world-builder-panel input, .world-builder-panel select, .world-builder-panel textarea {
  background: var(--bg-secondary); border: 1px solid var(--border); color: var(--text-primary);
  padding: 10px; border-radius: 8px;
}

/* Animations for Visual Feedback */
.post { animation: slideIn 0.3s ease-out; }
@keyframes slideIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}

.director-card {
  background: rgba(108, 92, 231, 0.15);
  border: 1px solid #6C5CE7;
  border-left: 5px solid #6C5CE7;
  border-radius: 12px;
  padding: 15px;
  margin: 15px 0;
  color: var(--text-primary);
}
.director-header {
  font-family: var(--font-mono); font-size: 10px; color: #a29bfe; font-weight: bold;
  margin-bottom: 8px; letter-spacing: 1px;
}
.director-body { font-size: 14px; font-weight: 500; font-style: italic; margin-bottom: 6px; }
.director-event { font-size: 13px; color: #fab1a0; font-family: var(--font-display); margin-bottom: 8px; }
.director-cliff { font-size: 11px; color: #ff7675; font-weight: bold; margin-top: 4px; border-top: 1px solid rgba(255,118,117,0.2); padding-top: 4px; }
.director-prog { font-size: 11px; color: #55efc4; font-weight: bold; margin-top: 4px; }
.director-mystery { font-size: 11px; color: #ffeaa7; font-weight: bold; margin-top: 4px; }

.ctrl-btn.pause { background: #E17055; color: white; }
.ctrl-btn.pause.active { background: #00B894; }

</style>
