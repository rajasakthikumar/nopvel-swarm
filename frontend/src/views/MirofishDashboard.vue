<template>
  <div class="dashboard-layout">
    <!-- Left Pane: Graph Visualization -->
    <div class="pane pane-left">
      <div class="pane-header">
        <h2>Graph Relationship Visualization</h2>
        <div class="graph-actions">
          <button class="action-btn"><span class="icon">↻</span> Refresh</button>
          <button class="action-btn icon-only"><span class="icon">⛶</span></button>
        </div>
      </div>
      
      <div class="graph-container" ref="graphContainer">
        <svg ref="svg" width="100%" height="100%"></svg>
      </div>

      <!-- Detail Card Overlay -->
      <div class="detail-card" v-if="selectedRel">
        <div class="detail-header">
          <h3>Relationship</h3>
          <button class="close-btn" @click="selectedRel = null">✕</button>
        </div>
        <div class="detail-title">
          <span class="source">{{ selectedRel.source }}</span> →
          <span class="rel-label">{{ selectedRel.label }}</span> →
          <span class="target">{{ selectedRel.target }}</span>
        </div>
        <div class="detail-body">
          <div class="detail-row"><span class="label">UUID:</span> <span class="val mono">{{ selectedRel.uuid }}</span></div>
          <div class="detail-row"><span class="label">Label:</span> <span class="val">{{ selectedRel.label }}</span></div>
          <div class="detail-row"><span class="label">Type:</span> <span class="val">{{ selectedRel.type }}</span></div>
          <div class="detail-row"><span class="label">Fact:</span> <span class="val">{{ selectedRel.fact }}</span></div>
          
          <div class="episodes-section">
            <div class="label">Episodes:</div>
            <div class="episode-id mono">{{ selectedRel.episode }}</div>
          </div>
          
          <div class="detail-row"><span class="label">Created:</span> <span class="val">{{ selectedRel.created }}</span></div>
          <div class="detail-row"><span class="label">Valid From:</span> <span class="val">{{ selectedRel.validFrom }}</span></div>
        </div>
      </div>

      <!-- Legend Overlay -->
      <div class="legend-card">
        <div class="legend-title">ENTITY TYPES</div>
        <div class="legend-grid">
          <div class="legend-item" v-for="(color, type) in entityTypes" :key="type">
            <span class="color-dot" :style="{ background: color }"></span>
            <span class="type-name">{{ type }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Pane: Orchestration Feed & Terminal -->
    <div class="pane pane-right">
      <div class="orchestration-panel">
        <div class="orch-header">
          <div class="orch-title-row">
            <h1>World Activation Orchestration</h1>
            <div style="display: flex; gap: 12px; align-items: center;">
              <span class="status-tag" v-if="!simulationRunning">STATUS: PENDING</span>
              <span class="status-tag" style="background:#dcfce7; color:#166534;" v-else>STATUS: RUNNING</span>
              <button @click="startSimulation" class="start-sim-btn" :disabled="simulationRunning">
                🚀 {{ simulationRunning ? 'Running...' : 'Start Simulation' }}
              </button>
            </div>
          </div>
          <div class="orch-subtitle mono">POST /api/pipeline/start</div>
          <p class="orch-desc">Initializes the simulation environment by spawning world-native agents, forming living memories, and establishing the thematic focus for the swarm debate.</p>
        </div>

        <div class="alert-box">
          <div class="alert-title">
            <span class="alert-icon">🎯</span> Narrative Constraints
          </div>
          <p class="alert-text">
            Agents are grounded strictly within the provided lore constraints. Generated personas will act natively within the world hierarchy, responding to factions, magic systems, and environmental variables. Conflict will emerge naturally from differing character motivations: some characters will defend the established status quo, while others will challenge systemic inequalities or pursue divergent hidden agendas based on their cognitive biases and life experiences.
          </p>
        </div>

        <transition name="fade-slide">
          <div class="injection-panel" v-if="simulationRunning">
            <div class="injection-header">
              <span class="icon">⚡</span> <h3>God-Mode Event Injection</h3>
            </div>
            <p class="injection-desc">Force an event into the simulation. Agents will react immediately.</p>
            <div class="injection-input-row">
              <input type="text" v-model="injectionText" placeholder="e.g., A massive earthquake just shattered the capital wall..." @keyup.enter="injectEvent" :disabled="isInjecting" />
              <button @click="injectEvent" :disabled="!injectionText.trim() || isInjecting">
                {{ isInjecting ? '...' : 'INJECT' }}
              </button>
            </div>
          </div>
        </transition>

        <div class="topics-section">
          <h3>Core Thematic Vectors</h3>
          <div class="topic-tags">
            <span class="topic-tag"># World Hierarchy</span>
            <span class="topic-tag"># Faction Warfare</span>
            <span class="topic-tag"># Resource Scarcity</span>
            <span class="topic-tag"># Latent Magic Resistance</span>
            <span class="topic-tag"># Internal Betrayal</span>
            <span class="topic-tag"># Core Axioms</span>
            <span class="topic-tag"># Narrative Tension</span>
            <span class="topic-tag"># Emergent Artifacts</span>
            <span class="topic-tag"># Social Upheaval</span>
            <span class="topic-tag"># AI Agency</span>
          </div>
        </div>

        <div class="sequence-section">
          <h3>Live Action Sequence</h3>
          <div class="sequence-list">
            <div class="seq-item" v-for="(item, index) in sequenceItems" :key="index">
              <div class="seq-header">
                <div class="seq-author">
                  <span class="author-type">{{ item.authorType }}</span>
                </div>
                <div class="seq-meta mono">Agent {{ item.agentId }} @{{ item.handle }}</div>
              </div>
              <div class="seq-content">{{ item.content }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="system-dashboard">
        <div class="dash-header">
          <span>SYSTEM DASHBOARD</span>
          <span class="dash-id">stn_5b1kc50a3ae9</span>
        </div>
        <div class="dash-logs" ref="dashLogs">
          <div class="log-line" v-for="(log, i) in systemLogs" :key="i">
            <span class="log-time">{{ log.time }}</span>
            <span class="log-msg"><span class="log-arrow">↗</span> {{ log.msg }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import * as d3 from 'd3'

export default {
  name: 'MirofishDashboard',
  props: ['projectId'],
  data() {
    return {
      entityTypes: {
        'MediaOutlet': '#f26d40', 'Entity': '#0984E3', 'GovernmentAgency': '#10b981',
        'Company': '#444444', 'Person': '#ef4444', 'Organization': '#8b5cf6',
        'InvestorInstitution': '#64748b', 'PolicyMaker': '#b45309',
        'DeveloperCommunity': '#059669', 'TechExecutive': '#dc2626',
        'character': '#E8A838', 'place': '#00B894', 'faction': '#C75B7A',
        'artifact': '#6C5CE7', 'magic_system': '#0984E3', 'event': '#E17055'
      },
      selectedRel: null,
      sequenceItems: [],
      systemLogs: [],
      nodes: [],
      edges: [],
      eventSource: null,
      simulationRunning: false,
      injectionText: '',
      isInjecting: false
    }
  },
  async mounted() {
    this.addLog("SYSTEM STARTUP", "Dashboard initialized");
    if (this.projectId) {
      await this.loadGraphData();
      this.connectSimulationSSE();
    } else {
      this.renderMockGraph();
      this.addLog("MOCK MODE", "No project ID provided, rendering mock layout.");
    }
  },
  beforeUnmount() {
    if (this.eventSource) this.eventSource.close();
  },
  methods: {
    addLog(title, msg) {
      const time = new Date().toISOString().split('T')[1].substring(0, 12);
      this.systemLogs.push({ time, msg: `[${title}] ${msg}` });
      this.$nextTick(() => {
        if (this.$refs.dashLogs) {
          this.$refs.dashLogs.scrollTop = this.$refs.dashLogs.scrollHeight;
        }
      });
    },
    async loadGraphData() {
      this.addLog("GRAPH", `Fetching data for project ${this.projectId}`);
      try {
        const res = await fetch(`/api/graph/query/${this.projectId}`);
        const data = await res.json();
        this.nodes = data.nodes || [];
        this.edges = data.edges || [];
        this.addLog("GRAPH", `Loaded ${this.nodes.length} nodes and ${this.edges.length} edges`);
        this.$nextTick(() => this.renderActualGraph());
      } catch (e) {
        this.addLog("ERROR", "Failed to compile graph data.");
      }
    },
    connectSimulationSSE() {
      this.addLog("SYSTEM", "Connecting to Event Stream...");
      this.eventSource = new EventSource('/api/pipeline/events');
      this.eventSource.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === 'agent_post' || msg.type === 'injection') {
          const post = msg.data.post || msg.data;
          this.sequenceItems.unshift({
            authorType: post.role || 'AGENT',
            agentId: post.author_id,
            handle: post.author_name.replace(/\s+/g, '_').toLowerCase(),
            content: post.text
          });
          if (this.sequenceItems.length > 50) this.sequenceItems.pop();
        } else if (msg.type === 'sim_start' || msg.type === 'phase_start') {
          this.simulationRunning = true;
          this.addLog("SIM", `Status update: ${msg.type}`);
        } else if (msg.type === 'keepalive') {
          // ignore
        } else {
          this.addLog("EVENT", `[${msg.type}]`);
        }
      };
    },
    async startSimulation() {
      if (!this.projectId) {
        this.addLog("ERROR", "No project selected. Go to Home tab to create a project first.");
        return;
      }
      this.addLog("SYSTEM", "Triggering pipeline start...");
      try {
        await fetch('/api/pipeline/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: this.projectId,
            seed: "Auto-started from dashboard",
            agent_count: 15,
            debate_rounds: 10
          })
        });
      } catch (err) {
        this.addLog("ERROR", "Failed to start: " + err.message);
      }
    },
    async injectEvent() {
      if (!this.injectionText.trim()) return;
      this.isInjecting = true;
      this.addLog("GOD-MODE", `Injecting: "${this.injectionText}"`);
      try {
        const res = await fetch('/api/pipeline/inject', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: this.injectionText })
        });
        if (!res.ok) throw new Error(await res.text());
        this.injectionText = '';
      } catch (err) {
        this.addLog("ERROR", "Injection failed: " + err.message);
      } finally {
        this.isInjecting = false;
      }
    },
    renderActualGraph() {
      const svg = d3.select(this.$refs.svg);
      const width = this.$refs.graphContainer.clientWidth;
      const height = this.$refs.graphContainer.clientHeight;
      svg.selectAll('*').remove();

      const g = svg.append('g');
      svg.call(d3.zoom().on('zoom', (e) => g.attr('transform', e.transform)));

      const nodeMap = {};
      this.nodes.forEach((n, i) => { nodeMap[n.name] = i });

      const links = this.edges
        .filter(e => nodeMap[e.source] !== undefined && nodeMap[e.target] !== undefined)
        .map(e => ({ source: nodeMap[e.source], target: nodeMap[e.target], type: e.type, uuid: e.uuid || 'N/A', fact: e.fact || 'No fact' }));

      const simulation = d3.forceSimulation(this.nodes)
        .force('link', d3.forceLink(links).distance(120))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide(25));

      const link = g.selectAll('.link').data(links).enter().append('line')
        .attr('class', 'link')
        .attr('stroke', '#eaeaeb').attr('stroke-width', 1.5)
        .on('click', (e, d) => {
          this.selectedRel = {
            source: d.source.name, target: d.target.name, label: d.type,
            type: d.type, uuid: d.uuid, fact: d.fact,
            episode: 'N/A', created: new Date().toISOString(), validFrom: 'N/A'
          };
        });

      const node = g.selectAll('.node').data(this.nodes).enter().append('g')
        .attr('class', 'node')
        .call(d3.drag()
          .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
          .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
          .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null }));

      node.append('circle')
        .attr('r', 6)
        .attr('fill', d => this.entityTypes[d.type] || '#888')
        .attr('stroke', '#fff').attr('stroke-width', 1);

      node.append('text')
        .text(d => d.name)
        .attr('dx', 10).attr('dy', 4)
        .attr('fill', '#666').attr('font-size', '10px')
        .attr('font-family', 'IBM Plex Mono, monospace');

      simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
    },
    renderMockGraph() {
      // Create a visually rich but static structural graph to mock the screenshot
      const svg = d3.select(this.$refs.svg)
      const width = this.$refs.graphContainer.clientWidth
      const height = this.$refs.graphContainer.clientHeight
      
      svg.selectAll('*').remove()
      const g = svg.append('g').attr('transform', `translate(${width/2}, ${height/2}) scale(0.6)`)
      
      // Zoom
      svg.call(d3.zoom().on('zoom', (e) => g.attr('transform', e.transform)))

      // Generate dummy nodes
      const nodes = Array.from({length: 300}, (_, i) => ({
        id: i,
        x: (Math.random() - 0.5) * 1200,
        y: (Math.random() - 0.5) * 1200,
        type: Object.keys(this.entityTypes)[Math.floor(Math.random() * 10)]
      }))

      // Force to cluster them somewhat nicely
      d3.forceSimulation(nodes)
        .force('collide', d3.forceCollide(15))
        .force('x', d3.forceX(0).strength(0.04))
        .force('y', d3.forceY(0).strength(0.04))
        .stop()
        .tick(50)

      // Draw faint background connections
      const links = []
      for(let i=0; i<400; i++) {
        const source = nodes[Math.floor(Math.random() * nodes.length)]
        const target = nodes[Math.floor(Math.random() * nodes.length)]
        links.push({source, target})
      }

      g.selectAll('.link')
        .data(links).enter().append('line')
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
        .attr('stroke', '#e0e0e0')
        .attr('stroke-width', 0.5)
        .attr('opacity', 0.6)

      // Draw nodes
      g.selectAll('.node')
        .data(nodes).enter().append('circle')
        .attr('cx', d => d.x).attr('cy', d => d.y)
        .attr('r', d => Math.random() > 0.9 ? 8 : 4)
        .attr('fill', d => this.entityTypes[d.type])
        .attr('stroke', '#fff')
        .attr('stroke-width', 1)
        
      // Draw some labels for large nodes
      g.selectAll('.label')
        .data(nodes.filter(n => Math.random() > 0.95)).enter().append('text')
        .attr('x', d => d.x + 10).attr('y', d => d.y + 4)
        .text(d => `Entity-${d.id}`)
        .attr('font-size', '10px')
        .attr('fill', '#666')
        .attr('font-family', 'sans-serif')
    }
  }
}
</script>

<style scoped>
.dashboard-layout {
  display: flex;
  height: 100vh;
  width: 100%;
  max-width: 100vw;
  overflow: hidden;
  background: var(--bg-primary);
}

.pane {
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  height: 100vh;
}

.pane-left {
  flex: 6;
  border-right: 1px solid var(--border-light);
  background: #fdfdfd;
  overflow-y: auto;
  overflow-x: hidden;
}

.pane-right {
  flex: 4;
  background: #ffffff;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Left Pane Styles */
.pane-header {
  position: absolute;
  top: 16px;
  left: 20px;
  right: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 10;
  pointer-events: none;
}

.pane-header h2 {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.graph-actions {
  display: flex;
  gap: 8px;
  pointer-events: auto;
}

.action-btn {
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

.action-btn.icon-only {
  padding: 6px 8px;
}

.graph-container {
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at center, #ffffff 0%, #f4f4f4 100%);
  cursor: grab;
}

.graph-container:active { cursor: grabbing; }

/* Detail Card Overlay */
.detail-card {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.06);
  z-index: 10;
  display: flex;
  flex-direction: column;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-light);
}

.detail-header h3 {
  font-size: 13px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
}

.detail-title {
  padding: 16px;
  font-size: 13px;
  font-weight: 500;
  background: #fcfcfc;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.rel-label {
  font-family: var(--font-mono);
  font-size: 11px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-secondary);
}

.detail-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 12px;
}

.detail-row {
  display: flex;
  align-items: flex-start;
}

.detail-row .label {
  color: var(--text-muted);
  width: 80px;
  flex-shrink: 0;
}

.detail-row .val {
  color: var(--text-main);
  line-height: 1.5;
}

.mono {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
}

.episodes-section {
  margin-top: 8px;
  margin-bottom: 8px;
}

.episodes-section .label {
  color: var(--text-muted);
  margin-bottom: 4px;
}

.episode-id {
  background: #f8f9fa;
  border: 1px solid var(--border-light);
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
}

/* Legend Overlay */
.legend-card {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(4px);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.03);
  z-index: 10;
}

.legend-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.legend-grid {
  display: grid;
  grid-template-columns: repeat(3, auto);
  gap: x 16px;
  row-gap: 8px;
  column-gap: 16px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-secondary);
}

.color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

/* Right Pane Styles */
.orchestration-panel {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
  display: flex;
  flex-direction: column;
}

.orch-header {
  margin-bottom: 24px;
}

.orch-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.orch-title-row h1 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-main);
}

.status-tag {
  background: #f1f5f9;
  color: var(--text-secondary);
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-light);
}

.orch-subtitle {
  color: var(--text-muted);
  margin-bottom: 12px;
  display: block;
}

.orch-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.alert-box {
  background: #fffaf5;
  border: 1px solid #ffedd5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 32px;
}

.alert-title {
  font-weight: 600;
  font-size: 14px;
  color: #c2410c;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.alert-text {
  font-size: 13px;
  line-height: 1.8;
  color: #555;
  text-align: justify;
}

.injection-panel {
  background: var(--bg-terminal);
  border: 1px solid var(--accent-gold);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 32px;
  box-shadow: 0 4px 15px rgba(232, 168, 56, 0.1);
}

.injection-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.injection-header .icon {
  font-size: 16px;
}

.injection-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-gold);
  margin: 0;
  letter-spacing: 1px;
  text-transform: uppercase;
  font-family: var(--font-mono);
}

.injection-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.injection-input-row {
  display: flex;
  gap: 12px;
}

.injection-input-row input {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-dark);
  color: var(--text-terminal);
  padding: 10px 14px;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 13px;
  transition: all 0.2s;
}

.injection-input-row input:focus {
  outline: none;
  border-color: var(--accent-gold);
  background: rgba(0, 0, 0, 0.2);
}

.injection-input-row button {
  background: var(--accent-gold);
  color: #000;
  border: none;
  padding: 0 20px;
  border-radius: 6px;
  font-weight: 700;
  font-family: var(--font-mono);
  cursor: pointer;
  transition: all 0.2s;
}

.injection-input-row button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(232, 168, 56, 0.3);
}

.injection-input-row button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.fade-slide-enter-active, .fade-slide-leave-active {
  transition: all 0.4s ease;
}
.fade-slide-enter-from, .fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.topics-section {
  margin-bottom: 40px;
}

.topics-section h3, .sequence-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 16px;
}

.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.topic-tag {
  background: #fff7ed;
  color: #ea580c;
  border: 1px solid #ffedd5;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
}

.sequence-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.seq-item {
  padding: 20px 0;
  border-bottom: 1px solid var(--border-light);
}

.seq-item:last-child {
  border-bottom: none;
}

.seq-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.author-type {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-main);
}

.seq-meta {
  color: var(--text-muted);
  font-size: 11px;
}

.seq-content {
  font-size: 13px;
  line-height: 1.7;
  color: #444;
}

/* System Dashboard */
.system-dashboard {
  height: 200px;
  background: var(--bg-terminal);
  border-top: 1px solid var(--border-dark);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.dash-header {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid #222;
  font-family: var(--font-mono);
  font-size: 10px;
  color: #666;
  letter-spacing: 1px;
}

.dash-id {
  color: #444;
}

.dash-logs {
  flex: 1;
  padding: 12px 16px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-terminal);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.log-line {
  display: flex;
  gap: 16px;
}

.log-time {
  color: #555;
  min-width: 90px;
}

.log-arrow {
  color: var(--accent-green);
  margin-right: 4px;
}

.start-sim-btn {
  background: var(--accent-blue);
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.start-sim-btn:hover:not(:disabled) {
  background: #0073cc;
  transform: translateY(-1px);
}

.start-sim-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>
