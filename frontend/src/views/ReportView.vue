<template>
  <div class="report-view">
    <div class="report-content" v-if="report">
      <div class="report-rendered" v-html="renderMarkdown(report)"></div>
    </div>
    <div v-else class="report-empty">
      <p>No report yet. Run a simulation first, then click Synthesize.</p>
      <button @click="$router.push(`/simulation/${projectId}`)">← Back to Simulation</button>
    </div>
    <div class="report-actions">
      <button @click="$router.push(`/interact/${projectId}`)" class="interact-btn">
        💬 Deep Interaction — Chat with Agents
      </button>
    </div>
  </div>
</template>

<script>
export default {
  props: ['projectId'],
  data() { return { report: '' } },
  async mounted() {
    // Try to fetch existing report
    try {
      const res = await fetch('/api/report/synthesize', { method: 'POST' })
      const data = await res.json()
      this.report = data.report || ''
    } catch {}
  },
  methods: {
    renderMarkdown(md) {
      // Basic markdown rendering
      return md
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/^/, '<p>').replace(/$/, '</p>')
    }
  }
}
</script>

<style scoped>
.report-view { max-width: 800px; margin: 0 auto; padding: 32px 20px; }
.report-content { line-height: 1.8; font-size: 15px; }
.report-content :deep(h1) { font-family: var(--font-display); font-size: 28px; color: var(--accent-gold); margin: 32px 0 16px; }
.report-content :deep(h2) { font-family: var(--font-display); font-size: 20px; color: var(--accent-rose); margin: 24px 0 12px; }
.report-content :deep(h3) { font-family: var(--font-mono); font-size: 14px; color: var(--accent-purple); margin: 20px 0 8px; }
.report-content :deep(p) { margin-bottom: 12px; color: var(--text-secondary); }
.report-content :deep(strong) { color: var(--text-primary); }
.report-content :deep(li) { margin-left: 20px; margin-bottom: 4px; color: var(--text-secondary); }
.report-empty { text-align: center; padding: 60px 20px; color: var(--text-muted); }
.report-empty button { margin-top: 16px; padding: 10px 20px; background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); border-radius: 8px; cursor: pointer; }
.report-actions { margin-top: 32px; text-align: center; }
.interact-btn {
  padding: 14px 32px; border-radius: 12px; border: none;
  background: linear-gradient(135deg, var(--accent-purple), var(--accent-rose));
  color: #fff; font-family: var(--font-mono); font-size: 13px; font-weight: 600;
  cursor: pointer; letter-spacing: 1px;
}
</style>
