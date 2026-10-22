import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 自签证书(供局域网/手机 HTTPS 直连测试)。存在则 dev 启 HTTPS,否则回退 HTTP。
const certDir = resolve(__dirname, '../certs')
const keyPath = resolve(certDir, 'key.pem')
const certPath = resolve(certDir, 'cert.pem')
const https =
  existsSync(keyPath) && existsSync(certPath)
    ? { key: readFileSync(keyPath), cert: readFileSync(certPath) }
    : undefined

// /api 反代到后端:前端同源调 /api/*,免 CORS;Funnel/局域网只需暴露前端一个端口。
const proxy = {
  '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true, secure: false },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // 绑 0.0.0.0,局域网可访问
    https,               // dev 自签 HTTPS(局域网手机直连用)
    proxy,
    allowedHosts: true,  // 允许经 Tailscale Funnel(*.ts.net)等域名访问
  },
  preview: {
    host: true,
    proxy,
    allowedHosts: true,  // 生产构建经 Funnel 对外
  },
})
