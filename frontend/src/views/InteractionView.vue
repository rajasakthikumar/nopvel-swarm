<template>
  <div class="interact-view">
    <!-- Sidebar -->
    <div class="interact-sidebar">
      <h3>💬 Deep Interaction</h3>
      <p class="interact-desc">Chat with the ReportAgent or interview individual agents about their reasoning.</p>

      <div class="mode-switch">
        <button @click="chatMode = 'report'" :class="{ active: chatMode === 'report' }">📊 ReportAgent</button>
        <button @click="chatMode = 'interview'" :class="{ active: chatMode === 'interview' }">🎭 Interview Agent</button>
      </div>

      <div v-if="chatMode === 'interview'" class="agent-picker">
        <div v-for="a in agents" :key="a.id" class="pick-agent"
             :class="{ selected: selectedAgentId === a.id }"
             @click="selectAgent(a.id)">
          <span class="agent-avatar">{{ a.avatar || '🎭' }}</span>
          <span class="agent-name">{{ a.name }}</span>
          <span class="agent-type-badge">{{ a.type }}</span>
        </div>
      </div>
    </div>

    <!-- Chat Area -->
    <div class="chat-area">
      <div class="messages" ref="messages">
        <div v-for="(msg, i) in messages" :key="i" class="message" :class="msg.role">
          <div class="msg-role">{{ msg.role === 'user' ? '✍️ You' : chatMode === 'report' ? '📊 ReportAgent' : `🎭 ${selectedAgentName}` }}</div>
          <div class="msg-text">{{ msg.content }}</div>
        </div>
      </div>

      <div class="chat-input">
        <input v-model="inputText" @keydown.enter="send"
               :placeholder="chatMode === 'report' ? 'Ask the ReportAgent about the simulation...' : `Ask ${selectedAgentName} a question...`" />
        <button @click="send" :disabled="!inputText.trim() || sending">
          {{ sending ? '...' : 'Send' }}
        </button>
      </div>
    </div>

    <!-- Agent Details Panel (always visible in interview mode) -->
    <div v-if="chatMode === 'interview' && selectedAgent" class="agent-details-panel">
      <div class="details-header">
        <h3>🎭 Agent Profile</h3>
      </div>

      <div class="details-content">
        <!-- Identity -->
        <div class="identity-section">
          <span class="agent-avatar-large">{{ selectedAgent.avatar || '🎭' }}</span>
          <div class="identity-info">
            <h4>{{ selectedAgent.name }}</h4>
            <span class="type-tag">{{ selectedAgent.type }}</span>
          </div>
        </div>

        <!-- Persona -->
        <div v-if="selectedAgent.persona" class="detail-section">
          <h4 class="section-title">Persona</h4>
          <p class="persona-text">{{ selectedAgent.persona }}</p>
        </div>

        <!-- Memory (Collapsible - expanded by default) -->
        <div class="detail-section memory-section">
          <button class="collapsible-header" @click="memoryExpanded = !memoryExpanded">
            <span>🧠</span>
            <span class="section-title">Memory</span>
            <span class="expand-icon">{{ memoryExpanded ? '▼' : '▶' }}</span>
          </button>
          <div v-if="memoryExpanded" class="collapsible-content">
            <div class="memory-content">
              {{ selectedAgent.memory || 'No memory stored yet. The agent will accumulate memories as they interact.' }}
            </div>
          </div>
        </div>

        <!-- Backstory (Collapsible) -->
        <div class="detail-section">
          <button class="collapsible-header" @click="backstoryExpanded = !backstoryExpanded">
            <span>📜</span>
            <span class="section-title">Backstory</span>
            <span class="expand-icon">{{ backstoryExpanded ? '▼' : '▶' }}</span>
          </button>
          <div v-if="backstoryExpanded" class="collapsible-content">
            <p class="backstory-text">{{ selectedAgent.backstory || 'No backstory available.' }}</p>
          </div>
        </div>

        <!-- Motivation (Collapsible) -->
        <div class="detail-section">
          <button class="collapsible-header" @click="motivationExpanded = !motivationExpanded">
            <span>🎯</span>
            <span class="section-title">Motivation</span>
            <span class="expand-icon">{{ motivationExpanded ? '▼' : '▶' }}</span>
          </button>
          <div v-if="motivationExpanded" class="collapsible-content">
            <p class="motivation-text">{{ selectedAgent.motivation || 'No motivation defined.' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: ['projectId'],
  data() {
    return {
      chatMode: 'report',
      messages: [],
      inputText: '',
      sending: false,
      agents: [],
      selectedAgentId: null,
      memoryExpanded: true,
      backstoryExpanded: false,
      motivationExpanded: false,
    }
  },
  computed: {
    selectedAgentName() {
      const a = this.agents.find(x => x.id === this.selectedAgentId)
      return a ? a.name : 'Agent'
    },
    selectedAgent() {
      return this.agents.find(x => x.id === this.selectedAgentId) || null
    }
  },
  async mounted() {
    try {
      const res = await fetch('/api/simulation/state')
      const data = await res.json()
      this.agents = data.agents || []
      if (this.agents.length) {
        this.selectedAgentId = this.agents[0].id
        await this.fetchAgentDetails(this.selectedAgentId)
      }
    } catch {}
  },
  methods: {
    async selectAgent(agentId) {
      this.selectedAgentId = agentId
      await this.fetchAgentDetails(agentId)
    },
    async fetchAgentDetails(agentId) {
      try {
        const res = await fetch(`/api/agents/${agentId}`)
        if (res.ok) {
          const data = await res.json()
          const idx = this.agents.findIndex(a => a.id === agentId)
          if (idx !== -1) {
            this.agents[idx] = { ...this.agents[idx], ...data }
          }
        }
      } catch (err) {
        console.error('Failed to fetch agent details:', err)
      }
    },
    async send() {
      if (!this.inputText.trim() || this.sending) return
      const text = this.inputText
      this.inputText = ''
      this.messages.push({ role: 'user', content: text })
      this.sending = true

      try {
        let res
        if (this.chatMode === 'report') {
          res = await fetch('/api/report/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: text,
              history: this.messages.filter(m => m.role !== 'system').map(m => ({ role: m.role, content: m.content })),
            }),
          })
        } else {
          res = await fetch('/api/report/interview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agent_id: this.selectedAgentId, question: text }),
          })
        }
        const data = await res.json()
        this.messages.push({ role: 'assistant', content: data.response })
      } catch (err) {
        this.messages.push({ role: 'assistant', content: `Error: ${err.message}` })
      }
      this.sending = false
      this.$nextTick(() => this.$refs.messages?.scrollTo(0, this.$refs.messages.scrollHeight))
    }
  }
}
</script>

<style scoped>
.interact-view { 
  display: flex; 
  height: calc(100vh - 50px); 
  overflow: hidden;
}

.interact-sidebar {
  width: 260px; 
  padding: 16px; 
  border-right: 1px solid var(--border);
  display: flex; 
  flex-direction: column; 
  gap: 12px;
  overflow-y: auto;
  flex-shrink: 0;
}
.interact-sidebar h3 { font-family: var(--font-mono); font-size: 14px; color: var(--accent-purple); }
.interact-desc { font-size: 12px; color: var(--text-muted); line-height: 1.6; }
.mode-switch { display: flex; gap: 4px; }
.mode-switch button {
  flex: 1; padding: 8px; border-radius: 8px; border: 1px solid var(--border);
  background: transparent; color: var(--text-muted); cursor: pointer;
  font-family: var(--font-mono); font-size: 10px;
}
.mode-switch button.active { background: var(--bg-elevated); color: var(--accent-purple); border-color: rgba(108,92,231,0.3); }
.agent-picker { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.pick-agent {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px; 
  cursor: pointer;
  font-family: var(--font-mono); 
  font-size: 11px; 
  color: var(--text-muted);
}
.pick-agent:hover { background: var(--bg-elevated); }
.pick-agent.selected { background: var(--bg-elevated); color: var(--text-primary); border-left: 2px solid var(--accent-purple); }
.pick-agent .agent-avatar { font-size: 14px; }
.pick-agent .agent-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pick-agent .agent-type-badge { font-size: 9px; padding: 2px 6px; background: rgba(108, 92, 231, 0.1); color: var(--accent-purple); border-radius: 4px; }

.chat-area { 
  flex: 1; 
  display: flex; 
  flex-direction: column; 
  min-width: 0;
  overflow: hidden;
}
.messages { 
  flex: 1; 
  overflow-y: auto; 
  overflow-x: hidden;
  padding: 20px; 
  display: flex; 
  flex-direction: column; 
  gap: 12px; 
}
.message { padding: 12px 16px; border-radius: 12px; }
.message.user { background: var(--bg-elevated); border-left: 3px solid var(--accent-yellow); }
.message.assistant { background: var(--bg-secondary); border-left: 3px solid var(--accent-purple); }
.msg-role { font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px; }
.msg-text { font-size: 13.5px; line-height: 1.8; color: var(--text-secondary); white-space: pre-wrap; }

.chat-input {
  padding: 12px 20px; border-top: 1px solid var(--border);
  display: flex; gap: 10px;
  flex-shrink: 0;
}
.chat-input input {
  flex: 1; background: var(--bg-secondary); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 14px; color: var(--text-primary);
  font-family: var(--font-body); font-size: 13px;
}
.chat-input button {
  padding: 10px 20px; border-radius: 10px; border: none;
  background: var(--accent-purple); color: #fff;
  font-family: var(--font-mono); font-size: 11px; font-weight: 600; cursor: pointer;
}
.chat-input button:disabled { background: var(--bg-elevated); color: var(--text-muted); }

/* Agent Details Panel */
.agent-details-panel {
  width: 320px;
  min-width: 320px;
  border-left: 1px solid var(--border);
  background: var(--bg-secondary);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.details-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-elevated);
  position: sticky;
  top: 0;
  z-index: 10;
  flex-shrink: 0;
}

.details-header h3 {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--accent-purple);
  margin: 0;
}

.details-content {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.identity-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--bg-primary);
  border-radius: 10px;
}

.agent-avatar-large {
  font-size: 32px;
}

.identity-info h4 {
  margin: 0 0 4px 0;
  font-size: 16px;
  color: var(--text-primary);
}

.type-tag {
  font-size: 10px;
  padding: 2px 8px;
  background: rgba(108, 92, 231, 0.1);
  color: var(--accent-purple);
  border-radius: 4px;
  font-family: var(--font-mono);
}

.detail-section {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.memory-section {
  border-color: rgba(108, 92, 231, 0.2);
  background: rgba(108, 92, 231, 0.03);
}

.collapsible-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
}

.collapsible-header:hover {
  background: var(--bg-elevated);
}

.section-title {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  margin: 0;
}

.expand-icon {
  font-size: 10px;
  color: var(--text-muted);
}

.collapsible-content {
  padding: 0 12px 12px;
}

.memory-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  font-style: italic;
  background: var(--bg-primary);
  padding: 12px;
  border-radius: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.persona-text,
.backstory-text,
.motivation-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  background: var(--bg-primary);
  padding: 12px;
  border-radius: 6px;
  margin: 0;
}
</style>
