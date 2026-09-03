import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Icon from '../Icon'
import { cn } from '@/lib/utils'
import type { Act, Invoice } from '@/types'
import { ErpError, can } from './erpShared'
import ActPrint from './ActPrint'

// DALOLATNOMA — faktura ichida.
//
// Faktura "qancha to'lash kerak" deydi, akt "ish BAJARILDI" deydi.
// Ular juftlik bo'lib yuradi, shuning uchun akt shu yerdan chiqariladi
// va qatorlar fakturadan KO'CHIRILADI.
//
// NEGA KO'CHIRILADI, BOG'LANMAYDI: faktura keyin bekor qilinishi mumkin
// (yangisi chiqariladi), akt esa bajarilgan ishning dalili va o'z
// holicha turishi kerak.

const STATUS_CLASS: Record<string, string> = {
  draft: 'bg-muted text-muted-foreground',
  issued: 'bg-secondary text-primary',
  signed: 'bg-ok-soft text-ok-strong',
  cancelled: 'bg-muted text-muted-foreground line-through',
}

/** Keyingi holatlar. Bekor qilingandan va imzolangandan qaytish yo'q. */
function nextStatuses(cur: string): string[] {
  if (cur === 'cancelled' || cur === 'signed') return []
  if (cur === 'draft') return ['issued', 'cancelled']
  return ['signed', 'cancelled']
}

/** Shu holatga o'tkazish uchun kerak bo'lgan AMAL (`api/erp/perm.py`).
 *
 *  Ilgari tugmalar huquqqa qaramay ko'rinardi va broker "Chiqarish" ni
 *  bosib 403 olardi — fakturada esa o'sha tugma umuman ko'rsatilmasdi.
 *  Ikki ekranda ikki xil xatti-harakat: bu yerda faktura qoidasiga
 *  keltiriladi — ruxsat berilmagan tugma CHIQARIB TASHLANADI. */
const AMAL: Record<string, string> = {
  issued: 'hujjat.chiqarish',
  signed: 'hujjat.chiqarish',
  cancelled: 'hujjat.bekor',
}

export default function ActPanel({ inv }: { inv: Invoice }) {
  const f = useFormat()
  const [rows, setRows] = useState<Act[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [number, setNumber] = useState('')
  const [printId, setPrintId] = useState<number | null>(null)

  const load = useCallback(() => {
    api.acts({ invoice_id: inv.id })
      .then(setRows)
      // Akt sxemasi qo'llanmagan bo'lsa (503) blok jim yashiriladi.
      .catch(() => setRows([]))
  }, [inv.id])

  useEffect(load, [load])

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true); setError(null); setNote(null)
    try {
      await fn()
      if (ok) setNote(ok)
      load()
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  const printAct = rows?.find((a) => a.id === printId) || null
  if (printAct) {
    return <ActPrint act={printAct} onClose={() => setPrintId(null)} />
  }

  if (rows === null) return null

  return (
    <div className="mt-3 border-t pt-2">
      <div className="mb-1 flex flex-wrap items-baseline gap-2">
        <span className="text-caption font-semibold text-muted-foreground">
          Dalolatnoma
        </span>
        <span className="text-caption text-muted-foreground">
          "ish bajarildi" — faktura bilan juft yuradigan hujjat
        </span>
      </div>

      {error && <ErpError msg={error} />}
      {note && (
        <div className="mb-2 rounded-md border border-ok/40 bg-ok-soft px-3 py-1.5 text-caption text-ok-strong">
          {note}
        </div>
      )}

      {!!rows.length && (
        <ul className="mb-2 divide-y">
          {rows.map((a) => (
            <li key={a.id}
              className="flex flex-wrap items-center gap-2 py-1.5 text-caption">
              <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                STATUS_CLASS[a.status] || 'bg-muted')}>
                {a.status_label}
              </span>
              <span className="font-medium">{a.number || 'raqamsiz'}</span>
              <span className="tabular">
                {f.money(a.totals?.total ?? 0, a.currency)}
              </span>
              <span className="text-muted-foreground">
                {a.act_date ? f.dateFmt(a.act_date) : '—'}
                {a.signed_at && ` · imzo: ${f.dateFmt(a.signed_at)}`}
              </span>
              <span className="ml-auto flex flex-wrap gap-1">
                <Button size="sm" variant="outline"
                  onClick={() => setPrintId(a.id)}>
                  Bosma shakl
                </Button>
                {nextStatuses(a.status).filter((st) => can(AMAL[st])).map((st) => (
                  <Button key={st} size="sm"
                    variant={st === 'cancelled' ? 'ghost' : 'outline'}
                    disabled={busy}
                    onClick={() => run(
                      () => api.setActStatus(a.id, st,
                        st === 'signed' ? a.act_date : null),
                      st === 'signed' ? 'Imzolandi deb belgilandi' : '')}>
                    {st === 'issued' ? 'Chiqarish'
                      : st === 'signed' ? 'Imzolandi' : 'Bekor qilish'}
                  </Button>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}

      {/* Qoralama fakturadan akt chiqarilmaydi: hali chiqarilmagan
          hujjat bo'yicha "ish bajarildi" deb yozish mantiqsiz. */}
      {inv.status === 'draft' ? (
        <p className="text-caption text-muted-foreground">
          Dalolatnoma faktura chiqarilgandan keyin yoziladi.
        </p>
      ) : inv.status === 'cancelled' ? (
        <p className="text-caption text-muted-foreground">
          Faktura bekor qilingan — yangi dalolatnoma chiqarilmaydi.
          Mavjudlari o'z holicha qoladi.
        </p>
      ) : !can('hujjat.qoralama') ? (
        <p className="text-caption text-muted-foreground">
          Dalolatnoma chiqarish — rahbar yoki menejer huquqi.
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Input className="max-w-40" placeholder="Akt raqami"
            value={number} onChange={(e) => setNumber(e.target.value)} />
          <Button size="sm" variant="outline" disabled={busy}
            onClick={() => run(async () => {
              const a = await api.actFromInvoice(inv.id, {
                number: number.trim() || null,
                act_date: new Date().toISOString().slice(0, 10),
              })
              setNumber('')
              setNote(`Qoralama yaratildi: ${a.filled?.lines ?? 0} ta qator `
                + `fakturadan ko'chirildi.`)
            }, '')}>
            <Icon name="plus" size={13} /> Dalolatnoma chiqarish
          </Button>
          <span className="text-caption text-muted-foreground">
            Qatorlar fakturadan ko'chiriladi
          </span>
        </div>
      )}
    </div>
  )
}
