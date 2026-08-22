import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Icon from '../Icon'
import { cn } from '@/lib/utils'
import type { Invoice } from '@/types'
import { ErpError } from './erpShared'

// KARTADAGI FAKTURALAR — zanjirning oxirgi bo'g'ini:
//   taklif -> shartnoma -> FAKTURA -> to'lov
//
// Bu yerda faqat RO'YXAT va CHIQARISH. Tahrirlash, to'lov va holat —
// "Hisob-fakturalar" bo'limida: bitta hujjatni ikki joyda tahrirlash
// imkoniyati chalkashlik keltirardi.
//
// "Chiqarish" bosilganda qatorlar kartaga AJRATILGAN tovarlardan
// to'ldiriladi (miqdor haqiqiy, narx tender-ai katalogidan). Nima
// to'ldirilgani va nimasi to'ldirilmagani OCHIQ aytiladi.

const STATUS_CLASS: Record<string, string> = {
  draft: 'bg-muted text-muted-foreground',
  issued: 'bg-secondary text-primary',
  sent: 'bg-secondary text-primary',
  paid: 'bg-ok-soft text-ok-strong',
  cancelled: 'bg-muted text-muted-foreground line-through',
}

export default function InvoiceLinks({ oppId }: { oppId: number }) {
  const f = useFormat()
  const [rows, setRows] = useState<Invoice[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [number, setNumber] = useState('')

  const load = useCallback(() => {
    api.invoices({ opportunity_id: oppId })
      .then(setRows)
      // Faktura sxemasi qo'llanmagan bo'lsa (503) blok jim yashiriladi:
      // karta shu tufayli buzilmasligi kerak.
      .catch(() => setRows([]))
  }, [oppId])

  useEffect(load, [load])

  async function create() {
    setBusy(true); setError(null); setNote(null)
    try {
      const inv = await api.invoiceFromOpportunity(oppId, {
        number: number.trim() || null,
        issued_at: new Date().toISOString().slice(0, 10),
      })
      setNumber('')
      const fl = inv.filled
      const parts: string[] = []
      if (fl?.lines) parts.push(`${fl.lines} ta qator ajratilgan tovardan`)
      else parts.push('qator topilmadi — ombordan tovar ajratilmagan')
      if (fl?.no_price) parts.push(`${fl.no_price} tasining narxi yo'q`)
      if (fl?.contract_number) parts.push(`shartnoma: ${fl.contract_number}`)
      setNote(`Qoralama yaratildi. ${parts.join(', ')}. Narxlarni tekshirib, `
        + `"Hisob-fakturalar" bo'limida chiqaring.`)
      load()
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  // Sxema yo'q va faktura ham yo'q — blokni umuman ko'rsatmaymiz.
  if (rows === null) return null

  return (
    <section className="mt-5">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <h3 className="text-body font-semibold">Hisob-fakturalar</h3>
        {rows.length > 0 && (
          <span className="text-caption text-muted-foreground">
            {rows.length} ta
          </span>
        )}
      </div>

      {error && <ErpError msg={error} />}
      {note && (
        <div className="mb-2 rounded-md border border-ok/40 bg-ok-soft px-3 py-1.5 text-caption text-ok-strong">
          {note}
        </div>
      )}

      {rows.length === 0 ? (
        <p className="mb-2 text-caption text-muted-foreground">
          Faktura chiqarilmagan.
        </p>
      ) : (
        <ul className="mb-2 divide-y">
          {rows.map((inv) => (
            <li key={inv.id}
              className="flex flex-wrap items-baseline gap-2 py-1.5 text-caption">
              <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                STATUS_CLASS[inv.status] || 'bg-muted')}>
                {inv.status_label}
              </span>
              <span className="text-body font-medium">
                {inv.number || 'raqamsiz'}
              </span>
              <span className="tabular">
                {f.money(inv.totals?.total ?? 0, inv.currency)}
              </span>
              {(inv.balance ?? 0) > 0 && inv.status !== 'draft'
                && inv.status !== 'cancelled' && (
                <span className="tabular text-soon-strong">
                  qarz: {f.money(inv.balance ?? 0, inv.currency)}
                </span>
              )}
              {inv.contract_number && (
                <span className="text-muted-foreground">
                  · shartnoma {inv.contract_number}
                </span>
              )}
              <span className="ml-auto tabular text-muted-foreground">
                {inv.issued_at ? f.dateFmt(inv.issued_at) : '—'}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input className="max-w-40" placeholder="Faktura raqami"
          value={number} onChange={(e) => setNumber(e.target.value)} />
        <Button size="sm" variant="outline" disabled={busy} onClick={create}>
          <Icon name="plus" size={13} /> Faktura chiqarish
        </Button>
        <span className="text-caption text-muted-foreground">
          Qatorlar ajratilgan tovardan to'ldiriladi; tahrirlash va to'lov —
          "Hisob-fakturalar" bo'limida
        </span>
      </div>
    </section>
  )
}
