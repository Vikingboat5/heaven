import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: '宠物乐园',
        short_name: '宠物乐园',
        description: '你的 AI 宠物伙伴',
        theme_color: '#150c2e',
        background_color: '#150c2e',
        display: 'standalone',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      // 宠物生成素材 (精灵帧/manifest)
      '/static': 'http://127.0.0.1:8000',
    },
  },
})
