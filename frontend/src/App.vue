<template>
  <div id="mirofish-app">
    <header class="top-nav">
      <div class="nav-left">
        <span class="logo">MIROFISH</span>
      </div>
      <div class="nav-center">
        <router-link to="/" class="nav-tab" active-class="active">Dashboard</router-link>
        <router-link to="/pipeline" class="nav-tab" active-class="active">Live Feed</router-link>
        <router-link to="/agents" class="nav-tab" active-class="active">Agents</router-link>
        <router-link to="/snowflake" class="nav-tab" active-class="active">❄️ Snowflake</router-link>
        <router-link to="/home" class="nav-tab" active-class="active">Workshop</router-link>
      </div>
      <div class="nav-right">
        <span class="step-indicator">PHASE 2 <strong>ENVIRONMENT READY</strong></span>
        <span class="status-ready"><span class="dot"></span> Online</span>
      </div>
    </header>
    <div class="main-content">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </div>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap');

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #f8f9fa;
  --bg-panel: #ffffff;
  --bg-terminal: #000000;
  --border-light: #eaebec;
  --border-dark: #333333;
  --text-main: #111111;
  --text-secondary: #555555;
  --text-muted: #888888;
  --text-terminal: #b0b0b0;
  
  /* Accent Colors */
  --accent-orange: #f26d40;
  --accent-blue: #0984E3;
  --accent-green: #10b981;
  --accent-red: #ef4444;
  
  --font-sans: 'Inter', -apple-system, sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
}

body {
  background: var(--bg-primary);
  color: var(--text-main);
  font-family: var(--font-sans);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

#mirofish-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.top-nav {
  height: 48px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 100;
  flex-shrink: 0;
}

.nav-left .logo {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 1.5px;
  color: #000;
}

.nav-center {
  display: flex;
  gap: 32px;
  height: 100%;
}

.nav-tab {
  display: inline-flex;
  align-items: center;
  height: 100%;
  padding: 0 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-tab:hover {
  color: var(--text-main);
}

.nav-tab.active, .nav-tab.router-link-exact-active {
  color: var(--text-main);
  border-bottom-color: var(--text-main);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 24px;
  font-size: 12px;
}

.step-indicator {
  color: var(--text-muted);
}

.step-indicator strong {
  color: var(--text-main);
  margin-left: 4px;
}

.status-ready {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--accent-green);
  font-weight: 500;
}

.status-ready .dot {
  width: 6px;
  height: 6px;
  background-color: var(--accent-green);
  border-radius: 50%;
}

.main-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #dbdbdb;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #c0c0c0;
}
</style>
