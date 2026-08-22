import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import Icon from '../Icon'
import { cn } from '@/lib/utils'
import type { ReserveSuggestions, StockBalance, StockReserve } from '@/types'
import { ErpError } from './erpShared'

// REZERV — "shu karta uchun ajratildi".
//
// Ombor jurnali "nima kirdi, nima chiqdi" deydi. Rezerv esa uchinchi
// holat: tovar HALI CHIQMAGAN, ammo boshqa tenderga va'da qilib
// bo'lmaydi. Shuning uchun u qoldiqni KAMAYTIRMAYDI, MAVJUD miqdorni
// kamaytiradi.
//
// Rezerv KARTANING STATUSIGA bog'langan va uni odam yopmaydi:
//   tasdiqlandi -> qo'yiladi (qo'lda, shu yerdan)
//   yutildi     -> chiqimga aylanadi
//   yutqazildi  -> bo'shaydi
// Shu sababli panel faqat "qo'yish" va "bo'shatish" ni biladi; qolganini
// status o'zgarishi hal qiladi.

const STATE_CLASS: Record<string, string> = {
  held: 'bg-secondary text-primary',
  consumed: 'bg-ok-soft text-ok-strong',
  released: 'bg-muted text-muted-foreground',
}

export default function ReservePanel({ oppId, oppStatus, onChanged }: {
  oppId: number
  oppStatus: string
  onChanged?: () => void
}) {
  const f = useFormat()
  const [rows, setRows] = useState<StockReserve[] | null>(null)
  const [stock, setStock] = useState<StockBalance[]>([])
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [productId, setProductId] = useState('')
  const [qty, setQty] = useState('')
  const [why, setWhy] = useState('')

  // TAKLIF: tender pozitsiyalaridan. Hech narsa avtomatik yozilmaydi —
  // moslashuv nom bo'yicha ishlaydi va har doim ham to'g'ri emas.
  // Shuning uchun odam har qatorni belgilab tasdiqlaydi.
  const [sug, setSug] = useState<ReserveSuggestions | null>(null)
  const [sugOpen, setSugOpen] = useState(false)
  const [picked, setPicked] = useState<Record<number, string>>({})

  const load = useCallback(() => {
    api.reserves({ opportunity_id: oppId })
      .then(setRows)
      .catch((e: Error) => { setError(e.message); setRows([]) })
  }, [oppId])

  useEffect(load, [load])
  useEffect(() => {
    // Mahsulot ro'yxati ombordan: bu yerda katalog yuritilmaydi.
    api.stock().then((d) => setStock(d.items)).catch(() => {})
  }, [])

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true); setError(null); setNote(null)
    try {
      await fn()
      if (ok) setNote(ok)
      load()
      onChanged?.()
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  async function add() {
    const res = await api.addReserve(oppId, {
      product_id: Number(productId), qty: Number(qty),
      note: why.trim() || null,
    })
    setQty(''); setWhy('')
    // Mavjuddan oshib ketish TAQIQ EMAS — server ogohlantiradi.
    setNote(res.warning
      ? `Ajratildi: ${res.qty}. ${res.warning}`
      : `Ajratildi: ${res.qty} ${res.unit || ''}. Mavjud qoldi: ${res.available}`)
  }

  const held = (rows || []).filter((r) => r.status === 'held')
  const chosen = stock.find((s) => String(s.product_id) === productId)

  async function loadSuggestions() {
    setBusy(true); setError(null); setNote(null)
    try {
      const d = await api.reserveSuggestions(oppId)
      setSug(d); setSugOpen(true)
      // Sukut bo'yicha TAKLIF QILINGAN miqdor qo'yiladi, lekin belgi
      // qo'yilmaydi: tasdiqni odam beradi.
      const init: Record<number, string> = {}
      d.items.forEach((it) => {
        if (it.can_reserve) init[it.product_id] = String(it.suggest ?? '')
      })
      setPicked(init)
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  async function confirmSuggestions() {
    const rowsToAdd = Object.entries(picked)
      .filter(([, v]) => Number(v) > 0)
      .map(([k, v]) => ({ product_id: Number(k), qty: Number(v) }))
    if (!rowsToAdd.length) return
    const res = await api.addReserves(oppId, rowsToAdd)
    setSugOpen(false); setSug(null); setPicked({})
    setNote(res.failed
      ? `${res.count} ta ajratildi, ${res.failed} tasi o'tmadi: `
        + res.errors.map((e) => e.error).join('; ')
      : `${res.count} ta pozitsiya ajratildi`)
  }

  return (
    <section className="mt-5">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <h3 className="text-body font-semibold">Ombordan ajratilgan</h3>
        {held.length > 0 && (
          <span className="text-caption text-muted-foreground">
            {held.length} ta pozitsiya band
          </span>
        )}
      </div>

      {error && <ErpError msg={error} />}
      {note && (
        <div className="mb-2 rounded-md border border-ok/40 bg-ok-soft px-3 py-1.5 text-caption text-ok-strong">
          {note}
        </div>
      )}

      {rows && rows.length === 0 && (
        <p className="mb-2 text-caption text-muted-foreground">
          Hali hech narsa ajratilmagan. Ajratilgan tovar omborda qoladi,
          lekin boshqa kartaga "mavjud" ko'rinmaydi.
        </p>
      )}

      {!!rows?.length && (
        <ul className="mb-2 divide-y">
          {rows.map((r) => (
            <li key={r.id}
              className="flex flex-wrap items-baseline gap-2 py-1.5 text-caption">
              <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                STATE_CLASS[r.status] || 'bg-muted')}>
                {r.status_label}
              </span>
              <span className="text-body">{r.product_name}</span>
              <span className="tabular font-semibold">
                {r.qty}{r.unit ? ` ${r.unit}` : ''}
              </span>
              {r.note && <span className="text-muted-foreground">· {r.note}</span>}
              <span className="ml-auto tabular text-muted-foreground">
                {r.created_by || '—'}
                {r.created_at ? ` · ${f.dateFmt(r.created_at)}` : ''}
              </span>
              {r.status === 'held' && (
                <Button size="sm" variant="ghost" disabled={busy}
                  onClick={() => run(() => api.releaseReserve(r.id),
                    'Rezerv bo\'shatildi')}>
                  Bo'shatish
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* --- TENDER POZITSIYALARIDAN TAKLIF --- */}
      {['confirmed', 'preparing', 'submitted'].includes(oppStatus) && (
        <div className="mb-3">
          {!sugOpen ? (
            <Button size="sm" variant="outline" disabled={busy}
              onClick={loadSuggestions}>
              <Icon name="search" size={13} /> Tender pozitsiyalaridan taklif
            </Button>
          ) : (
            <div className="rounded-md border bg-background p-3">
              <div className="mb-2 flex flex-wrap items-baseline gap-2">
                <span className="text-body font-semibold">
                  Tenderga nima kerak
                </span>
                <span className="text-caption text-muted-foreground">
                  Moslashuv nom bo'yicha ishlaydi — tekshirib tasdiqlang
                </span>
                <Button size="sm" variant="ghost" className="ml-auto"
                  onClick={() => { setSugOpen(false); setSug(null) }}>
                  Yopish
                </Button>
              </div>

              {sug?.warning && (
                <div className="mb-2 rounded border border-soon/40 bg-soon-soft px-2 py-1 text-caption text-soon-strong">
                  {sug.warning}
                </div>
              )}

              {sug && sug.items.length === 0 && (
                <p className="text-caption text-muted-foreground">
                  Tender pozitsiyalariga mos mahsulot topilmadi.
                </p>
              )}

              {!!sug?.items.length && (
                <ul className="divide-y">
                  {sug.items.map((it) => (
                    <li key={it.product_id}
                      className="flex flex-wrap items-center gap-2 py-1.5 text-caption">
                      <span className="text-body">{it.product_name}</span>
                      <span className="text-muted-foreground">
                        · {it.position} ({it.position_amount || '—'})
                      </span>
                      <span className="tabular text-muted-foreground">
                        kerak: {it.required ?? '—'}
                        {it.held > 0 && ` · ajratilgan: ${it.held}`}
                        {' · mavjud: '}{it.available ?? '—'}
                      </span>
                      {it.reason && (
                        <span className="text-soon-strong">{it.reason}</span>
                      )}
                      <span className="ml-auto flex items-center gap-1">
                        <Input className="h-8 w-24" inputMode="decimal"
                          disabled={!it.can_reserve}
                          value={picked[it.product_id] ?? ''}
                          onChange={(e) => setPicked({
                            ...picked, [it.product_id]: e.target.value,
                          })} />
                        {it.unit && (
                          <span className="text-muted-foreground">{it.unit}</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              {/* Moslashmagan pozitsiyalar ham ko'rsatiladi: "katalogda
                  yo'q" degan javob ham ma'lumot. */}
              {!!sug?.unmatched.length && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-caption text-muted-foreground">
                    Katalogda topilmagan {sug.unmatched.length} ta pozitsiya
                  </summary>
                  <ul className="mt-1 space-y-0.5">
                    {sug.unmatched.map((u, i) => (
                      <li key={i} className="text-caption text-muted-foreground">
                        {u.position} ({u.amount || '—'}) — {u.reason}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              {!!sug?.items.length && (
                <Button size="sm" className="mt-2" disabled={busy}
                  onClick={() => run(confirmSuggestions, '')}>
                  Tasdiqlash va ajratish
                </Button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Rezerv faqat tasdiqlangandan keyin va yakuniygacha qo'yiladi —
          serverda ham shu qoida bor, bu yerda faqat forma yashiriladi. */}
      {['confirmed', 'preparing', 'submitted'].includes(oppStatus) ? (
        <div className="grid gap-2 sm:grid-cols-4">
          <div className="sm:col-span-2">
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Mahsulot
            </div>
            <Select value={productId} onValueChange={setProductId}>
              <SelectTrigger className="bg-card text-body">
                <SelectValue placeholder="Tanlang" />
              </SelectTrigger>
              <SelectContent>
                {stock.map((s) => (
                  <SelectItem key={s.product_id} value={String(s.product_id)}>
                    {s.product_name} — mavjud: {s.available}{s.unit ? ` ${s.unit}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Miqdor
            </div>
            <Input inputMode="decimal" value={qty}
              onChange={(e) => setQty(e.target.value)} />
          </div>
          <div>
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Izoh
            </div>
            <Input value={why} onChange={(e) => setWhy(e.target.value)} />
          </div>
          <div className="sm:col-span-4 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={busy || !productId || !qty}
              onClick={() => run(add, '')}>
              <Icon name="plus" size={13} /> Ajratish
            </Button>
            {chosen && (
              <span className="text-caption text-muted-foreground">
                {chosen.product_name}: qoldiq {chosen.qty}, band {chosen.reserved},
                mavjud {chosen.available}
              </span>
            )}
          </div>
        </div>
      ) : (
        <p className="text-caption text-muted-foreground">
          Rezerv "Qatnashish tasdiqlandi" bosqichidan boshlab qo'yiladi.
          Yakuniy statusda esa avtomatik yopiladi: yutilsa — chiqimga
          aylanadi, yutqazilsa — bo'shaydi.
        </p>
      )}
    </section>
  )
}
