// Local-only LAN pairing session. The QR this produces encodes nothing but
// a short-lived confirmation URL on this machine's own LAN address — it
// never installs anything, never opens a reverse shell, and never tunnels
// to the public internet. Confirming it only tells the desktop app "the
// owner, standing at the phone, said yes" — the actual device attach still
// goes through already-authorized adb/scrcpy, never through this server.
import { createServer, type Server } from 'node:http'
import { networkInterfaces } from 'node:os'
import { randomBytes } from 'node:crypto'
import QRCode from 'qrcode'
import type { PairSession, PairSessionState, PairStatusEvent } from '../shared/types'

const TOKEN_TTL_MS = 5 * 60 * 1000

interface ActiveSession {
  token: string
  createdAt: number
  expiresAt: number
  state: PairSessionState
}

let server: Server | null = null
let session: ActiveSession | null = null
let onStatusChange: ((event: PairStatusEvent) => void) | null = null

export function setPairStatusListener(cb: (event: PairStatusEvent) => void): void {
  onStatusChange = cb
}

function getLanAddress(): string | null {
  const ifaces = networkInterfaces()
  for (const name of Object.keys(ifaces)) {
    for (const iface of ifaces[name] ?? []) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address
      }
    }
  }
  return null
}

function confirmPageHtml(state: 'ask' | 'ok' | 'expired' | 'used'): string {
  const bodies: Record<string, string> = {
    ask: `
      <h1>Pair with TMIRROR?</h1>
      <p>This confirms this device belongs to you and may connect to TMIRROR on this Wi-Fi network. This link expires in a few minutes and can be used once.</p>
      <form method="POST" action="confirm">
        <button type="submit">Confirm on this phone</button>
      </form>`,
    ok: `<h1>Confirmed</h1><p>Return to TMIRROR on your computer.</p>`,
    expired: `<h1>Link expired</h1><p>Go back to TMIRROR and generate a new QR code.</p>`,
    used: `<h1>Already used</h1><p>This pairing link was already confirmed.</p>`
  }
  return `<!doctype html>
<html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>TMIRROR pairing</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; background: #F8F9FA; color: #212529; margin: 0; padding: 32px 20px; text-align: center; }
  h1 { color: #FF6B5A; font-size: 22px; }
  p { color: #495057; line-height: 1.6; max-width: 360px; margin: 12px auto 24px; }
  button { background: #2BBBAD; color: white; border: none; border-radius: 12px; padding: 14px 28px; font-size: 16px; font-weight: 600; }
</style></head>
<body>${bodies[state]}</body></html>`
}

function stopServer(): void {
  if (server) {
    server.close()
    server = null
  }
}

export async function createPairSession(): Promise<PairSession> {
  stopServer()

  const lanIp = getLanAddress()
  if (!lanIp) {
    throw new Error('No LAN network address found. Connect this PC to Wi-Fi or Ethernet first.')
  }

  const token = randomBytes(16).toString('hex')
  const now = Date.now()
  session = { token, createdAt: now, expiresAt: now + TOKEN_TTL_MS, state: 'pending' }

  server = createServer((req, res) => {
    const url = new URL(req.url ?? '/', `http://${lanIp}`)

    if (req.method === 'GET' && url.pathname === '/pair') {
      const reqToken = url.searchParams.get('token')
      if (!session || reqToken !== session.token) {
        res.writeHead(404).end(confirmPageHtml('expired'))
        return
      }
      if (Date.now() > session.expiresAt) {
        session.state = 'expired'
        res.writeHead(410).end(confirmPageHtml('expired'))
        return
      }
      if (session.state === 'confirmed') {
        res.writeHead(200).end(confirmPageHtml('used'))
        return
      }
      res.writeHead(200, { 'Content-Type': 'text/html' }).end(confirmPageHtml('ask'))
      return
    }

    if (req.method === 'POST' && url.pathname === '/pair/confirm') {
      const reqToken = url.searchParams.get('token')
      if (!session || (reqToken && reqToken !== session.token)) {
        res.writeHead(404).end(confirmPageHtml('expired'))
        return
      }
      if (Date.now() > session.expiresAt) {
        session.state = 'expired'
        res.writeHead(410).end(confirmPageHtml('expired'))
        return
      }
      session.state = 'confirmed'
      onStatusChange?.({ token: session.token, state: 'confirmed' })
      res.writeHead(200, { 'Content-Type': 'text/html' }).end(confirmPageHtml('ok'))
      return
    }

    res.writeHead(404).end('Not found')
  })

  const port = await new Promise<number>((resolvePromise, reject) => {
    server?.on('error', reject)
    server?.listen(0, lanIp, () => {
      const addr = server?.address()
      if (addr && typeof addr === 'object') resolvePromise(addr.port)
      else reject(new Error('Failed to bind pairing server'))
    })
  })

  const pairUrl = `http://${lanIp}:${port}/pair?token=${token}`
  const qrDataUrl = await QRCode.toDataURL(pairUrl, { margin: 1, width: 260 })

  setTimeout(() => {
    if (session?.token === token && session.state === 'pending') {
      session.state = 'expired'
      onStatusChange?.({ token, state: 'expired' })
      stopServer()
    }
  }, TOKEN_TTL_MS)

  return { token, url: pairUrl, qrDataUrl, lanIp, port, expiresAt: session.expiresAt }
}

export function cancelPairSession(): void {
  if (session) {
    onStatusChange?.({ token: session.token, state: 'cancelled' })
  }
  session = null
  stopServer()
}

export function currentPairState(): PairSessionState | null {
  return session?.state ?? null
}
