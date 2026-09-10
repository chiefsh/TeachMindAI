import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import 'katex/dist/katex.min.css'
import './assets/main.css'

// 仅注册实际用到的图标，避免全量 @element-plus/icons-vue 拖慢首屏
import {
  HomeFilled, Collection, EditPen, VideoPlay, Tickets,
  DataAnalysis, TrendCharts, Setting, SwitchButton,
  Connection, CopyDocument, Printer, Finished, Flag, User,
  Cpu, ChatDotRound, Avatar, Key,
} from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)

// 侧栏等通过字符串名引用的图标必须全局注册；页面内显式 import 的图标无需再挂全局
const icons = {
  HomeFilled, Collection, EditPen, VideoPlay, Tickets,
  DataAnalysis, TrendCharts, Setting, SwitchButton,
  Connection, CopyDocument, Printer, Finished, Flag, User,
  Cpu, ChatDotRound, Avatar, Key,
}
for (const [key, component] of Object.entries(icons)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
