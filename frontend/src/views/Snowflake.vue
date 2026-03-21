<template>
  <div class="sfg-page">

    <!-- ── Header ── -->
    <header class="sfg-header">
      <span class="sfg-logo">⑂ Story Graph</span>
      <div class="sfg-header-center" v-if="selectedNode">
        <span class="sfg-breadcrumb">
          <span v-for="(anc, i) in ancestorChain" :key="anc.id">
            <span class="sfg-crumb" @click="selectNode(anc.id)">{{ truncate(anc.label, 18) }}</span>
            <span class="sfg-crumb-sep"> / </span>
          </span>
          <span class="sfg-crumb sfg-crumb-active">{{ truncate(selectedNode.label, 22) }}</span>
        </span>
      </div>
      <div class="sfg-header-right">
        <span class="sfg-node-count">{{ Object.keys(nodes).length }} nodes</span>
        <button class="sfg-btn sfg-btn-ghost" @click="confirmClear">🗑 Reset</button>
      </div>
    </header>

    <div class="sfg-body">

      <!-- ── Left: Branch list ── -->
      <aside class="sfg-sidebar">
        <div class="sfg-sidebar-title">BRANCHES</div>
        <div
          v-for="br in branchList"
          :key="br.name"
          class="sfg-branch-item"
          :class="{ active: selectedNode && selectedNode.branchName === br.name }"
        >
          <span class="sfg-branch-dot" :style="{ background: br.color }"></span>
          <div class="sfg-branch-info">
            <div class="sfg-branch-name">{{ br.name }}</div>
            <div class="sfg-branch-stats">{{ branchNodeCount(br.name) }} nodes</div>
          </div>
        </div>
        <div class="sfg-sidebar-hint">Click any node on the canvas to edit it</div>
      </aside>

      <!-- ── Center: Graph canvas ── -->
      <div
        class="sfg-canvas-wrap"
        ref="canvasWrap"
        @mousedown="startPan"
        @mousemove="doPan"
        @mouseup="endPan"
        @mouseleave="endPan"
        @wheel.prevent="doZoom"
      >
        <svg class="sfg-svg" ref="svgEl">
          <defs>
            <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#ccc" />
            </marker>
          </defs>
          <g :transform="`translate(${pan.x},${pan.y}) scale(${zoom})`">

            <!-- Edges -->
            <path
              v-for="edge in computedEdges"
              :key="edge.id"
              :d="edge.path"
              :stroke="edge.color"
              fill="none"
              stroke-width="2"
              stroke-linecap="round"
              :stroke-dasharray="edge.isBranch ? '5,3' : ''"
              opacity="0.7"
            />

            <!-- Branch label at first node of each branch -->
            <text
              v-for="bl in branchLabels"
              :key="'bl-' + bl.name"
              :x="bl.x + DOT_R + 4"
              :y="bl.y - DOT_R - 4"
              font-size="10"
              font-family="IBM Plex Mono, monospace"
              :fill="bl.color"
              font-weight="600"
            >{{ bl.name }}</text>

            <!-- Nodes -->
            <g
              v-for="node in nodesWithLayout"
              :key="node.id"
              class="sfg-node-g"
              :class="{ selected: selectedId === node.id }"
              @click.stop="selectNode(node.id)"
            >
              <!-- Selection ring -->
              <circle
                v-if="selectedId === node.id"
                :cx="node.lx" :cy="node.ly"
                :r="DOT_R + 6"
                fill="none"
                :stroke="getBranchColor(node.branchName)"
                stroke-width="1.5"
                stroke-dasharray="3,2"
                opacity="0.6"
              />
              <!-- Main dot -->
              <circle
                :cx="node.lx" :cy="node.ly"
                :r="DOT_R"
                :fill="getBranchColor(node.branchName)"
                :stroke="selectedId === node.id ? '#000' : 'transparent'"
                stroke-width="2"
              />
              <!-- Content indicator (white centre when node has content) -->
              <circle
                v-if="node.content && node.content.trim()"
                :cx="node.lx" :cy="node.ly"
                r="3"
                fill="white"
                pointer-events="none"
              />
              <!-- Label -->
              <text
                :x="node.lx + DOT_R + 6"
                :y="node.ly + 4"
                font-size="12"
                font-family="Inter, sans-serif"
                :fill="selectedId === node.id ? '#000' : '#444'"
                :font-weight="selectedId === node.id ? '600' : '400'"
                pointer-events="none"
              >{{ truncate(node.label, 28) }}</text>
            </g>

          </g>
        </svg>

        <!-- Canvas toolbar -->
        <div class="sfg-zoom-bar">
          <button @click="zoom = Math.min(zoom * 1.25, 4)" class="sfg-zoom-btn">+</button>
          <span class="sfg-zoom-label">{{ Math.round(zoom * 100) }}%</span>
          <button @click="zoom = Math.max(zoom / 1.25, 0.2)" class="sfg-zoom-btn">−</button>
          <button @click="resetView" class="sfg-zoom-btn" title="Reset view">⌂</button>
        </div>
      </div>

      <!-- ── Right: Node editor ── -->
      <aside class="sfg-detail" v-if="selectedNode" :key="selectedId">

        <div class="sfg-detail-header">
          <div class="sfg-detail-meta">
            <span class="sfg-branch-tag" :style="{ background: getBranchColor(selectedNode.branchName) }">
              {{ selectedNode.branchName }}
            </span>
            <span class="sfg-depth-tag">depth {{ selectedNodeDepth }}</span>
          </div>
          <input
            class="sfg-title-input"
            v-model="selectedNode.label"
            @input="save"
            placeholder="Plot point title..."
          />
        </div>

        <!-- Content area -->
        <div class="sfg-content-block">
          <div class="sfg-block-label">CONTENT</div>
          <textarea
            class="sfg-content-area"
            v-model="selectedNode.content"
            @input="save"
            placeholder="What happens at this plot point? Describe the events, conflict, and emotional beat..."
            rows="7"
          ></textarea>
        </div>

        <!-- AI Suggest -->
        <div class="sfg-suggest-block">
          <button
            class="sfg-btn sfg-btn-ai"
            @click="getSuggestion"
            :disabled="isSuggesting"
          >
            <span v-if="!isSuggesting">✨ AI Suggest</span>
            <span v-else class="sfg-loading">
              <span class="sfg-dot-pulse"></span> Generating...
            </span>
          </button>
          <span v-if="suggestError" class="sfg-error">{{ suggestError }}</span>
        </div>

        <div v-if="suggestion" class="sfg-suggestion-box">
          <div class="sfg-suggestion-hdr">
            <span>✨ Suggestion</span>
            <div class="sfg-suggestion-acts">
              <button class="sfg-btn-xs" @click="useSuggestion">Use</button>
              <button class="sfg-btn-xs sfg-ghost" @click="appendSuggestion">Append</button>
              <button class="sfg-btn-xs sfg-ghost" @click="suggestion = ''">✕</button>
            </div>
          </div>
          <div class="sfg-suggestion-text">{{ suggestion }}</div>
        </div>

        <!-- Graph actions -->
        <div class="sfg-graph-actions">
          <button class="sfg-btn" @click="addChild(selectedId)">
            + Continue
          </button>
          <button class="sfg-btn sfg-btn-branch" @click="openBranchDialog">
            ⑂ Branch here
          </button>
        </div>

        <div class="sfg-danger-row">
          <button class="sfg-btn-danger-link" @click="deleteNode(selectedId)">
            Delete this node
          </button>
        </div>

      </aside>

      <!-- Empty state -->
      <aside class="sfg-detail sfg-detail-empty" v-else>
        <div class="sfg-empty-state">
          <div class="sfg-empty-icon">⑂</div>
          <h3>Story Graph</h3>
          <p>Click any node to view and edit its content.</p>
          <ul>
            <li><strong>+ Continue</strong> — add the next plot point on the same branch</li>
            <li><strong>⑂ Branch here</strong> — fork a new storyline from any node</li>
            <li><strong>✨ AI Suggest</strong> — let the LLM write the plot point based on context</li>
          </ul>
        </div>
      </aside>

    </div>

    <!-- ── Branch dialog ── -->
    <div v-if="showBranchDialog" class="sfg-overlay" @click.self="showBranchDialog = false">
      <div class="sfg-modal">
        <h3>⑂ New Branch</h3>
        <p class="sfg-modal-sub">
          Branching from <strong>{{ selectedNode?.label }}</strong>
          <span class="sfg-branch-tag" :style="{ background: getBranchColor(selectedNode?.branchName) }">
            {{ selectedNode?.branchName }}
          </span>
        </p>
        <label class="sfg-form-label">Branch name</label>
        <input
          class="sfg-form-input"
          v-model="newBranchName"
          placeholder="e.g. alternate-ending, dark-arc, side-story..."
          @keyup.enter="createBranch"
          ref="branchInput"
        />
        <div class="sfg-modal-actions">
          <button
            class="sfg-btn sfg-btn-branch"
            @click="createBranch"
            :disabled="!newBranchName.trim()"
          >Create Branch</button>
          <button class="sfg-btn sfg-btn-ghost" @click="showBranchDialog = false">Cancel</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script>
// ── Constants ──────────────────────────────────────────────────────────────
const COL_WIDTH  = 200   // pixels between branch columns
const ROW_HEIGHT = 90    // pixels between depth levels
const X_OFFSET   = 80    // left padding
const Y_OFFSET   = 60    // top padding
const DOT_R      = 8     // node dot radius

const BRANCH_COLORS = [
  '#0984E3', // blue   — main
  '#e17055', // orange
  '#6c5ce7', // purple
  '#00b894', // green
  '#fdcb6e', // yellow
  '#d63031', // red
  '#74b9ff', // light blue
  '#fd79a8', // pink
  '#55efc4', // mint
  '#a29bfe', // lavender
]

function genId() {
  return 'n_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 6)
}

export default {
  name: 'SnowflakeGraph',

  data() {
    return {
      // Graph data
      nodes: {},      // { [id]: { id, label, content, parentId, branchName } }
      branches: {},   // { [name]: { name, color, col } }

      // UI state
      selectedId: null,
      suggestion: '',
      isSuggesting: false,
      suggestError: '',
      showBranchDialog: false,
      newBranchName: '',

      // Pan / zoom
      zoom: 1,
      pan: { x: 40, y: 40 },
      isPanning: false,
      _panStart: null,

      // layout constant exposed for template
      DOT_R,
    }
  },

  computed: {
    // ── Selected node helpers ──────────────────────────────────────────────

    selectedNode() {
      return this.selectedId ? this.nodes[this.selectedId] : null
    },

    selectedNodeDepth() {
      return this._depths()[this.selectedId] ?? 0
    },

    ancestorChain() {
      if (!this.selectedId) return []
      const chain = []
      let cur = this.nodes[this.selectedId]
      while (cur?.parentId) {
        cur = this.nodes[cur.parentId]
        if (cur) chain.unshift(cur)
      }
      return chain
    },

    // ── Branch list ────────────────────────────────────────────────────────

    branchList() {
      return Object.values(this.branches).sort((a, b) => a.col - b.col)
    },

    // ── Layout ────────────────────────────────────────────────────────────

    _layout() {
      const depths = this._depths()
      const result = {}
      for (const [id, node] of Object.entries(this.nodes)) {
        const col  = this.branches[node.branchName]?.col  ?? 0
        const depth = depths[id] ?? 0
        result[id] = {
          x: X_OFFSET + col * COL_WIDTH,
          y: Y_OFFSET + depth * ROW_HEIGHT,
        }
      }
      return result
    },

    nodesWithLayout() {
      const layout = this._layout()
      return Object.values(this.nodes).map(node => ({
        ...node,
        lx: layout[node.id]?.x ?? 0,
        ly: layout[node.id]?.y ?? 0,
      }))
    },

    computedEdges() {
      const layout = this._layout()
      const edges  = []

      for (const node of Object.values(this.nodes)) {
        if (!node.parentId) continue
        const parent = this.nodes[node.parentId]
        if (!parent) continue

        const px = layout[parent.id]?.x ?? 0
        const py = layout[parent.id]?.y ?? 0
        const cx = layout[node.id]?.x   ?? 0
        const cy = layout[node.id]?.y   ?? 0

        const isBranch = parent.branchName !== node.branchName
        const color = this.getBranchColor(node.branchName)

        let path
        if (!isBranch) {
          // Straight vertical line (same branch)
          path = `M ${px} ${py + DOT_R} L ${cx} ${cy - DOT_R}`
        } else {
          // Git-style cubic bezier branch connector
          const midY = (py + cy) / 2
          path = `M ${px} ${py + DOT_R} C ${px} ${midY}, ${cx} ${midY}, ${cx} ${cy - DOT_R}`
        }

        edges.push({
          id: `${parent.id}→${node.id}`,
          path,
          color,
          isBranch,
        })
      }
      return edges
    },

    // One label per branch, placed above the branch's first node
    branchLabels() {
      const layout  = this._layout()
      const seen    = new Set()
      const labels  = []
      for (const node of Object.values(this.nodes)) {
        if (seen.has(node.branchName)) continue
        // First node on this branch = smallest depth
        seen.add(node.branchName)
        const pos = layout[node.id]
        if (!pos) continue
        labels.push({
          name:  node.branchName,
          color: this.getBranchColor(node.branchName),
          x:     pos.x,
          y:     pos.y,
        })
      }
      return labels
    },
  },

  methods: {
    // ── Depths ────────────────────────────────────────────────────────────

    _depths() {
      const depths = {}
      const compute = (id) => {
        if (depths[id] !== undefined) return depths[id]
        const node = this.nodes[id]
        if (!node || !node.parentId) { depths[id] = 0; return 0 }
        depths[id] = compute(node.parentId) + 1
        return depths[id]
      }
      Object.keys(this.nodes).forEach(id => compute(id))
      return depths
    },

    // ── Branch helpers ────────────────────────────────────────────────────

    getBranchColor(branchName) {
      return this.branches[branchName]?.color || '#999'
    },

    branchNodeCount(branchName) {
      return Object.values(this.nodes).filter(n => n.branchName === branchName).length
    },

    // ── Node operations ───────────────────────────────────────────────────

    selectNode(id) {
      this.selectedId = id
      this.suggestion = ''
      this.suggestError = ''
    },

    addChild(parentId) {
      const parent = this.nodes[parentId]
      if (!parent) return
      const id = genId()
      this.nodes = {
        ...this.nodes,
        [id]: {
          id,
          label:      `Plot Point ${Object.keys(this.nodes).length + 1}`,
          content:    '',
          parentId,
          branchName: parent.branchName,
        },
      }
      this.selectedId = id
      this.save()
    },

    openBranchDialog() {
      this.newBranchName = ''
      this.showBranchDialog = true
      this.$nextTick(() => this.$refs.branchInput?.focus())
    },

    createBranch() {
      const name = this.newBranchName.trim()
      if (!name || !this.selectedId) return

      // Assign next available column
      const nextCol = Object.keys(this.branches).length
      const color   = BRANCH_COLORS[nextCol % BRANCH_COLORS.length]

      this.branches = {
        ...this.branches,
        [name]: { name, color, col: nextCol },
      }

      // Create the first node on the new branch, child of the selected node
      const id = genId()
      this.nodes = {
        ...this.nodes,
        [id]: {
          id,
          label:      `${name} — Start`,
          content:    '',
          parentId:   this.selectedId,
          branchName: name,
        },
      }

      this.selectedId       = id
      this.showBranchDialog = false
      this.newBranchName    = ''
      this.save()
    },

    deleteNode(id) {
      if (!confirm('Delete this node? Its children will be re-connected to its parent.')) return

      const node      = this.nodes[id]
      const newParent = node?.parentId ?? null
      const newNodes  = { ...this.nodes }
      delete newNodes[id]

      // Re-parent direct children
      for (const n of Object.values(newNodes)) {
        if (n.parentId === id) {
          newNodes[n.id] = { ...n, parentId: newParent }
        }
      }

      this.nodes      = newNodes
      this.selectedId = null
      this.save()
    },

    // ── AI Suggest ────────────────────────────────────────────────────────

    async getSuggestion() {
      if (!this.selectedNode) return
      this.isSuggesting  = true
      this.suggestError  = ''
      this.suggestion    = ''

      // Build sibling context (other nodes on same branch, same parent)
      const siblings = Object.values(this.nodes).filter(
        n => n.branchName === this.selectedNode.branchName &&
             n.id !== this.selectedId &&
             n.parentId === this.selectedNode.parentId
      ).map(n => ({ label: n.label, content: n.content }))

      try {
        const res = await fetch('/api/snowflake/node-suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            label:           this.selectedNode.label,
            branch:          this.selectedNode.branchName,
            current_content: this.selectedNode.content,
            ancestor_chain:  this.ancestorChain.map(n => ({
              label:   n.label,
              content: n.content,
            })),
            siblings,
          }),
        })
        const data = await res.json()
        if (data.error) this.suggestError = data.error
        else            this.suggestion   = data.suggestion || ''
      } catch (e) {
        this.suggestError = `Failed: ${e.message}`
      } finally {
        this.isSuggesting = false
      }
    },

    useSuggestion() {
      if (this.selectedNode) {
        this.nodes[this.selectedId].content = this.suggestion
        this.suggestion = ''
        this.save()
      }
    },

    appendSuggestion() {
      if (this.selectedNode) {
        const sep = this.nodes[this.selectedId].content.trim() ? '\n\n' : ''
        this.nodes[this.selectedId].content += sep + this.suggestion
        this.suggestion = ''
        this.save()
      }
    },

    // ── Pan / zoom ────────────────────────────────────────────────────────

    startPan(e) {
      // Don't pan when clicking on a node
      if (e.target.closest('.sfg-node-g')) return
      this.isPanning = true
      this._panStart = { mx: e.clientX, my: e.clientY, px: this.pan.x, py: this.pan.y }
    },

    doPan(e) {
      if (!this.isPanning || !this._panStart) return
      this.pan = {
        x: this._panStart.px + (e.clientX - this._panStart.mx),
        y: this._panStart.py + (e.clientY - this._panStart.my),
      }
    },

    endPan() {
      this.isPanning = false
      this._panStart = null
    },

    doZoom(e) {
      const factor = e.deltaY > 0 ? 0.9 : 1.1
      this.zoom = Math.max(0.15, Math.min(4, this.zoom * factor))
    },

    resetView() {
      this.zoom = 1
      this.pan  = { x: 40, y: 40 }
    },

    // ── Persistence ───────────────────────────────────────────────────────

    save() {
      try {
        localStorage.setItem('sfg_nodes',    JSON.stringify(this.nodes))
        localStorage.setItem('sfg_branches', JSON.stringify(this.branches))
      } catch (_) {}
    },

    load() {
      try {
        const n = localStorage.getItem('sfg_nodes')
        const b = localStorage.getItem('sfg_branches')
        if (n) this.nodes    = JSON.parse(n)
        if (b) this.branches = JSON.parse(b)
      } catch (_) {}
    },

    confirmClear() {
      if (!confirm('Clear all nodes and branches?')) return
      this.nodes    = {}
      this.branches = { main: { name: 'main', color: BRANCH_COLORS[0], col: 0 } }
      this.selectedId = null
      this._initRoot()
    },

    _initRoot() {
      const root = {
        id: 'root', label: 'Story Start', content: '',
        parentId: null, branchName: 'main',
      }
      this.nodes = { root }
      this.selectedId = 'root'
      this.save()
    },

    // ── Util ──────────────────────────────────────────────────────────────

    truncate(text, len) {
      if (!text) return 'Untitled'
      return text.length > len ? text.slice(0, len) + '…' : text
    },
  },

  created() {
    this.load()
    if (Object.keys(this.nodes).length === 0) {
      this.branches = { main: { name: 'main', color: BRANCH_COLORS[0], col: 0 } }
      this._initRoot()
    }
  },
}
</script>

<style scoped>
/* ── Page layout ── */
.sfg-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--bg-primary);
  font-family: var(--font-sans);
  user-select: none;
}

/* ── Header ── */
.sfg-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 20px;
  height: 44px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.sfg-logo {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}

.sfg-header-center {
  flex: 1;
  overflow: hidden;
}

.sfg-breadcrumb {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sfg-crumb {
  cursor: pointer;
  color: var(--text-secondary);
  transition: color 0.1s;
}

.sfg-crumb:hover { color: var(--text-main); }

.sfg-crumb-active { color: var(--text-main); font-weight: 600; }

.sfg-crumb-sep { color: var(--border-light); margin: 0 2px; }

.sfg-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.sfg-node-count {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* ── Body ── */
.sfg-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Left sidebar ── */
.sfg-sidebar {
  width: 180px;
  flex-shrink: 0;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-light);
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sfg-sidebar-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-bottom: 4px;
}

.sfg-branch-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid transparent;
  transition: background 0.1s;
}

.sfg-branch-item.active {
  background: var(--bg-primary);
  border-color: var(--border-light);
}

.sfg-branch-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.sfg-branch-info { flex: 1; min-width: 0; }

.sfg-branch-name {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sfg-branch-stats {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.sfg-sidebar-hint {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: auto;
  padding-top: 12px;
  line-height: 1.5;
}

/* ── Canvas ── */
.sfg-canvas-wrap {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #f8f9fa;
  background-image:
    radial-gradient(circle, #d0d0d0 1px, transparent 1px);
  background-size: 24px 24px;
  cursor: default;
}

.sfg-canvas-wrap.panning { cursor: grabbing; }

.sfg-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.sfg-node-g { cursor: pointer; }

.sfg-node-g:hover circle:first-child {
  opacity: 0.3 !important;
}

/* Zoom bar */
.sfg-zoom-bar {
  position: absolute;
  bottom: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 4px 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.07);
}

.sfg-zoom-btn {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: background 0.1s;
}

.sfg-zoom-btn:hover { background: var(--bg-primary); }

.sfg-zoom-label {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  min-width: 38px;
  text-align: center;
}

/* ── Right detail panel ── */
.sfg-detail {
  width: 320px;
  flex-shrink: 0;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sfg-detail-empty {
  align-items: center;
  justify-content: center;
}

.sfg-empty-state {
  padding: 32px 24px;
  text-align: center;
}

.sfg-empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
  opacity: 0.3;
}

.sfg-empty-state h3 {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--text-secondary);
}

.sfg-empty-state p {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;
  line-height: 1.5;
}

.sfg-empty-state ul {
  list-style: none;
  padding: 0;
  text-align: left;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.8;
}

.sfg-detail-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sfg-detail-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sfg-branch-tag {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  padding: 2px 7px;
  border-radius: 3px;
  font-family: var(--font-mono);
}

.sfg-depth-tag {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.sfg-title-input {
  font-size: 15px;
  font-weight: 600;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-main);
  width: 100%;
  padding: 0;
}

.sfg-title-input::placeholder { color: #ccc; }

/* Content block */
.sfg-content-block {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sfg-block-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.sfg-content-area {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-main);
  font-size: 13px;
  line-height: 1.65;
  padding: 10px 12px;
  font-family: var(--font-sans);
  resize: vertical;
  min-height: 120px;
  user-select: text;
  transition: border-color 0.15s;
}

.sfg-content-area:focus {
  outline: none;
  border-color: #000;
}

.sfg-content-area::placeholder { color: #bbb; font-style: italic; }

/* Suggest block */
.sfg-suggest-block {
  padding: 0 16px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.sfg-error {
  font-size: 11px;
  color: var(--accent-red);
}

/* Suggestion box */
.sfg-suggestion-box {
  margin: 0 16px 12px;
  background: #f0f7ff;
  border: 1px solid #b8d9f8;
  border-radius: 8px;
  overflow: hidden;
}

.sfg-suggestion-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #dbeeff;
  border-bottom: 1px solid #b8d9f8;
  font-size: 12px;
  font-weight: 600;
  color: #1565c0;
}

.sfg-suggestion-acts { display: flex; gap: 4px; }

.sfg-suggestion-text {
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--text-main);
  white-space: pre-wrap;
  user-select: text;
}

/* Graph actions */
.sfg-graph-actions {
  display: flex;
  gap: 8px;
  padding: 0 16px 12px;
}

.sfg-danger-row {
  padding: 4px 16px 16px;
}

.sfg-btn-danger-link {
  font-size: 11px;
  color: var(--text-muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
  transition: color 0.1s;
}

.sfg-btn-danger-link:hover { color: var(--accent-red); }

/* ── Buttons ── */
.sfg-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid var(--border-light);
  background: var(--bg-primary);
  color: var(--text-secondary);
  transition: all 0.12s;
  white-space: nowrap;
  user-select: none;
}

.sfg-btn:hover {
  background: #eee;
  color: var(--text-main);
}

.sfg-btn-ai {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-color: transparent;
  min-width: 130px;
  justify-content: center;
}

.sfg-btn-ai:hover:not(:disabled) { opacity: 0.9; }
.sfg-btn-ai:disabled { opacity: 0.5; cursor: not-allowed; }

.sfg-btn-branch {
  background: #000;
  color: #fff;
  border-color: #000;
}

.sfg-btn-branch:hover { background: #222; }
.sfg-btn-branch:disabled { opacity: 0.4; cursor: not-allowed; }

.sfg-btn-ghost {
  background: transparent;
  border-color: var(--border-light);
}

.sfg-btn-xs {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #1565c0;
  background: #fff;
  color: #1565c0;
  font-weight: 600;
  transition: all 0.1s;
}

.sfg-btn-xs:hover { background: #1565c0; color: #fff; }

.sfg-btn-xs.sfg-ghost {
  border-color: #b8d9f8;
  color: #555;
}

.sfg-btn-xs.sfg-ghost:hover { background: #e3f0fd; color: #333; }

/* Loading pulse */
.sfg-loading {
  display: flex;
  align-items: center;
  gap: 7px;
}

.sfg-dot-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.8);
  animation: pulse 0.9s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1;   transform: scale(1);   }
  50%       { opacity: 0.4; transform: scale(0.7); }
}

/* ── Modal ── */
.sfg-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.sfg-modal {
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 28px 32px;
  width: 380px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}

.sfg-modal h3 {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 8px;
}

.sfg-modal-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sfg-form-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-bottom: 6px;
}

.sfg-form-input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 13px;
  background: var(--bg-primary);
  color: var(--text-main);
  margin-bottom: 18px;
  transition: border-color 0.15s;
}

.sfg-form-input:focus {
  outline: none;
  border-color: #000;
}

.sfg-modal-actions {
  display: flex;
  gap: 10px;
}
</style>
