import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Home from './views/Home.vue'
import PipelineView from './views/PipelineView.vue'
import SimulationView from './views/SimulationView.vue'
import MirofishDashboard from './views/MirofishDashboard.vue'
import AgentDashboard from './views/AgentDashboard.vue'

const routes = [
  { path: '/', component: MirofishDashboard },
  { path: '/dashboard/:projectId?', component: MirofishDashboard, props: true },
  { path: '/home', component: Home },
  { path: '/pipeline', component: PipelineView },
  { path: '/simulation', component: SimulationView },
  { path: '/agents', component: AgentDashboard },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
