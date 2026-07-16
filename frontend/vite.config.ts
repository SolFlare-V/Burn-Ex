import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

// Self-signed cert lives at project root /certs/
// Vite dev server serves over HTTPS so getUserMedia works on LAN IPs.
// Modern browsers only allow camera access in a secure context
// (https:// or http://localhost). Plain http://<LAN-IP> is blocked.
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const CERT_DIR = path.resolve(__dirname, '../certs')
const certPath = path.join(CERT_DIR, 'local.crt')
const keyPath  = path.join(CERT_DIR, 'local.key')

const hasCerts = fs.existsSync(certPath) && fs.existsSync(keyPath)
const httpsConfig = hasCerts
  ? { cert: fs.readFileSync(certPath), key: fs.readFileSync(keyPath) }
  : undefined

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    host: '0.0.0.0',   // bind to all interfaces for LAN access
    port: 5173,
    https: httpsConfig,
  },
})
