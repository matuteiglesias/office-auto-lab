import DefaultTheme from 'vitepress/theme'
import StatusBadge from './components/StatusBadge.vue'
import RouteCard from './components/RouteCard.vue'
import './custom.css'

export default { extends: DefaultTheme, enhanceApp({ app }) { app.component('StatusBadge', StatusBadge); app.component('RouteCard', RouteCard) } }
