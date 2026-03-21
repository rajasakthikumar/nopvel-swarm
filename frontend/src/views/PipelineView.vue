<template>
  <div class="pipeline">
    <!-- Seed Input (if not started) -->
    <div v-if="!started" class="seed-section">
      <div class="hero">
        <div class="hero-icon">🐟</div>
        <h1>NOVEL SWARM</h1>
        <p class="hero-sub">Give me a seed. I'll build the world.</p>
      </div>
      <div class="seed-input-area">
        <textarea v-model="seed" rows="4" placeholder="A disabled prince in a crumbling empire discovers he's the only one who can wield forbidden ash magic that feeds on suffering..."></textarea>
        <div class="config-row">
          <label>Chapters: <input type="number" v-model.number="chapterCount" style="width: 60px" /> </label>
          <label>Genres: <input type="text" v-model="genres" placeholder="Action, Thriller, Romance..." style="flex: 1" /> </label>
        </div>
        <div class="config-row">
          <label style="width: 100%">Actual Ending: <textarea v-model="actualEnding" placeholder="Describe the specific ending you want..." rows="2" style="width: 100%; margin-top: 5px;"></textarea></label>
        </div>
        <div class="config-row">
          <label>Pacing: 
            <select v-model="pacing">
              <option value="slow">Slow Burn</option>
              <option value="balanced">Balanced</option>
              <option value="fast">Fast-Paced</option>
              <option value="thriller">Breakneck</option>
            </select>
          </label>
          <label>Mood: 
            <select v-model="mood">
              <option value="grimdark">Grimdark</option>
              <option value="dark">Dark</option>
              <option value="neutral">Neutral</option>
              <option value="hopeful">Hopeful</option>
              <option value="whimsical">Whimsical</option>
            </select>
          </label>
        </div>
        <div class="config-row">
          <label><input type="checkbox" v-model="godMode" /> ⚡ GOD MODE (Auto-pause between world layers for review/injection)</label>
        </div>
        <button @click="startPipeline" :disabled="!seed.trim()" class="start-btn">🐟 BUILD MY WORLD</button>
      </div>
    </div>

    <!-- Pipeline Progress -->
    <div v-else class="progress-area">
      <!-- Phase indicator -->
      <div class="phase-bar">
        <div v-for="(p, i) in phases" :key="i" class="phase-step" :class="{ active: currentPhaseIndex === i, done: i < currentPhaseIndex, pending: i > currentPhaseIndex }">
          <span class="phase-icon">{{ p.icon }}</span>
          <span class="phase-label">{{ p.label }}</span>
        </div>
      </div>

      <div class="pipeline-controls" style="text-align: center; margin: 10px 0;">
        <button v-if="!isPaused" @click="pausePipeline" class="control-btn warning" style="background:#f39c12;border:none;padding:10px 20px;color:white;cursor:pointer;border-radius:6px;font-weight:bold;">⏸ PAUSE PIPELINE</button>
        <button v-else @click="resumePipeline" class="control-btn success" style="background:#2ecc71;border:none;padding:10px 20px;color:white;cursor:pointer;border-radius:6px;font-weight:bold;">▶ RESUME PIPELINE</button>
        
        <label style="margin-left: 20px; font-family: var(--font-mono); font-size: 12px; color: var(--accent-gold); cursor: pointer;">
          <input type="checkbox" v-model="godMode" @change="toggleGodMode" /> ⚡ GOD MODE
        </label>
      </div>

      <div class="pipeline-split">
        <!-- left: live generation & debate feed -->
        <div class="mirofish-panel">
          <h3>⚡ Live Generation & Debate</h3>
          <div class="mirofish-feed" ref="feed">
            <div v-for="(evt, i) in events" :key="i" class="timeline-item" :class="evt.type">
              
              <template v-if="evt.type === 'agent_post'">
                <div class="agent-message" :class="{ 'whisper-post': evt.data.post?.visibility && evt.data.post.visibility !== 'public', 'leak-post': evt.data.post?.action === 'leak_secret' }">
                  <div class="msg-header">
                    <span class="msg-author">{{ evt.data.post?.author_name }}</span>
                    <span class="msg-action">{{ evt.data.post?.action }}</span>
                    <span v-if="evt.data.post?.visibility && evt.data.post.visibility !== 'public'" class="msg-whisper-tag">🔒 {{ evt.data.post.visibility }}</span>
                  </div>
                  <div class="msg-text">{{ evt.data.post?.text }}</div>
                  <div v-if="evt.data.post && liveReactions(evt.data.post.id)" class="msg-reactions">
                    <span v-for="(names, emoji) in liveReactions(evt.data.post.id)" :key="emoji" class="reaction-chip" :title="names.join(', ')">
                      {{ emoji }} {{ names.length }}
                    </span>
                  </div>
                </div>
              </template>
              
              <template v-else>
                <div class="system-event" :class="evt.type">
                  <span class="sys-icon">{{ eventIcon(evt.type) }}</span>
                  <span class="sys-text">{{ eventText(evt) }}</span>
                </div>
              </template>

            </div>
            <div ref="feedEnd"></div>
          </div>
          
          <div class="spotlight-bar" v-if="spotlightInfo">
            🔦 Round {{ spotlightInfo.round }} — <strong>{{ spotlightInfo.active }}</strong> / {{ spotlightInfo.total }} agents speaking
          </div>

          <div class="injection-panel" style="margin-top: 15px; padding: 15px; background: rgba(0,0,0,0.2); border-left: 3px solid #9b59b6; border-radius: 4px;">
            <div class="injection-input-row" style="display:flex; gap: 10px;">
              <input type="text" v-model="injectionText" placeholder="⚡ God-Mode: Inject an event, rule, or direction" @keyup.enter="injectEvent" :disabled="isInjecting" style="flex:1; padding:10px; border-radius:4px; border:1px solid #333; background:#222; color:#fff;" />
              <button @click="injectEvent" :disabled="!injectionText.trim() || isInjecting" style="background:#9b59b6; border:none; padding:10px 20px; color:white; border-radius:4px; cursor:pointer; font-weight:bold;">INJECT</button>
            </div>
          </div>
        </div>

        <!-- right: state preview -->
        <div class="side-panel">
          <!-- Generated World Layers -->
          <div v-if="worldLayers.length" class="world-preview">
            <h3>🌍 Generated World</h3>
            <div class="layer-grid">
              <div v-for="layer in worldLayers" :key="layer.name" class="layer-card" @click="selectedLayer = layer">
                <div class="layer-name">{{ layer.name }}</div>
                <div class="layer-count">{{ layer.items.length }} entries</div>
                <div class="layer-names">{{ layer.items.map(i => i.name || i.era_name || i.theme || '?').join(', ') }}</div>
              </div>
            </div>
          </div>

          <!-- Agent Roster -->
          <div v-if="agents.length" class="agent-roster">
            <h3>🎭 Agents</h3>
            <div class="agent-grid">
              <div v-for="a in agents" :key="a.id" class="agent-card" @click="selectedAgent = a">
                <div class="agent-header">
                  <span class="agent-avatar">{{ a.avatar }}</span>
                  <span class="agent-name">{{ a.name }}</span>
                </div>
                <div class="agent-iq">IQ: {{ a.cognitive?.intelligence || '?' }} • {{ a.cognitive?.education_level || '?' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Final Outline -->
      <div v-if="outline" class="outline-section">
        <h3>📋 Generated Outline</h3>
        <div class="outline-content" v-html="renderMd(outline)"></div>
      </div>

      <!-- POV Prose Output -->
      <div v-if="povProse" class="prose-section">
        <div class="prose-header">
          <h3>✍️ First Chapter Draft</h3>
          <span class="prose-pov-tag">POV: {{ povAgentName }}</span>
        </div>
        <div class="prose-body">{{ povProse }}</div>
      </div>

      <!-- Agent Detail Modal -->
      <div v-if="selectedAgent" class="modal-overlay" @click.self="selectedAgent = null">
        <div class="modal">
          <button class="modal-close" @click="selectedAgent = null">×</button>
          <h2>{{ selectedAgent.avatar }} {{ selectedAgent.name }}</h2>
          <p class="modal-summary">{{ selectedAgent.personality_summary }}</p>
          <div class="modal-grid">
            <div class="modal-section">
              <h4>Cognitive Profile</h4>
              <div class="stat-row"><span>IQ</span><span>{{ selectedAgent.cognitive?.intelligence }}</span></div>
              <div class="stat-row"><span>Education</span><span>{{ selectedAgent.cognitive?.education_level }}</span></div>
              <div class="stat-row"><span>Exposure</span><span>{{ selectedAgent.cognitive?.worldly_exposure }}</span></div>
              <div class="stat-row"><span>Reasoning</span><span>{{ selectedAgent.cognitive?.reasoning_style }}</span></div>
              <div class="stat-row"><span>Communication</span><span>{{ selectedAgent.cognitive?.communication_style }}</span></div>
              <div v-if="selectedAgent.cognitive?.cognitive_biases?.length">
                <h4>Biases</h4>
                <div v-for="b in selectedAgent.cognitive.cognitive_biases" :key="b" class="bias-tag">{{ b }}</div>
              </div>
              <div v-if="selectedAgent.cognitive?.blind_spots?.length">
                <h4>Blind Spots</h4>
                <div v-for="b in selectedAgent.cognitive.blind_spots" :key="b" class="blind-tag">{{ b }}</div>
              </div>
            </div>
            <div class="modal-section">
              <h4>Life Experience</h4>
              <div v-if="selectedAgent.life?.formative_event" class="life-item">🔥 {{ selectedAgent.life.formative_event }}</div>
              <div v-if="selectedAgent.life?.deepest_wound" class="life-item">🩸 {{ selectedAgent.life.deepest_wound }}</div>
              <div v-if="selectedAgent.life?.greatest_achievement" class="life-item">⭐ {{ selectedAgent.life.greatest_achievement }}</div>
              <div class="stat-row"><span>Origin</span><span>{{ selectedAgent.life?.social_class_origin }}</span></div>
              <div class="stat-row"><span>Position</span><span>{{ selectedAgent.life?.current_social_position }}</span></div>
              <div v-if="selectedAgent.life?.traveled_places?.length" class="life-item">🗺️ Traveled: {{ selectedAgent.life.traveled_places.join(', ') }}</div>
            </div>
          </div>
          <div v-if="selectedAgent.speech_pattern" class="speech-box">
            💬 "{{ selectedAgent.catchphrase || '...' }}"
            <br><small>Speech: {{ selectedAgent.speech_pattern }}</small>
          </div>
        </div>
      </div>

      <!-- Spine Review Modal -->
      <div v-if="waitingForSpine" class="modal-overlay">
        <div class="modal review-modal">
          <h2>📋 Review Story Spine</h2>
          <p>The AI has generated the core structure. Tweak act names, themes and turning points before generating the full chapter outline.</p>
          <div v-if="fullSpine" class="spine-meta">
            <strong>{{ fullSpine.title }}</strong> &mdash; {{ fullSpine.total_chapters }} chapters
          </div>
          <div class="spine-editor">
            <div v-for="(act, i) in spineReviewData" :key="i" class="spine-beat">
              <div class="beat-header">
                <strong>Act {{ act.act_number }}</strong>
                <span class="beat-range">Ch {{ act.chapters_range?.[0] }}–{{ act.chapters_range?.[1] }}</span>
                <input v-model="act.act_name" class="beat-title-input" placeholder="Act name..." />
              </div>
              <div class="beat-field">
                <label>Theme</label>
                <input v-model="act.theme" class="beat-theme-input" />
              </div>
              <div class="beat-field">
                <label>Opens with</label>
                <textarea v-model="act.starts_with" rows="2"></textarea>
              </div>
              <div class="beat-field">
                <label>Ends with</label>
                <textarea v-model="act.ends_with" rows="2"></textarea>
              </div>
              <div class="beat-field">
                <label>Emotional arc</label>
                <input v-model="act.emotional_arc" class="beat-theme-input" />
              </div>
            </div>
          </div>
          <div class="modal-actions">
            <button @click="approveSpine" class="approve-btn" :disabled="isApproving">
              {{ isApproving ? 'Resuming...' : 'APPROVE & CONTINUE' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PipelineView',
  data() {
    return {
      seed: '', agentCount: 12, debateRounds: 15,
      chapterCount: 35, genres: '', actualEnding: '',
      started: false, currentPhaseIndex: 0,
      projectId: '',
      pacing: 'balanced', mood: 'neutral',
      godMode: false,
      isPaused: false,
      isInjecting: false,
      isApproving: false,
      injectionText: '',
      events: [], worldLayers: [], agents: [], debatePosts: [], outline: '',
      selectedLayer: null, selectedAgent: null,
      povProse: '', povAgentName: '',
      spotlightInfo: null,
      waitingForSpine: false,
      fullSpine: null,
      spineReviewData: [],
      phases: [
        { icon: '💡', label: 'Expand Seed' },
        { icon: '🌍', label: 'Build World' },
        { icon: '🎭', label: 'Spawn Agents' },
        { icon: '⚡', label: 'Agent Debate' },
        { icon: '📋', label: 'Outline' },
        { icon: '✍️', label: 'Write Chapter 1' },
      ],
    }
  },
  methods: {
    async startPipeline() {
      this.started = true
      try {
        // Create project first
        const projRes = await fetch('/api/projects/', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ name: this.seed.slice(0, 50), mode: 'outline', lore_text: this.seed }),
        })
        const project = await projRes.json()
        this.projectId = project.id  // Save for all subsequent fetches

        // Start pipeline
        const startRes = await fetch('/api/pipeline/start', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            seed: this.seed, project_id: this.projectId,
            agent_count: this.agentCount, debate_rounds: this.debateRounds,
            chapter_count: this.chapterCount, actual_ending: this.actualEnding,
            genres: this.genres, pacing: this.pacing, mood: this.mood,
            god_mode: this.godMode
          }),
        })
        if (!startRes.ok) {
          const err = await startRes.json().catch(() => ({}))
          this.events.push({ type: 'pipeline_error', data: { error: err.error || 'Failed to start pipeline' } })
          return
        }
      } catch (e) {
        this.events.push({ type: 'pipeline_error', data: { error: String(e) } })
        return
      }

      // Connect SSE — server buffers past events so we'll catch up even if pipeline already started
      this._connectSSE()
    },

    _connectSSE() {
      const es = new EventSource('/api/pipeline/events')
      this._es = es
      es.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'keepalive') return
        this.events.push(msg)
        this.handleEvent(msg)
        this.$nextTick(() => {
          if (this.$refs.feedEnd) this.$refs.feedEnd.scrollIntoView({ behavior: 'smooth' })
        })
      }
      es.onerror = () => {
        es.close()
        // Retry after 3s unless pipeline is done
        if (this.started && this.currentPhaseIndex < 5) {
          setTimeout(() => this._connectSSE(), 3000)
        }
      }
    },

    async pausePipeline() {
      try {
        await fetch('/api/pipeline/pause', { method: 'POST' })
        this.isPaused = true
      } catch(e) { console.error('Pause failed', e) }
    },

    async resumePipeline() {
      try {
        await fetch('/api/pipeline/resume', { method: 'POST' })
        this.isPaused = false
      } catch(e) { console.error('Resume failed', e) }
    },
    
    async toggleGodMode() {
      try {
        await fetch('/api/pipeline/god-mode', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: this.godMode })
        })
      } catch (e) {
        console.error('God Mode toggle failed', e)
      }
    },

    async approveSpine() {
      this.isApproving = true
      try {
        // Merge edited acts back into the full spine before sending
        const spineToSend = { ...this.fullSpine, act_structure: this.spineReviewData }
        const res = await fetch('/api/pipeline/approve', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: this.projectId, spine: spineToSend })
        })
        if (res.ok) {
          this.waitingForSpine = false
        } else {
          const err = await res.json().catch(() => ({}))
          console.error('Approve failed:', err)
        }
      } catch (e) {
        console.error('Approve failed', e)
      } finally {
        this.isApproving = false
      }
    },

    async injectEvent() {
      if (!this.injectionText.trim()) return
      this.isInjecting = true
      try {
        await fetch('/api/pipeline/inject', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: this.injectionText })
        })
        this.injectionText = ''
      } catch (e) {
        console.error('Injection failed', e)
      } finally {
        this.isInjecting = false
      }
    },

    liveReactions(postId) {
      const post = this.debatePosts.find(p => p.id === postId)
      if (!post || !post.reactions || !Object.keys(post.reactions).length) return null
      return post.reactions
    },

    handleEvent(msg) {
      const t = msg.type
      const d = msg.data || {}

      if (t === 'phase_start') {
        const phaseMap = {
          expand_seed: 0,
          generate_world: 1,
          spawn_agents: 2,
          debate: 3,
          outline: 4,
          pov_prose: 5,
        }
        if (phaseMap[d.phase] !== undefined) this.currentPhaseIndex = phaseMap[d.phase]
      }

      if (t === 'layer_complete') {
        const existing = this.worldLayers.find(l => l.name === d.layer)
        if (!existing) {
          this.worldLayers.push({ name: d.layer, items: (d.names || []).map(n => ({ name: n })) })
        }
      }

      if (t === 'agents_spawned') {
        this.currentPhaseIndex = 2
        if (d.agents) {
          this.agents = d.agents
        } else if (d.names) {
          // Merge new names into existing agent list display
          d.names.forEach(name => {
            if (!this.agents.find(a => a.name === name)) {
              this.agents.push({ name, avatar: '🎭', id: name, cognitive: {} })
            }
          })
        }
      }

      if (t === 'agent_post' && d.post) {
        this.debatePosts.push(d.post)
      }

      if (t === 'round_spotlight') {
        this.spotlightInfo = { round: d.round, active: d.active_count, total: d.total_agents }
      }

      if (t === 'phase_complete' && d.phase === 'outline') {
        this.currentPhaseIndex = 4
        fetch(`/api/pipeline/results/${this.projectId}`)
          .then(r => r.json()).then(res => { if (res.outline) this.outline = res.outline }).catch(() => {})
      }

      if (t === 'phase_complete' && d.phase === 'pov_prose') {
        this.currentPhaseIndex = 5
        this.povAgentName = d.pov_agent || 'Unknown'
        fetch(`/api/pipeline/results/${this.projectId}`)
          .then(r => r.json()).then(res => {
            if (res.outline?.includes('First Chapter Draft')) {
              const match = res.outline.split('## First Chapter Draft')[1]
              if (match) this.povProse = match.replace(/^.*?\n\n/, '').trim()
            }
          }).catch(() => {})
      }

      if (t === 'reactions_updated' && d.post_id) {
        const post = this.debatePosts.find(p => p.id === d.post_id)
        if (post) {
          post.reactions = d.reactions
        }
      }

      if (t === 'phase_waiting' && d.phase === 'spine_review') {
        this.fullSpine = d.spine || {}
        this.spineReviewData = this.fullSpine.act_structure || []
        this.waitingForSpine = true
      }

      if (t === 'pipeline_complete') {
        fetch(`/api/pipeline/results/${this.projectId}`)
          .then(r => r.json()).then(res => { if (res.outline) this.outline = res.outline }).catch(() => {})
      }

      if (t === 'pipeline_paused') {
        this.isPaused = true
      }
      if (t === 'pipeline_resumed') {
        this.isPaused = false
      }
    },

    eventIcon(type) {
      const icons = {
        phase_start: '▶', phase_complete: '✅',
        layer_start: '🔨', layer_complete: '✅', layer_error: '❌',
        draft_stage: '📝',
        agents_spawned: '🎭', agent_start: '💭', agent_post: '💬', agent_error: '❌',
        injection: '⚡', living_memory_formed: '🧠', character_promoted: '👑',
        graph_updated: '🕸', round_start: '🔄', round_end: '✓', round_spotlight: '🔦',
        sim_start: '🚀', sim_end: '🏁', coherence_issues: '🔍', outline_progress: '📝',
        pipeline_start: '🐟', pipeline_complete: '🎉', pipeline_error: '💥',
        pipeline_paused: '⏸️', pipeline_resumed: '▶️', system_notification: '⚙️'
      }
      return icons[type] || '•'
    },

    eventText(evt) {
      const d = evt.data || {}
      switch (evt.type) {
        case 'phase_start':     return `Starting: ${d.description || d.phase}`
        case 'phase_complete':  return `✅ Completed: ${d.phase}${d.chapters ? ` — ${d.chapters} chapters` : ''}${d.posts ? ` — ${d.posts} posts` : ''}${d.length ? ` — ${d.length} chars` : ''}`
        case 'layer_start':     return `Building ${d.layer}…`
        case 'pipeline_paused': return `⏸️ Pipeline Paused`
        case 'pipeline_resumed':return `▶️ Pipeline Resumed`
        case 'system_notification': return `System: ${d}`
        case 'draft_stage':     return `[${d.layer}] Generating ${d.stage}…`
        case 'layer_complete':  return `${d.layer}: ${d.count} entries — ${(d.names || []).join(', ')}`
        case 'agents_spawned':  return `${d.count} agents spawned: ${(d.names || []).slice(0, 5).join(', ')}`
        case 'agent_post':      return `${d.post?.author_name} [${d.post?.action}]: ${(d.post?.text || '').slice(0, 80)}`
        case 'round_start':     return `Round ${d.round} — ${d.total_agents || ''} agents`
        case 'round_spotlight': return `🔦 Round ${d.round}: ${d.active_count}/${d.total_agents} agents active — ${(d.active_names || []).join(', ')}`
        case 'living_memory_formed': return `${d.agent_name} formed ${d.memory_type}: ${d.description}`
        case 'character_promoted':   return `${d.entity} promoted: ${d.from} → ${d.to} (${d.mentions} mentions)`
        case 'coherence_issues':     return `Coherence: ${d.count} issues found in ${d.layer}, auto-repairing…`
        case 'outline_progress':     return `Outline: ${d.message} (${d.current}/${d.total})`
        case 'pipeline_complete':    return `🎉 Done! ${d.world_layers} world layers, ${d.debate_posts} posts, ${d.chapters || 0} chapters`
        case 'pipeline_error':       return `💥 Error: ${d.error}`
        default: return JSON.stringify(d).slice(0, 120)
      }
    },

    renderMd(md) {
      return md
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/^/, '<p>').replace(/$/, '</p>')
    },
  }
}
</script>

<style scoped>
.review-modal { max-width: 800px; width: 90vw; }
.spine-editor { 
  max-height: 400px; overflow-y: auto; margin: 20px 0; padding: 10px;
  background: rgba(0,0,0,0.2); border-radius: 8px;
}
.spine-beat { 
  background: rgba(255,255,255,0.05); padding: 15px; margin-bottom: 10px; border-radius: 6px;
  border-left: 4px solid var(--accent-gold);
}
.beat-header { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.beat-range { font-family: var(--font-mono); font-size: 10px; color: var(--accent-purple); background: rgba(108,92,231,0.1); padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.beat-title-input { flex: 1; min-width: 120px; background: transparent; border: 1px solid rgba(255,255,255,0.1); color: white; padding: 5px; border-radius: 4px; }
.beat-theme-input { width: 100%; background: transparent; border: 1px solid rgba(255,255,255,0.1); color: white; padding: 5px; border-radius: 4px; box-sizing: border-box; }
.beat-field { margin-bottom: 8px; }
.beat-field label { display: block; font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.5px; }
.beat-field textarea, .beat-field input { width: 100%; background: transparent; border: 1px solid rgba(255,255,255,0.1); color: white; padding: 8px; border-radius: 4px; resize: vertical; box-sizing: border-box; font-family: var(--font-body); font-size: 13px; }
.spine-meta { font-family: var(--font-mono); font-size: 12px; color: var(--accent-gold); margin-bottom: 16px; }
.modal-actions { display: flex; justify-content: flex-end; margin-top: 20px; }
.approve-btn { 
  background: var(--accent-gold); color: black; font-weight: bold; padding: 12px 30px; 
  border-radius: 30px; cursor: pointer; border: none; transition: 0.3s;
}
.approve-btn:hover { transform: scale(1.05); filter: brightness(1.2); }
.approve-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.pipeline { 
  max-width: 100%; 
  margin: 0 auto; 
  padding: 20px; 
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
}
.hero { text-align: center; margin-bottom: 32px; }
.hero-icon { font-size: 48px; margin-bottom: 8px; }
.hero h1 { font-family: var(--font-display); font-size: 38px; background: linear-gradient(135deg, var(--accent-gold), var(--accent-rose), var(--accent-purple), var(--accent-gold)); background-size: 300% 300%; -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 5px; animation: gradientPan 8s ease infinite; text-shadow: 0 0 40px rgba(232,168,56,0.2); }
.hero-sub { font-family: var(--font-mono); font-size: 14px; color: var(--text-muted); margin-top: 8px; }

.seed-input-area { max-width: 640px; margin: 0 auto; }
.seed-input-area textarea { width: 100%; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); border-radius: 14px; padding: 20px; font-size: 15px; font-family: var(--font-body); line-height: 1.8; resize: vertical; box-sizing: border-box; }
.seed-input-area textarea:focus { outline: none; border-color: var(--accent-gold); }
.config-row { display: flex; gap: 24px; margin: 16px 0; font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); }
.config-row label { display: flex; align-items: center; gap: 8px; }
.config-row input[type=range] { accent-color: var(--accent-gold); width: 120px; }
.start-btn { width: 100%; padding: 18px; border-radius: 14px; border: none; background: linear-gradient(135deg, var(--accent-gold), var(--accent-rose)); color: #fff; font-family: var(--font-display); font-size: 16px; font-weight: 700; letter-spacing: 3px; cursor: pointer; box-shadow: 0 4px 30px rgba(232,168,56,0.2); transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); animation: pulseGlow 4s infinite; }
.start-btn:hover:not(:disabled) { transform: translateY(-3px) scale(1.02); box-shadow: 0 8px 40px rgba(232,168,56,0.5); }
.start-btn:disabled { background: var(--bg-elevated); color: var(--text-muted); box-shadow: none; animation: none; transform: none; }

.phase-bar { display: flex; gap: 4px; padding: 16px 0; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.phase-step { flex: 1; text-align: center; padding: 8px; border-radius: 8px; font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); transition: all 0.3s; }
.phase-step.active { background: rgba(232,168,56,0.1); color: var(--accent-gold); border: 1px solid rgba(232,168,56,0.3); }
.phase-step.done { color: var(--accent-green); }
.phase-icon { display: block; font-size: 20px; margin-bottom: 4px; }
.phase-label { display: block; }

.pipeline-split { 
  display: grid; 
  grid-template-columns: 1.5fr 1fr; 
  gap: 24px; 
  margin-top: 20px;
  max-width: 100%;
  overflow: hidden;
}
.mirofish-panel h3 { font-family: var(--font-mono); font-size: 14px; color: var(--accent-gold); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
.mirofish-feed { 
  height: 600px; 
  max-height: 65vh; 
  overflow-y: auto; 
  overflow-x: hidden;
  display: flex; 
  flex-direction: column; 
  gap: 8px; 
  padding-right: 8px; 
  scroll-behavior: smooth; 
}
.timeline-item { width: 100%; animation: fadeSlideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) backwards; }

.spotlight-bar { margin: 8px 0; padding: 6px 12px; background: rgba(108,92,231,0.08); border: 1px solid rgba(108,92,231,0.2); border-radius: 8px; font-family: var(--font-mono); font-size: 11px; color: var(--accent-purple); }
.spotlight-bar strong { color: var(--text-primary); }
.injection-panel { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-light); }
.injection-input-row { display: flex; gap: 8px; }
.injection-input-row input { flex: 1; padding: 10px; border-radius: 6px; border: 1px solid var(--border-dark); background: rgba(0,0,0,0.2); color: var(--text-primary); font-family: var(--font-mono); font-size: 12px; }
.injection-input-row button { padding: 0 16px; background: var(--accent-gold); color: #000; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; transition: 0.2s; }
.injection-input-row button:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(232,168,56,0.3); }
.injection-input-row button:disabled { opacity: 0.5; }

.system-event { padding: 6px 12px; border-radius: 6px; background: rgba(255,255,255,0.03); display: flex; gap: 10px; align-items: flex-start; font-family: var(--font-mono); font-size: 11.5px; }
.sys-icon { flex-shrink: 0; font-size: 14px; }
.sys-text { color: var(--text-secondary); line-height: 1.5; word-break: break-word; }
.system-event.layer_complete { color: var(--accent-green); background: rgba(0,184,148,0.05); border: 1px solid rgba(0,184,148,0.2); }
.system-event.pipeline_complete { color: var(--accent-gold); font-weight: 600; border: 1px solid var(--accent-gold); }

.agent-message { padding: 12px 16px; border-radius: 12px; background: var(--bg-secondary); border-left: 3px solid var(--accent-purple); margin-left: 20px; }
.msg-header { margin-bottom: 6px; }
.msg-author { font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--text-primary); }
.msg-action { font-family: var(--font-mono); font-size: 10px; font-weight: 600; color: var(--accent-purple); padding: 2px 6px; background: rgba(108,92,231,0.1); border-radius: 6px; margin-left: 8px; }
.msg-text { font-size: 13.5px; line-height: 1.6; color: var(--text-secondary); white-space: pre-wrap; }
.msg-reactions { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.reaction-chip { display: inline-flex; align-items: center; gap: 3px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 2px 8px; font-size: 12px; cursor: default; transition: background 0.15s; }
.reaction-chip:hover { background: rgba(255,255,255,0.12); }

.whisper-post { background: rgba(14,14,26,0.9); border-left-color: var(--accent-green); font-style: italic; opacity: 0.85; }
.whisper-post .msg-text { color: var(--accent-green); }
.msg-whisper-tag { font-family: var(--font-mono); font-size: 9px; color: var(--accent-green); background: rgba(0,184,148,0.1); padding: 2px 6px; border-radius: 4px; margin-left: 6px; }
.leak-post { border-left-color: var(--accent-red); background: rgba(214,48,49,0.05); }
.leak-post .msg-action { background: rgba(214,48,49,0.15); color: var(--accent-red); }

.side-panel { display: flex; flex-direction: column; gap: 24px; }
.world-preview h3, .agent-roster h3, .outline-section h3 { font-family: var(--font-mono); font-size: 14px; color: var(--accent-gold); margin-bottom: 12px; }
.layer-grid { display: flex; flex-direction: column; gap: 8px; }
.layer-card { padding: 10px 14px; background: rgba(14,14,26,0.6); backdrop-filter: blur(4px); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); }
.layer-card:hover { border-color: var(--accent-gold); transform: translateY(-4px); box-shadow: 0 10px 25px rgba(232,168,56,0.15); background: rgba(14,14,26,0.9); }
.layer-name { font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--text-primary); text-transform: uppercase; }
.layer-count { font-family: var(--font-mono); font-size: 10px; color: var(--accent-green); }
.layer-names { font-size: 11px; color: var(--text-muted); margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.agent-grid { display: flex; flex-direction: column; gap: 8px; }
.agent-card { padding: 10px; background: rgba(14,14,26,0.6); backdrop-filter: blur(4px); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); }
.agent-card:hover { border-color: var(--accent-purple); transform: translateY(-4px); box-shadow: 0 10px 25px rgba(108,92,231,0.15); background: rgba(14,14,26,0.9); }
.agent-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.agent-avatar { font-size: 16px; }
.agent-name { font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--text-primary); }
.agent-iq { font-family: var(--font-mono); font-size: 10px; color: var(--accent-purple); }

.outline-section { margin-top: 24px; }
.outline-content { line-height: 1.8; font-size: 14px; color: var(--text-secondary); }
.outline-content :deep(h1) { font-family: var(--font-display); font-size: 24px; color: var(--accent-gold); margin: 24px 0 12px; }
.outline-content :deep(h2) { font-family: var(--font-display); font-size: 18px; color: var(--accent-rose); margin: 20px 0 8px; }
.outline-content :deep(strong) { color: var(--text-primary); }

.prose-section { margin-top: 32px; border: 1px solid rgba(232,168,56,0.25); border-radius: 14px; overflow: hidden; }
.prose-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: rgba(232,168,56,0.08); border-bottom: 1px solid rgba(232,168,56,0.15); }
.prose-header h3 { font-family: var(--font-mono); font-size: 14px; color: var(--accent-gold); margin: 0; }
.prose-pov-tag { font-family: var(--font-mono); font-size: 11px; color: var(--accent-purple); background: rgba(108,92,231,0.1); padding: 4px 10px; border-radius: 6px; }
.prose-body { padding: 24px; font-size: 15px; line-height: 2; color: var(--text-secondary); white-space: pre-wrap; font-family: 'Georgia', serif; }

/* Agent Detail Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 16px; padding: 24px; max-width: 700px; width: 90%; max-height: 85vh; overflow-y: auto; position: relative; }
.modal-close { position: absolute; top: 12px; right: 16px; background: none; border: none; color: var(--text-muted); font-size: 24px; cursor: pointer; }
.modal h2 { font-family: var(--font-display); font-size: 20px; color: var(--text-primary); margin-bottom: 8px; }
.modal-summary { font-size: 14px; color: var(--text-secondary); line-height: 1.7; margin-bottom: 16px; font-style: italic; }
.modal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.modal-section h4 { font-family: var(--font-mono); font-size: 11px; color: var(--accent-gold); letter-spacing: 1px; margin: 12px 0 6px; }
.stat-row { display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 11px; padding: 3px 0; border-bottom: 1px solid var(--border); }
.stat-row span:first-child { color: var(--text-muted); }
.stat-row span:last-child { color: var(--text-primary); }
.bias-tag { display: inline-block; font-family: var(--font-mono); font-size: 10px; background: rgba(232,168,56,0.1); color: var(--accent-gold); padding: 2px 8px; border-radius: 6px; margin: 2px; }
.blind-tag { display: inline-block; font-family: var(--font-mono); font-size: 10px; background: rgba(214,48,49,0.1); color: var(--accent-red); padding: 2px 8px; border-radius: 6px; margin: 2px; }
.life-item { font-size: 12px; color: var(--text-secondary); margin: 4px 0; line-height: 1.5; }
.speech-box { margin-top: 16px; padding: 12px 16px; background: var(--bg-elevated); border-radius: 10px; font-size: 13px; color: var(--accent-gold); font-style: italic; line-height: 1.6; }
.speech-box small { color: var(--text-muted); font-style: normal; }
</style>
