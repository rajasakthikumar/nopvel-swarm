<template>
  <div class="graph-view">
    <div class="sidebar">
      <h2>🕸️ Knowledge Graph</h2>
      <p class="stat">{{ nodes.length }} entities • {{ edges.length }} relationships</p>

      <div class="entity-list">
        <div v-for="node in nodes" :key="node.name" class="entity-item"
             :class="{ selected: selected === node.name }"
             @click="selectEntity(node.name)">
          <span class="entity-type" :style="{ color: typeColor(node.type) }">{{ node.type }}</span>
          <span class="entity-name">{{ node.name }}</span>
        </div>
      </div>

      <button @click="proceed" class="proceed-btn" :disabled="!nodes.length">
        Continue → Generate Agents
      </button>
    </div>

    <div class="graph-container" ref="graphContainer">
      <svg ref="svg" width="100%" height="100%"></svg>
    </div>

    <!-- New Node Floating Button -->
    <button @click="showNewNodeModal = true" class="add-node-btn">+ New Node</button>

    <!-- New Node Modal -->
    <div v-if="showNewNodeModal" class="modal-overlay" @click.self="showNewNodeModal = false">
      <div class="modal-content">
        <h3>Add New Entity</h3>
        <input v-model="newNode.name" placeholder="Entity Name" />
        <select v-model="newNode.type">
          <option value="character">Character</option>
          <option value="place">Place</option>
          <option value="faction">Faction</option>
          <option value="artifact">Artifact</option>
          <option value="magic_system">Magic/Power</option>
          <option value="event">Event</option>
          <option value="concept">Concept</option>
          <option value="creature">Creature</option>
          <option value="culture">Culture</option>
        </select>
        <textarea v-model="newNode.description" placeholder="Description/Lore"></textarea>
        <div class="modal-actions">
          <button @click="showNewNodeModal = false" class="cancel-btn">Cancel</button>
          <button @click="addNode" class="save-btn" :disabled="!newNode.name.trim()">Add Node</button>
        </div>
      </div>
    </div>

    <div v-if="selectedEntity" class="detail-panel">
      <h3>{{ selectedEntity.entity?.name }}</h3>
      <p class="detail-type" :style="{ color: typeColor(selectedEntity.entity?.type) }">
        {{ selectedEntity.entity?.type }}
      </p>
      <p class="detail-desc">{{ selectedEntity.entity?.description }}</p>
      <div class="detail-actions">
        <button @click="deleteSelectedNode" class="delete-btn">🗑️ Delete Entity</button>
      </div>
      <div v-if="selectedEntity.relationships?.length" class="detail-rels">
        <h4>Relationships</h4>
        <div v-for="r in selectedEntity.relationships" :key="r.target" class="rel-item">
          <span class="rel-type">{{ r.rel_type }}</span> → {{ r.target }}
          <button @click="deleteEdge(selectedEntity.entity.name, r.target, r.rel_type)" class="del-edge-btn">✕</button>
        </div>
      </div>
    </div>

    <!-- Edge Drawing Modal -->
    <div v-if="newEdge.source" class="modal-overlay" @click.self="cancelEdge">
      <div class="modal-content">
        <h3>New Relationship</h3>
        <p><strong>From:</strong> {{ newEdge.source.name }} <br><strong>To:</strong> {{ newEdge.target.name }}</p>
        <input v-model="newEdge.type" placeholder="Relationship Type (e.g. ALLY, ENEMY, CREATOR)" />
        <textarea v-model="newEdge.description" placeholder="Optional description"></textarea>
        <div class="modal-actions">
          <button @click="cancelEdge" class="cancel-btn">Cancel</button>
          <button @click="saveEdge" class="save-btn" :disabled="!newEdge.type.trim()">Link Entities</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import * as d3 from 'd3'

const TYPE_COLORS = {
  character: '#E8A838', place: '#00B894', faction: '#C75B7A',
  artifact: '#6C5CE7', magic_system: '#0984E3', event: '#E17055',
  concept: '#636E72', creature: '#D63031', culture: '#FDCB6E',
}

export default {
  name: 'GraphView',
  props: ['projectId'],
  data() {
    return {
      nodes: [], edges: [], selected: null, selectedEntity: null,
      showNewNodeModal: false,
      newNode: { name: '', type: 'character', description: '' },
      newEdge: { source: null, target: null, type: '', description: '' },
      dragLine: null
    }
  },
  async mounted() {
    const res = await fetch(`/api/graph/query/${this.projectId}`)
    const data = await res.json()
    this.nodes = data.nodes || []
    this.edges = data.edges || []
    this.$nextTick(() => this.renderGraph())
  },
  methods: {
    typeColor(type) { return TYPE_COLORS[type] || '#636E72' },
    async selectEntity(name) {
      this.selected = name
      try {
        const res = await fetch(`/api/graph/entity/${this.projectId}/${encodeURIComponent(name)}`)
        this.selectedEntity = await res.json()
      } catch {
        this.selectedEntity = { entity: this.nodes.find(n => n.name === name), relationships: [] }
      }
    },
    async addNode() {
      if (!this.newNode.name.trim()) return;
      await fetch(`/api/graph/entity/${this.projectId}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.newNode)
      });
      this.showNewNodeModal = false;
      this.newNode = { name: '', type: 'character', description: '' };
      await this.refreshGraph();
    },
    async deleteSelectedNode() {
      if (!this.selectedEntity || !confirm(`Delete entity "${this.selected}"?`)) return;
      await fetch(`/api/graph/entity/${this.projectId}/${encodeURIComponent(this.selected)}`, { method: 'DELETE' });
      this.selected = null;
      this.selectedEntity = null;
      await this.refreshGraph();
    },
    async deleteEdge(source, target, type) {
      if (!confirm(`Delete relationship: ${source} -[${type}]-> ${target}?`)) return;
      await fetch(`/api/graph/relationship/${this.projectId}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, target, type })
      });
      await this.refreshGraph();
      if (this.selected) this.selectEntity(this.selected);
    },
    async saveEdge() {
      if (!this.newEdge.type.trim()) return;
      await fetch(`/api/graph/relationship/${this.projectId}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: this.newEdge.source.name,
          target: this.newEdge.target.name,
          type: this.newEdge.type,
          description: this.newEdge.description
        })
      });
      this.cancelEdge();
      await this.refreshGraph();
    },
    cancelEdge() {
      this.newEdge = { source: null, target: null, type: '', description: '' };
      if (this.dragLine) this.dragLine.remove();
    },
    async refreshGraph() {
      const res = await fetch(`/api/graph/query/${this.projectId}`)
      const data = await res.json()
      this.nodes = data.nodes || []
      this.edges = data.edges || []
      this.renderGraph()
    },
    proceed() {
      this.$router.push(`/simulation/${this.projectId}`)
    },
    renderGraph() {
      const svg = d3.select(this.$refs.svg)
      const container = this.$refs.graphContainer
      const width = container.clientWidth
      const height = container.clientHeight

      svg.selectAll('*').remove()

      const g = svg.append('g')

      // Zoom
      svg.call(d3.zoom().on('zoom', (e) => g.attr('transform', e.transform)))

      const nodeMap = {}
      this.nodes.forEach((n, i) => { nodeMap[n.name] = i })

      const links = this.edges
        .filter(e => nodeMap[e.source] !== undefined && nodeMap[e.target] !== undefined)
        .map(e => ({ source: nodeMap[e.source], target: nodeMap[e.target], type: e.type }))

      const simulation = d3.forceSimulation(this.nodes)
        .force('link', d3.forceLink(links).distance(120))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide(40))

      // Drag line (for edge creation)
      this.dragLine = g.append('path')
        .attr('class', 'dragline hidden')
        .attr('d', 'M0,0L0,0')
        .attr('stroke', 'var(--accent-gold)')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '5,5')
        .attr('pointer-events', 'none')

      const link = g.selectAll('.link').data(links).enter().append('line')
        .attr('class', 'link')
        .attr('stroke', '#1a1a2e').attr('stroke-width', 1.5)

      const node = g.selectAll('.node').data(this.nodes).enter().append('g')
        .attr('class', 'node')
        .on('click', (e, d) => {
          if (e.shiftKey) {
            if (!this.newEdge.source) {
              this.newEdge.source = d
              this.dragLine.classed('hidden', false)
            } else if (this.newEdge.source.name !== d.name) {
              this.newEdge.target = d
              this.dragLine.classed('hidden', true)
            }
            e.stopPropagation()
          } else {
            this.selectEntity(d.name)
          }
        })
        .call(d3.drag()
          .on('start', (e, d) => { 
            if (e.sourceEvent.shiftKey) return; // Don't drag if linking
            if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y 
          })
          .on('drag', (e, d) => { 
            if (e.sourceEvent.shiftKey) return;
            d.fx = e.x; d.fy = e.y 
          })
          .on('end', (e, d) => { 
            if (e.sourceEvent.shiftKey) return;
            if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null 
          }))

      svg.on('mousemove', (e) => {
        if (this.newEdge.source && !this.newEdge.target) {
          const [mx, my] = d3.pointer(e, g.node())
          this.dragLine.attr('d', `M${this.newEdge.source.x},${this.newEdge.source.y}L${mx},${my}`)
        }
      })

      svg.on('click', () => {
        if (this.newEdge.source && !this.newEdge.target) {
          this.cancelEdge()
        }
      })

      node.append('circle')
        .attr('r', d => 8 + (d.type === 'character' ? 4 : 0))
        .attr('fill', d => this.typeColor(d.type))
        .attr('opacity', 0.85)
        .attr('stroke', '#fff').attr('stroke-width', 0)

      node.filter(d => d.name === this.selected).select('circle').attr('stroke-width', 2)

      node.append('text')
        .text(d => d.name)
        .attr('dx', 14).attr('dy', 4)
        .attr('fill', '#888')
        .attr('font-size', '11px')
        .attr('font-family', 'IBM Plex Mono, monospace')

      simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
        node.attr('transform', d => `translate(${d.x},${d.y})`)
        if (this.newEdge.source && !this.newEdge.target) {
          // Keep dragline attached to source node even as layout shifts
          const [mx, my] = d3.pointer({ clientX: window.event?.clientX, clientY: window.event?.clientY }, g.node())
          this.dragLine.attr('d', `M${this.newEdge.source.x},${this.newEdge.source.y}L${mx},${my}`)
        }
      })
    }
  }
}
</script>

<style scoped>
.graph-view { display: flex; height: calc(100vh - 50px); }
.sidebar {
  width: 260px; padding: 16px; border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden;
}
.sidebar h2 { font-family: var(--font-mono); font-size: 14px; color: var(--accent-gold); margin-bottom: 4px; }
.stat { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); margin-bottom: 16px; }
.entity-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.entity-item {
  display: flex; gap: 8px; padding: 6px 10px; border-radius: 6px;
  cursor: pointer; font-size: 12px; transition: background 0.2s;
}
.entity-item:hover { background: var(--bg-elevated); }
.entity-item.selected { background: var(--bg-elevated); border-left: 2px solid var(--accent-gold); }
.entity-type { font-family: var(--font-mono); font-size: 9px; min-width: 60px; }
.entity-name { color: var(--text-primary); font-family: var(--font-mono); font-weight: 500; }

.proceed-btn {
  margin-top: 12px; padding: 12px; border-radius: 10px; border: none;
  background: linear-gradient(135deg, var(--accent-gold), var(--accent-rose));
  color: #fff; font-family: var(--font-mono); font-size: 12px; font-weight: 600;
  cursor: pointer; letter-spacing: 1px;
}
.proceed-btn:disabled { background: var(--bg-elevated); color: var(--text-muted); }

.graph-container { flex: 1; background: var(--bg-primary); overflow: hidden; }

.detail-panel {
  width: 280px; padding: 16px; border-left: 1px solid var(--border);
  overflow-y: auto;
}
.detail-panel h3 { font-family: var(--font-mono); font-size: 14px; margin-bottom: 4px; }
.detail-type { font-family: var(--font-mono); font-size: 10px; margin-bottom: 12px; }
.detail-desc { font-size: 13px; line-height: 1.7; color: var(--text-secondary); margin-bottom: 16px; }
.detail-rels h4 { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); margin-bottom: 8px; }
.rel-item {
  font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary);
  padding: 4px 0; border-bottom: 1px solid var(--border);
}
.rel-type { color: var(--accent-purple); }

.add-node-btn {
  position: absolute; bottom: 20px; left: 280px; z-index: 10;
  padding: 10px 18px; border-radius: 20px; border: none;
  background: var(--accent-gold); color: #000;
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.modal-overlay {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0,0,0,0.7); display: flex; align-items: center;
  justify-content: center; z-index: 100; backdrop-filter: blur(4px);
}
.modal-content {
  background: var(--bg-secondary); border: 1px solid var(--border);
  border-radius: 16px; padding: 24px; width: 400px; display: flex;
  flex-direction: column; gap: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.modal-content h3 { font-family: var(--font-display); color: var(--accent-gold); margin-bottom: 8px; }
.modal-content input, .modal-content select, .modal-content textarea {
  background: var(--bg-primary); border: 1px solid var(--border);
  padding: 10px; border-radius: 8px; color: var(--text-primary);
  font-family: var(--font-body);
}
.modal-content textarea { height: 100px; resize: none; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }
.cancel-btn, .save-btn, .delete-btn {
  padding: 8px 16px; border-radius: 8px; cursor: pointer;
  font-family: var(--font-mono); font-size: 11px; font-weight: 600;
}
.cancel-btn { background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border); }
.save-btn { background: var(--accent-gold); color: #000; border: none; }
.delete-btn { background: rgba(214,48,49,0.1); color: var(--accent-red); border: 1px solid rgba(214,48,49,0.3); width: 100%; margin-top: 10px; }

.detail-actions { margin-bottom: 20px; }
.del-edge-btn {
  background: transparent; border: none; color: var(--text-muted);
  cursor: pointer; font-size: 14px; margin-left: 8px;
  transition: color 0.2s;
}
.del-edge-btn:hover { color: var(--accent-red); }

.detail-rels { margin-top: 20px; }
.rel-item {
  display: flex; align-items: center; justify-content: space-between;
}
.hidden { display: none; }
</style>
