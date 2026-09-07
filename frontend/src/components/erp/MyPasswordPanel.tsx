import { useState } from 'react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Icon from '../Icon'

// O'Z PAROLINI ALMASHTIRISH (auth-6).
//
// Uch maydon: joriy, yangi, takror.
//
// JORIY parol majburiy — bu shunchaki formallik emas. Ochiq qolgan
// kompyuter yoki o'g'irlangan sessiya bilan begona odam parolni
// o'zgartirib, hisobni butunlay egallab olardi: egasi endi kira
// olmasdi, hujumchi esa qola berardi.
//
// PAROL QOIDASI BU YERDA TAKRORLANMAYDI. Uzunlik talabi serverda
// (`AUTH_PASSWORD_MIN`) va uning xato matni allaqachon nima qilish
// kerakligini aytadi. Bu yerda takrorlansa, ikki joyda ikki xil raqam
// qolib ketishi aniq — loyihada bu xato bir necha marta uchragan.
// Shuning uchun bu yerda faqat FORMANING o'z shartlari tekshiriladi:
// maydonlar to'la va ikki nusxa mos.

export default function MyPasswordPanel({ userId, onClose }: {
  userId: number
  onClose: () => void
}) {
  const [cur, setCur] = useState('')
  const [pw1, setPw1] = useState('')
  const [pw2, setPw2] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const mismatch = pw2.length > 0 && pw1 !== pw2
  const ready = cur.length > 0 && pw1.length > 0 && pw1 === pw2 && !busy

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!ready) return
    setBusy(true); setError(null); setDone(null)
    try {
      const r = await api.setUserPassword(userId, pw1, cur)
      // Yopilgan sessiyalar soni AYTILADI: odam "boshqa
      // qurilmalarimdan chiqarildimi?" degan savolga javob olishi kerak.
      setDone(r.closed_sessions > 0
        ? `Parol almashtirildi. Boshqa ${r.closed_sessions} ta sessiya yopildi — `
          + 'ular qaytadan kirishi kerak.'
        : 'Parol almashtirildi.')
      setCur(''); setPw1(''); setPw2('')
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-lg border bg-card p-5 shadow-lg">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-body font-semibold">Parolni o'zgartirish</h2>
          <button type="button" onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-accent">
            <Icon name="close" size={16} />
          </button>
        </div>

        <div className="space-y-3">
          <Field id="pw-cur" label="Joriy parol" value={cur} onChange={setCur}
            autoFocus autoComplete="current-password" />
          <Field id="pw-new" label="Yangi parol" value={pw1} onChange={setPw1}
            autoComplete="new-password" />
          <Field id="pw-rep" label="Yangi parol (takror)" value={pw2}
            onChange={setPw2} autoComplete="new-password" />
          {mismatch && (
            <p className="text-caption text-destructive">
              Ikki nusxa bir xil emas.
            </p>
          )}
        </div>

        <p className="mt-3 text-micro text-muted-foreground">
          Boshqa qurilmalardagi sessiyalar yopiladi, shu yerdagisi qoladi.
        </p>

        {error && (
          <p className="mt-3 rounded-md border border-destructive/40 bg-destructive/10
                        px-3 py-2 text-caption text-destructive">
            {error}
          </p>
        )}
        {done && (
          <p className="mt-3 rounded-md border border-ok/40 bg-ok-soft px-3 py-2
                        text-caption text-ok-strong">
            {done}
          </p>
        )}

        <div className="mt-4 flex items-center gap-2">
          <Button type="submit" size="sm" disabled={!ready}>
            {busy ? 'Almashtirilyapti…' : 'Almashtirish'}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>
            Yopish
          </Button>
        </div>
      </form>
    </div>
  )
}

/** Maydon YORLIQ bilan bog'langan (`htmlFor` + `id`).
 *
 *  Ilgari yorliq oddiy `<div>` edi: ko'zga bir xil ko'rinardi, lekin
 *  ekran o'quvchisi uchun maydon NOMSIZ qolardi va yorliqni bosish ham
 *  ishlamasdi. Buni interfeys sinovi topdi. */
function Field({ id, label, value, onChange, ...rest }: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  autoFocus?: boolean
  autoComplete?: string
}) {
  return (
    <div>
      <label htmlFor={id}
        className="mb-1 block text-caption font-semibold text-muted-foreground">
        {label}
      </label>
      <Input id={id} type="password" value={value}
        onChange={(e) => onChange(e.target.value)} {...rest} />
    </div>
  )
}
