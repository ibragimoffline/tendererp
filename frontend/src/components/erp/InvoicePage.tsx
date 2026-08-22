import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import Icon from '../Icon'
import { cn } from '@/lib/utils'
import type { ClientRow, Invoice, InvoiceLine } from '@/types'
import { ErpError } from './erpShared'
import InvoicePrint from './InvoicePrint'
import ActPanel from './ActPanel'

// HISOB-FAKTURA (5B-2).
//
// UCH NARSA EKRANDA KO'RINIB TURISHI KERAK, chunki ular modelning
// asosiy qarorlari:
//   1. QQS stavkasi HAR QATORDA — sukut mijoz passportidan olinadi,
//      lekin qator uni O'ZIDA saqlaydi. Shuning uchun stavka qatorda
//      tahrirlanadi, sarlavhada emas.
//   2. Summalar SAQLANMAYDI — har safar qatorlardan hisoblanadi.
//   3. Chiqarilgan hujjat MUZLATILGAN: tahrir tugmalari yo'qoladi.
//      Xato bo'lsa bekor qilinadi va yangisi chiqariladi.
//
// EKSPORT tugmasi YO'Q: format hali sozlanmagan va ishlamaydigan tugma
// turgani yolg'on va'da bo'lardi (`api/erp/invoice_export.py`).

const STATUS_CLASS: Record<string, string> = {
  draft: 'bg-muted text-muted-foreground',
  issued: 'bg-secondary text-primary',
  sent: 'bg-secondary text-primary',
  paid: 'bg-ok-soft text-ok-strong',
  cancelled: 'bg-muted text-muted-foreground line-through',
}

/** Keyingi mumkin bo'lgan holatlar. Bekor qilingandan qaytish yo'q. */
function nextStatuses(cur: string): string[] {
  if (cur === 'cancelled' || cur === 'paid') return []
  if (cur === 'draft') return ['issued', 'cancelled']
  return ['sent', 'cancelled']
}

export default function InvoicePage() {
  const f = useFormat()
  const [rows, setRows] = useState<Invoice[] | null>(null)
  const [clients, setClients] = useState<ClientRow[]>([])
  const [statuses, setStatuses] = useState<{ code: string; label: string }[]>([])
  const [methods, setMethods] = useState<{ code: string; label: string }[]>([])
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [openId, setOpenId] = useState<number | null>(null)
  const [filter, setFilter] = useState('')
  // Bosma shakl: brauzer chop etadi (PDF kutubxonasi yo'q).
  const [printId, setPrintId] = useState<number | null>(null)

  // Yangi faktura
  const [newClient, setNewClient] = useState('')
  const [newNumber, setNewNumber] = useState('')

  // Yangi qator
  const [line, setLine] = useState({ name: '', qty: '', price: '', vat: '' })
  // Yangi to'lov
  const [pay, setPay] = useState({ amount: '', paid_at: '', method: 'bank' })

  const load = useCallback(() => {
    api.invoices(filter ? { status: filter } : undefined)
      .then(setRows)
      .catch((e: Error) => { setError(e.message); setRows([]) })
  }, [filter])

  useEffect(load, [load])
  useEffect(() => {
    api.clients().then(setClients).catch(() => {})
    api.meta().then((m) => {
      setStatuses(m.invoice_statuses || [])
      setMethods(m.payment_methods || [])
    }).catch(() => {})
  }, [])

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

  const open = rows?.find((r) => r.id === openId) || null
  const printInv = rows?.find((r) => r.id === printId) || null
  const client = clients.find((c) => String(c.id) === newClient)

  if (!rows && !error) return <Skeleton className="h-64 w-full rounded-lg" />

  if (printInv) {
    return <InvoicePrint inv={printInv} onClose={() => setPrintId(null)} />
  }

  return (
    <div className="space-y-4">
      {error && <ErpError msg={error} />}
      {note && (
        <div className="rounded-lg border border-ok/40 bg-ok-soft px-3 py-2 text-body text-ok-strong">
          {note}
        </div>
      )}

      {/* --- yangi faktura --- */}
      <section className="rounded-lg border bg-card p-4">
        <h2 className="mb-1 text-body font-semibold">Yangi hisob-faktura</h2>
        <p className="mb-3 text-caption text-muted-foreground">
          Ikkala tomonning rekvizitlari SHU PAYTDA ko'chiriladi va keyin
          o'zgarmaydi. QQS stavkasi mijoz passportidan olinadi.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-56">
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Mijoz
            </div>
            <Select value={newClient} onValueChange={setNewClient}>
              <SelectTrigger className="bg-card text-body">
                <SelectValue placeholder="Tanlang" />
              </SelectTrigger>
              <SelectContent>
                {clients.filter((c) => c.active).map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Raqam
            </div>
            <Input className="max-w-40" value={newNumber}
              onChange={(e) => setNewNumber(e.target.value)} />
          </div>
          <Button size="sm" disabled={busy || !newClient}
            onClick={() => run(async () => {
              const inv = await api.createInvoice({
                client_id: Number(newClient),
                number: newNumber.trim() || null,
                issued_at: new Date().toISOString().slice(0, 10),
              })
              setNewNumber(''); setOpenId(inv.id)
            }, 'Qoralama yaratildi')}>
            <Icon name="plus" size={13} /> Yaratish
          </Button>
          {client && client.vat_payer == null && (
            <span className="text-caption text-soon-strong">
              Bu mijozning QQS holati so'ralmagan — stavka 0 bo'ladi.
              Passportda to'ldiring.
            </span>
          )}
        </div>
      </section>

      {/* --- ro'yxat --- */}
      <section className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-body font-semibold">
            Fakturalar {rows ? `(${rows.length})` : ''}
          </h2>
          <Select value={filter || '__all__'}
            onValueChange={(v) => setFilter(v === '__all__' ? '' : v)}>
            <SelectTrigger className="ml-auto h-9 w-auto min-w-40 bg-card text-body">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Barcha holatlar</SelectItem>
              {statuses.map((s) => (
                <SelectItem key={s.code} value={s.code}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {rows && rows.length === 0 ? (
          <div className="text-body text-muted-foreground">
            Faktura yo'q.
          </div>
        ) : (
          <ul className="divide-y">
            {rows?.map((inv) => (
              <li key={inv.id}>
                <button
                  className="flex w-full flex-wrap items-baseline gap-2 py-2 text-left"
                  onClick={() => setOpenId(openId === inv.id ? null : inv.id)}>
                  <Icon name={openId === inv.id ? 'down' : 'right'} size={13}
                    className="text-muted-foreground" />
                  <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                    STATUS_CLASS[inv.status] || 'bg-muted')}>
                    {inv.status_label}
                  </span>
                  <span className="text-body font-medium">
                    {inv.number || 'raqamsiz'}
                  </span>
                  <span className="text-caption text-muted-foreground">
                    {inv.client.name}
                  </span>
                  <span className="tabular ml-auto text-body font-semibold">
                    {f.money(inv.totals?.total ?? 0, inv.currency)}
                  </span>
                  {inv.balance != null && inv.balance > 0
                    && inv.status !== 'draft' && inv.status !== 'cancelled' && (
                    <span className="tabular w-40 text-right text-caption text-soon-strong">
                      qarz: {f.money(inv.balance, inv.currency)}
                    </span>
                  )}
                  <span className="tabular w-24 text-right text-caption text-muted-foreground">
                    {inv.issued_at ? f.dateFmt(inv.issued_at) : '—'}
                  </span>
                </button>

                {openId === inv.id && open && (
                  <InvoiceDetail inv={open} busy={busy} methods={methods}
                    line={line} setLine={setLine} pay={pay} setPay={setPay}
                    run={run} onPrint={() => setPrintId(inv.id)} />
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/** Ochilgan faktura: rekvizitlar, qatorlar, to'lovlar. */
function InvoiceDetail({ inv, busy, methods, line, setLine, pay, setPay, run,
  onPrint }: {
  inv: Invoice
  busy: boolean
  methods: { code: string; label: string }[]
  line: { name: string; qty: string; price: string; vat: string }
  setLine: (v: { name: string; qty: string; price: string; vat: string }) => void
  pay: { amount: string; paid_at: string; method: string }
  setPay: (v: { amount: string; paid_at: string; method: string }) => void
  run: (fn: () => Promise<unknown>, ok: string) => void
  onPrint: () => void
}) {
  const f = useFormat()
  const next = nextStatuses(inv.status)

  return (
    <div className="mb-3 rounded-md border bg-background p-3">
      {/* --- rekvizitlar (snapshot) --- */}
      <div className="mb-3 grid gap-3 text-caption sm:grid-cols-2">
        <div>
          <div className="mb-0.5 font-semibold text-muted-foreground">Sotuvchi</div>
          <div className="text-body">{inv.own.name || '—'}</div>
          <div className="text-muted-foreground">
            INN {inv.own.inn || '—'} · {inv.own.bank || '—'} · {inv.own.account || '—'}
          </div>
        </div>
        <div>
          <div className="mb-0.5 font-semibold text-muted-foreground">Xaridor</div>
          <div className="text-body">{inv.client.name}</div>
          <div className="text-muted-foreground">
            INN {inv.client.inn || '—'} · {inv.client.bank || '—'} ·{' '}
            {inv.client.account || '—'}
          </div>
          <div className="text-muted-foreground">
            QQS: {inv.client.vat_payer === true ? "to'lovchi"
              : inv.client.vat_payer === false ? "to'lovchi emas" : "noma'lum"}
          </div>
        </div>
      </div>

      {/* --- qatorlar --- */}
      <table className="w-full text-caption">
        <thead className="text-muted-foreground">
          <tr className="border-b">
            <th className="py-1 text-left font-semibold">Nomi</th>
            <th className="py-1 text-right font-semibold">Miqdor</th>
            <th className="py-1 text-right font-semibold">Narx</th>
            <th className="py-1 text-right font-semibold">QQS %</th>
            <th className="py-1 text-right font-semibold">Summa</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {inv.lines?.map((ln: InvoiceLine) => (
            <tr key={ln.id} className="border-b">
              <td className="py-1">{ln.name}</td>
              <td className="tabular py-1 text-right">
                {ln.qty}{ln.unit ? ` ${ln.unit}` : ''}
              </td>
              <td className="tabular py-1 text-right">{f.money(ln.price, inv.currency)}</td>
              <td className="tabular py-1 text-right">{ln.vat_rate}</td>
              <td className="tabular py-1 text-right">{f.money(ln.total, inv.currency)}</td>
              <td className="py-1 text-right">
                {inv.editable && (
                  <Button size="sm" variant="ghost" disabled={busy}
                    onClick={() => run(() => api.deleteInvoiceLine(inv.id, ln.id), '')}>
                    <Icon name="close" size={12} />
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={4} className="py-1 text-right text-muted-foreground">
              QQS siz
            </td>
            <td className="tabular py-1 text-right">
              {f.money(inv.totals?.net ?? 0, inv.currency)}
            </td>
            <td />
          </tr>
          <tr>
            <td colSpan={4} className="py-1 text-right text-muted-foreground">QQS</td>
            <td className="tabular py-1 text-right">
              {f.money(inv.totals?.vat ?? 0, inv.currency)}
            </td>
            <td />
          </tr>
          <tr className="border-t font-semibold">
            <td colSpan={4} className="py-1 text-right">Jami</td>
            <td className="tabular py-1 text-right">
              {f.money(inv.totals?.total ?? 0, inv.currency)}
            </td>
            <td />
          </tr>
        </tfoot>
      </table>

      {/* --- yangi qator (faqat qoralamada) --- */}
      {inv.editable ? (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <Input className="max-w-52" placeholder="Nomi" value={line.name}
            onChange={(e) => setLine({ ...line, name: e.target.value })} />
          <Input className="max-w-24" placeholder="Miqdor" inputMode="decimal"
            value={line.qty} onChange={(e) => setLine({ ...line, qty: e.target.value })} />
          <Input className="max-w-32" placeholder="Narx" inputMode="decimal"
            value={line.price} onChange={(e) => setLine({ ...line, price: e.target.value })} />
          <Input className="max-w-24" placeholder="QQS %" inputMode="decimal"
            value={line.vat} onChange={(e) => setLine({ ...line, vat: e.target.value })} />
          <Button size="sm" disabled={busy || !line.name.trim() || !line.qty || !line.price}
            onClick={() => run(async () => {
              await api.addInvoiceLine(inv.id, {
                name: line.name.trim(), qty: Number(line.qty),
                price: Number(line.price),
                vat_rate: line.vat === '' ? null : Number(line.vat),
              })
              setLine({ name: '', qty: '', price: '', vat: '' })
            }, '')}>
            <Icon name="plus" size={13} /> Qator
          </Button>
          <span className="text-caption text-muted-foreground">
            QQS bo'sh qoldirilsa mijoz passportidan olinadi
          </span>
        </div>
      ) : (
        <p className="mt-2 text-caption text-muted-foreground">
          Hujjat chiqarilgan — tahrirlanmaydi. Xato bo'lsa bekor qiling va
          yangisini chiqaring.
        </p>
      )}

      {/* --- to'lovlar --- */}
      {inv.status !== 'draft' && inv.status !== 'cancelled' && (
        <div className="mt-3 border-t pt-2">
          <div className="mb-1 flex flex-wrap items-baseline gap-2">
            <span className="text-caption font-semibold text-muted-foreground">
              To'lovlar
            </span>
            <span className="tabular text-caption">
              to'landi: {f.money(inv.paid ?? 0, inv.currency)} · qoldi:{' '}
              <span className={cn((inv.balance ?? 0) > 0 && 'text-soon-strong')}>
                {f.money(inv.balance ?? 0, inv.currency)}
              </span>
            </span>
          </div>
          {!!inv.payments?.length && (
            <ul className="mb-2 divide-y">
              {inv.payments.map((p) => (
                <li key={p.id} className="flex flex-wrap items-baseline gap-2 py-1 text-caption">
                  <span className="tabular font-semibold">
                    {f.money(p.amount, inv.currency)}
                  </span>
                  <span className="text-muted-foreground">{p.method_label}</span>
                  {p.doc_ref && <span className="text-muted-foreground">· {p.doc_ref}</span>}
                  <span className="tabular ml-auto text-muted-foreground">
                    {p.paid_at ? f.dateFmt(p.paid_at) : ''} · {p.created_by || '—'}
                  </span>
                  <Button size="sm" variant="ghost" disabled={busy}
                    onClick={() => run(() => api.deletePayment(p.id), '')}>
                    <Icon name="close" size={12} />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <Input className="max-w-32" placeholder="Summa" inputMode="decimal"
              value={pay.amount}
              onChange={(e) => setPay({ ...pay, amount: e.target.value })} />
            <Input className="max-w-36" type="date" value={pay.paid_at}
              onChange={(e) => setPay({ ...pay, paid_at: e.target.value })} />
            <Select value={pay.method}
              onValueChange={(v) => setPay({ ...pay, method: v })}>
              <SelectTrigger className="h-9 w-auto min-w-32 bg-card text-body">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {methods.map((m) => (
                  <SelectItem key={m.code} value={m.code}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="sm" disabled={busy || !pay.amount || !pay.paid_at}
              onClick={() => run(async () => {
                await api.addPayment(inv.id, {
                  amount: Number(pay.amount), paid_at: pay.paid_at,
                  method: pay.method,
                })
                setPay({ amount: '', paid_at: '', method: 'bank' })
              }, '')}>
              To'lov qo'shish
            </Button>
            <span className="text-caption text-muted-foreground">
              To'liq to'langanda holat o'zi "To'landi" bo'ladi
            </span>
          </div>
        </div>
      )}

      {/* DALOLATNOMA — faktura bilan juft yuradigan hujjat. */}
      <ActPanel inv={inv} />

      {/* SUMMA SO'Z BILAN — serverda yasaladi va sinaladi. */}
      {inv.totals?.words && (
        <p className="mt-2 text-caption text-muted-foreground">
          So'z bilan: {inv.totals.words}
        </p>
      )}

      {/* --- holat --- */}
      <div className="mt-3 flex flex-wrap gap-2 border-t pt-2">
        <Button size="sm" variant="outline" onClick={onPrint}>
          <Icon name="clip" size={13} /> Bosma shakl
        </Button>
      </div>

      {next.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {next.map((st) => (
            <Button key={st} size="sm"
              variant={st === 'cancelled' ? 'outline' : 'default'}
              disabled={busy}
              onClick={() => run(() => api.setInvoiceStatus(inv.id, st),
                'Holat o\'zgartirildi')}>
              {st === 'issued' ? 'Chiqarish'
                : st === 'sent' ? 'Yuborildi deb belgilash'
                  : 'Bekor qilish'}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
