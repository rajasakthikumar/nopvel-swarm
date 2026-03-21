<template>
  <div class="agent-dashboard">
    <header class="dashboard-header">
      <h1>Agent Intelligence Dashboard</h1>
      <div class="status-badge" :class="{ active: isActive }">
        {{ isActive ? '● Live' : '○ Offline' }}
      </div>
    </header>

    <div class="dashboard-grid">
      <!-- Agent List Panel -->
      <div class="panel agent-list">
        <h2>Active Agents</h2>
        <div class="agent-grid">
          <div 
            v-for="agent in agents" 
            :key="agent.id"
            class="agent-card"
            :class="{ selected: selectedAgent?.id === agent.id }"
            @click="selectAgent(agent)"
          >
            <div class="agent-header">
              <span class="agent-avatar">{{ getAvatar(agent) }}</span>
              <div class="agent-info">
                <h3>{{ agent.name }}</h3>
                <span class="agent-role">{{ agent.role }}</span>
              </div>
              <div class="agent-status" :class="agent.enhanced?.emotional_state">
                {{ agent.enhanced?.emotional_state || 'neutral' }}
              </div>
            </div>
            <div class="agent-stats">
              <span class="stat">
                <strong>{{ agent.posts_count || 0 }}</strong> posts
              </span>
              <span class="stat">
                <strong>{{ agent.replies_count || 0 }}</strong> replies
              </span>
            </div>
          </div>
        </div>

        <!-- Agent Type Legend -->
        <div class="agent-type-legend">
          <div class="legend-header">
            <span class="legend-icon">📋</span>
            <h4>Agent Types</h4>
          </div>
          <div class="legend-items">
            <div class="legend-item">
              <span class="type-badge type-critic">Critic</span>
              <span class="type-desc">Meta-narrative perspective, focusing on themes and structure.</span>
            </div>
            <div class="legend-item">
              <span class="type-badge type-character">Character</span>
              <span class="type-desc">Diegetic perspective, responding as if they are in the world.</span>
            </div>
            <div class="legend-item">
              <span class="type-badge type-strategist">Strategist</span>
              <span class="type-desc">Focuses on plot twists, pacing, and logical consistency.</span>
            </div>
            <div class="legend-item">
              <span class="type-badge type-historian">Historian</span>
              <span class="type-desc">Focuses on world-building, lore consistency, and historical depth.</span>
            </div>
            <div class="legend-item">
              <span class="type-badge type-arc">Character_Arc_Planner</span>
              <span class="type-desc">Focuses on emotional growth, internal conflicts, and character development.</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Agent Detail Panel -->
      <div v-if="selectedAgent" class="panel agent-detail">
        <h2>Agent Profile</h2>
        
        <div class="detail-section">
          <h3>Identity</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <label>Name</label>
              <span>{{ selectedAgent.name }}</span>
            </div>
            <div class="detail-item">
              <label>Role</label>
              <span>{{ selectedAgent.role }}</span>
            </div>
            <div class="detail-item">
              <label>Platform</label>
              <span>{{ selectedAgent.platform }}</span>
            </div>
            <div class="detail-item">
              <label>Stance</label>
              <span class="stance-badge" :class="selectedAgent.stance">
                {{ selectedAgent.stance }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="agentDashboardData" class="detail-section">
          <h3>Current State</h3>
          <div class="state-display">
            <div class="state-item">
              <label>Emotional State</label>
              <span class="emotion-badge" :class="agentDashboardData.enhanced?.emotional_state">
                {{ agentDashboardData.enhanced?.emotional_state || 'neutral' }}
              </span>
            </div>
            <div class="state-item">
              <label>Actions Taken</label>
              <span>{{ agentDashboardData.enhanced?.action_count || 0 }}</span>
            </div>
            <div class="state-item">
              <label>Memories Stored</label>
              <span>{{ agentDashboardData.enhanced?.memory_count || 0 }}</span>
            </div>
            <div class="state-item">
              <label>Active Goals</label>
              <span>{{ agentDashboardData.enhanced?.active_goals || 0 }}</span>
            </div>
          </div>
        </div>

        <div v-if="agentDashboardData?.motivation" class="detail-section">
          <h3>Motivations</h3>
          <pre class="motivation-text">{{ agentDashboardData.motivation }}</pre>
        </div>

        <div v-if="agentDashboardData?.memory_summary" class="detail-section">
          <h3>Recent Memories</h3>
          <pre class="memory-text">{{ agentDashboardData.memory_summary }}</pre>
        </div>

        <div v-if="agentDashboardData?.relationships?.length" class="detail-section">
          <h3>Relationships</h3>
          <div class="relationship-list">
            <div 
              v-for="rel in agentDashboardData.relationships" 
              :key="rel.other_agent"
              class="relationship-item"
            >
              <span class="rel-agent">{{ getAgentName(rel.other_agent) }}</span>
              <span class="rel-sentiment" :class="getSentimentClass(rel.sentiment)">
                {{ formatSentiment(rel.sentiment) }}
              </span>
              <span class="rel-count">{{ rel.interactions }} interactions</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Analytics Panel -->
      <div class="panel analytics">
        <h2>Simulation Analytics</h2>
        
        <div v-if="analytics" class="analytics-content">
          <div class="metric-row">
            <div class="metric-card">
              <label>Total Rounds</label>
              <strong>{{ analytics.summary?.total_rounds || 0 }}</strong>
            </div>
            <div class="metric-card">
              <label>Total Actions</label>
              <strong>{{ analytics.summary?.total_actions || 0 }}</strong>
            </div>
            <div class="metric-card">
              <label>Avg Actions/Round</label>
              <strong>{{ formatNumber(analytics.summary?.avg_actions_per_round) }}</strong>
            </div>
          </div>

          <div v-if="emotionTimeline.length" class="emotion-chart">
            <h3>Emotional Timeline</h3>
            <div class="timeline">
              <div 
                v-for="point in emotionTimeline" 
                :key="point.round"
                class="timeline-point"
              >
                <span class="round-label">R{{ point.round }}</span>
                <div class="emotion-bars">
                  <div 
                    v-for="(count, emotion) in point.emotions" 
                    :key="emotion"
                    class="emotion-bar"
                    :class="emotion"
                    :style="{ height: `${count * 20}px` }"
                    :title="`${emotion}: ${count}`"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="analytics-placeholder">
          <p>Analytics data not available</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AgentDashboard'
}
</script>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const agents = ref([])
const selectedAgent = ref(null)
const agentDashboardData = ref(null)
const analytics = ref(null)
const emotionTimeline = ref([])
const isActive = ref(false)

let refreshInterval = null

const API_BASE = '/api/enhanced'

async function fetchAgents() {
  try {
    const response = await fetch(`${API_BASE}/agents`)
    if (response.ok) {
      const data = await response.json()
      agents.value = data.agents || []
    }
  } catch (err) {
    console.error('Failed to fetch agents:', err)
  }
}

async function fetchAgentDashboard(agentId) {
  try {
    const response = await fetch(`${API_BASE}/agents/${agentId}/dashboard`)
    if (response.ok) {
      agentDashboardData.value = await response.json()
    }
  } catch (err) {
    console.error('Failed to fetch agent dashboard:', err)
  }
}

async function fetchAnalytics() {
  try {
    const response = await fetch(`${API_BASE}/analytics`)
    if (response.ok) {
      analytics.value = await response.json()
    }
  } catch (err) {
    console.error('Failed to fetch analytics:', err)
  }
}

async function fetchEmotionTimeline() {
  try {
    const response = await fetch(`${API_BASE}/emotions/timeline`)
    if (response.ok) {
      const data = await response.json()
      emotionTimeline.value = data.timeline || []
    }
  } catch (err) {
    console.error('Failed to fetch emotion timeline:', err)
  }
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`)
    if (response.ok) {
      const data = await response.json()
      isActive.value = data.active
    }
  } catch (err) {
    isActive.value = false
  }
}

function selectAgent(agent) {
  selectedAgent.value = agent
  if (agent?.id) {
    fetchAgentDashboard(agent.id)
  }
}

function getAvatar(agent) {
  // Simple avatar generation based on name
  const avatars = ['🧙', '⚔️', '📜', '🌙', '🔮', '🗡️', '👁️', '🦅', '🐉', '🏰']
  const index = agent.name?.length % avatars.length || 0
  return agent.avatar || avatars[index]
}

function getAgentName(agentId) {
  const agent = agents.value.find(a => a.id === agentId)
  return agent?.name || agentId
}

function formatSentiment(sentiment) {
  if (sentiment > 0.3) return 'Allied'
  if (sentiment > 0) return 'Friendly'
  if (sentiment === 0) return 'Neutral'
  if (sentiment > -0.3) return 'Tense'
  return 'Hostile'
}

function getSentimentClass(sentiment) {
  if (sentiment > 0.3) return 'allied'
  if (sentiment > 0) return 'friendly'
  if (sentiment === 0) return 'neutral'
  if (sentiment > -0.3) return 'tense'
  return 'hostile'
}

function formatNumber(num) {
  if (num === undefined || num === null) return '0'
  return num.toFixed(1)
}

async function refreshData() {
  await checkHealth()
  if (isActive.value) {
    await fetchAgents()
    await fetchAnalytics()
    await fetchEmotionTimeline()
    
    if (selectedAgent.value) {
      await fetchAgentDashboard(selectedAgent.value.id)
    }
  }
}

onMounted(() => {
  refreshData()
  refreshInterval = setInterval(refreshData, 3000) // Refresh every 3 seconds
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.agent-dashboard {
  padding: 24px;
  max-width: 1600px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.dashboard-header h1 {
  font-size: 24px;
  font-weight: 600;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  background: #e5e7eb;
  color: #6b7280;
}

.status-badge.active {
  background: #dcfce7;
  color: #16a34a;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 300px 1fr 400px;
  gap: 20px;
  height: calc(100vh - 140px);
}

.panel {
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 20px;
  overflow-y: auto;
}

.panel h2 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #111;
}

/* Agent List */
.agent-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.agent-card {
  padding: 16px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s;
}

.agent-card:hover {
  border-color: #d1d5db;
  background: #f9fafb;
}

.agent-card.selected {
  border-color: #0984E3;
  background: #eff6ff;
}

.agent-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.agent-avatar {
  font-size: 24px;
}

.agent-info {
  flex: 1;
}

.agent-info h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.agent-role {
  font-size: 12px;
  color: #6b7280;
}

.agent-status {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  background: #e5e7eb;
  color: #6b7280;
}

.agent-status.excited,
.agent-status.enthusiastic {
  background: #dcfce7;
  color: #16a34a;
}

.agent-status.angry,
.agent-status.anxious,
.agent-status.hostile {
  background: #fee2e2;
  color: #dc2626;
}

.agent-status.content,
.agent-status.relaxed {
  background: #dbeafe;
  color: #2563eb;
}

.agent-stats {
  display: flex;
  gap: 16px;
}

.stat {
  font-size: 12px;
  color: #6b7280;
}

.stat strong {
  color: #111;
  font-weight: 600;
}

/* Agent Detail */
.detail-section {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid #e5e7eb;
}

.detail-section:last-child {
  border-bottom: none;
}

.detail-section h3 {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-item label {
  font-size: 12px;
  color: #6b7280;
}

.detail-item span {
  font-size: 14px;
  font-weight: 500;
}

.stance-badge {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
}

.stance-badge.strongly_positive {
  background: #dcfce7;
  color: #16a34a;
}

.stance-badge.strongly_negative {
  background: #fee2e2;
  color: #dc2626;
}

.state-display {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.state-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.state-item label {
  font-size: 12px;
  color: #6b7280;
}

.emotion-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.motivation-text,
.memory-text {
  background: #f9fafb;
  padding: 16px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  font-family: inherit;
  max-height: 300px;
  overflow-y: auto;
}

/* Relationships */
.relationship-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.relationship-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: #f9fafb;
  border-radius: 8px;
  font-size: 13px;
}

.rel-agent {
  flex: 1;
  font-weight: 500;
}

.rel-sentiment {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.rel-sentiment.allied {
  background: #dcfce7;
  color: #16a34a;
}

.rel-sentiment.friendly {
  background: #dbeafe;
  color: #2563eb;
}

.rel-sentiment.neutral {
  background: #f3f4f6;
  color: #6b7280;
}

.rel-sentiment.tense {
  background: #fef3c7;
  color: #d97706;
}

.rel-sentiment.hostile {
  background: #fee2e2;
  color: #dc2626;
}

.rel-count {
  font-size: 12px;
  color: #9ca3af;
}

/* Analytics */
.metric-row {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.metric-card {
  flex: 1;
  padding: 16px;
  background: #f9fafb;
  border-radius: 10px;
  text-align: center;
}

.metric-card label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.metric-card strong {
  font-size: 24px;
  font-weight: 700;
  color: #111;
}

/* Emotion Timeline */
.emotion-chart {
  margin-top: 24px;
}

.emotion-chart h3 {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  margin-bottom: 16px;
}

.timeline {
  display: flex;
  gap: 4px;
  align-items: flex-end;
  height: 150px;
  padding-bottom: 24px;
  border-bottom: 1px solid #e5e7eb;
}

.timeline-point {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.round-label {
  font-size: 10px;
  color: #9ca3af;
}

.emotion-bars {
  display: flex;
  gap: 2px;
  align-items: flex-end;
  height: 100px;
}

.emotion-bar {
  width: 8px;
  border-radius: 2px 2px 0 0;
  min-height: 4px;
  transition: all 0.3s;
}

.emotion-bar.excited,
.emotion-bar.enthusiastic {
  background: #16a34a;
}

.emotion-bar.angry,
.emotion-bar.anxious,
.emotion-bar.hostile {
  background: #dc2626;
}

.emotion-bar.content,
.emotion-bar.relaxed {
  background: #2563eb;
}

.emotion-bar.neutral {
  background: #9ca3af;
}

.analytics-placeholder {
  text-align: center;
  padding: 40px;
  color: #9ca3af;
}

@media (max-width: 1200px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
    height: auto;
  }
  
  .panel {
    max-height: 600px;
  }
}

/* Agent Type Legend */
.agent-type-legend {
  margin-top: 16px;
  padding: 12px;
  border-top: 1px solid #e5e7eb;
  background: #fafafa;
  border-radius: 8px;
}

.legend-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.legend-icon {
  font-size: 14px;
}

.legend-header h4 {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  margin: 0;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.legend-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.type-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  width: fit-content;
  font-family: var(--font-mono);
}

.type-critic { background: #fef3c7; color: #92400e; }
.type-character { background: #dbeafe; color: #1e40af; }
.type-strategist { background: #fee2e2; color: #991b1b; }
.type-historian { background: #d1fae5; color: #065f46; }
.type-arc { background: #ede9fe; color: #5b21b6; }

.type-desc {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.4;
  padding-left: 4px;
}
</style>
