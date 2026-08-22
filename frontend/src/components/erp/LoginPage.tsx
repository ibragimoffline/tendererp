import { useState } from 'react'
import { api, ApiError } from '@/api'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { AuthUser } from '@/types'
import { ErpError } from './erpShared'

// KIRISH EKRANI.
//
// HODIM hisoblari ERP niki (`erp.app_user`): odam — ERP ning
// tushunchasi. Tender-AI esa KOMPANIYA hisobi bilan kiriladi va uning
// o'z kirish ekrani bo'ladi (auth-2).
//
// Xato matni ATAYLAB umumiy: "login yoki parol noto'g'ri". Qaysi biri xato
// ekanini aytish mavjud loginlarni topishga yo'l ochadi.

export default function LoginPage({ onLogin }: { onLogin: (u: AuthUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) return
    setBusy(true); setError(null)
    try {
      onLogin(await api.login(username.trim(), password))
    } catch (err) {
      const a = err as ApiError
      // 503 — kimlik jadvallari bazaga qo'llanmagan. Tender-AI bu
      // yerda AYBDOR EMAS: hodim hisoblari ERP niki.
      setError(a.status === 503
        ? 'Kimlik jadvallari tayyor emas — schema_patch_erp_6.sql qo\'llanmagan.'
        : a.message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <form onSubmit={submit}
        className="w-full max-w-sm rounded-lg border bg-card p-6 shadow-sm">
        <div className="mb-5 flex items-center gap-3">
          {/* Belgi yon paneldagi bilan BIR XIL: kirish ekrani ham
              o'sha ilova ekanini birinchi qarashda bildirsin. */}
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Icon name="briefcase" size={19} />
          </span>
          <div>
            <div className="text-lead font-semibold leading-tight">Tender ERP</div>
            <div className="text-micro text-muted-foreground">ichki ish kartalari</div>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Login
            </div>
            <Input autoFocus autoComplete="username" value={username}
              onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Parol
            </div>
            <Input type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </div>

          {error && <ErpError msg={error} />}

          <Button type="submit" className="w-full"
            disabled={busy || !username.trim() || !password}>
            {busy ? 'Tekshirilmoqda…' : 'Kirish'}
          </Button>
        </div>

        <p className="mt-4 text-micro text-muted-foreground">
          Hodim hisobini administrator ochadi. Birinchi hisob{' '}
          <code>create_user.py</code> skripti orqali.
        </p>
      </form>
    </div>
  )
}
