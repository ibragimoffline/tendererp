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
import type { StockBalance, StockList, StockProduct } from '@/types'
import { ErpError, can } from './erpShared'

// OMBOR (5B-1) — qoldiqning egasi ERP.
//
// EKRANNING ASOSIY G'OYASI: qoldiq — alohida saqlanadigan son emas,
// HARAKATLAR YIG'INDISI. Shuning uchun har qatorni ochib "nega shuncha?"
// degan savolga javob ko'rish mumkin: kim, qachon, qancha va nima uchun.
//
// Mahsulot katalogi TENDER-AI da (u yerda tender moslashuvi uchun
// ishlatiladi). Bu yerda mahsulot QO'SHILMAYDI — faqat harakat yoziladi.
// Ikkinchi katalog ikki xil nomenklatura degani bo'lardi.

const KIND_CLASS: Record<string, string> = {
  opening: 'bg-secondary text-primary',
  in: 'bg-ok-soft text-ok-strong',
  out: 'bg-soon-soft text-soon-strong',
  adjust: 'bg-muted text-muted-foreground',
}

export default function StockPage() {
  const f = useFormat()
  const [data, setData] = useState<StockList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')

  // Ochiq mahsulot: qoldiq + harakatlar tarixi
  const [open, setOpen] = useState<StockProduct | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)

  // Harakat formasi
  const [kind, setKind] = useState('in')
  const [qty, setQty] = useState('')
  const [docRef, setDocRef] = useState('')
  const [moveNote, setMoveNote] = useState('')

  const load = useCallback(() => {
    api.stock()
      .then(setData)
      .catch((e: Error) => { setError(e.message); setData(null) })
  }, [])

  useEffect(load, [load])

  const loadProduct = useCallback((id: number) => {
    setOpenId(id); setOpen(null)
    api.stockProduct(id).then(setOpen).catch((e: Error) => setError(e.message))
  }, [])

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true); setError(null); setNote(null)
    try {
      await fn()
      setNote(ok)
      load()
      if (openId) loadProduct(openId)
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  async function addMove() {
    if (!openId || !qty) return
    const res = await api.addStockMove({
      product_id: openId, kind, qty: Number(qty),
      doc_ref: docRef.trim() || null, note: moveNote.trim() || null,
    })
    setQty(''); setDocRef(''); setMoveNote('')
    // Manfiy qoldiq TAQIQ EMAS — server ogohlantiradi, biz ko'rsatamiz.
    setNote(res.warning
      ? `${res.kind_label}: ${res.qty}. ${res.warning}`
      : `${res.kind_label} yozildi. Yangi qoldiq: ${res.balance}`)
  }

  if (!data && !error) return <Skeleton className="h-64 w-full rounded-lg" />

  const items = (data?.items || []).filter(
    (r) => !q.trim() || r.product_name.toLowerCase().includes(q.trim().toLowerCase()))
  // Import qilingan, lekin omborga hali ko'chirilmagan qoldiqlar bormi
  const pending = (data?.items || []).filter(
    (r) => r.move_count === 0 && r.import_qty != null && r.import_qty !== 0)

  return (
    <div className="space-y-4">
      {error && <ErpError msg={error} />}
      {note && (
        <div className="rounded-lg border border-ok/40 bg-ok-soft px-3 py-2 text-body text-ok-strong">
          {note}
        </div>
      )}

      {/* Ombor ishga tushmaguncha tender-ai eski import suratini
          ko'rsatadi. Bir marta ko'chirilgach EGA butunlay ERP bo'ladi. */}
      {pending.length > 0 && (
        <div className="rounded-lg border border-soon/40 bg-soon-soft px-3 py-2.5 text-body text-soon-strong">
          <div className="mb-1.5 font-semibold">
            {pending.length} ta mahsulotning qoldig'i Tender-AI importida
            qolgan
          </div>
          <p className="mb-2 text-caption">
            Bir marta ko'chirib oling — shundan keyin qoldiq shu jurnaldan
            hisoblanadi.
          </p>
          {can('ombor.harakat') && (
            <Button size="sm" disabled={busy}
              onClick={() => run(api.seedOpening, 'Boshlang\'ich qoldiqlar ko\'chirildi')}>
              Import qoldiqlarini ko'chirish
            </Button>
          )}
        </div>
      )}

      <section className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-body font-semibold">
            {/* Son FILTRLANGAN ro'yxatniki: qidiruvda "Qoldiqlar (1800)"
                deb turgan sarlavha 3 ta qator ustida yolg'on gapiradi.
                Filtr yoqilganda umumiy son ham ko'rsatiladi. */}
            Qoldiqlar {data
              ? (q.trim()
                ? `(${items.length} / ${data.items.length})`
                : `(${data.items.length})`)
              : ''}
          </h2>
          <Input className="ml-auto max-w-56" placeholder="Mahsulot nomi"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>

        <p className="mb-3 text-caption text-muted-foreground">
          Qoldiq — harakatlar yig'indisi. Katalog Tender-AI da.
        </p>

        {items.length === 0 ? (
          <div className="text-body text-muted-foreground">
            Mahsulot topilmadi. Katalog Tender-AI da to'ldiriladi.
          </div>
        ) : (
          <ul className="divide-y">
            {items.map((r) => (
              <li key={r.product_id}>
                <button
                  className={cn('flex w-full flex-wrap items-baseline gap-2 py-2 text-left',
                    openId === r.product_id && 'font-medium')}
                  onClick={() => (openId === r.product_id
                    ? (setOpenId(null), setOpen(null))
                    : loadProduct(r.product_id))}>
                  <Icon name={openId === r.product_id ? 'down' : 'right'}
                    size={13} className="text-muted-foreground" />
                  <span className="text-body">{r.product_name}</span>
                  {!r.in_catalog && (
                    <span className="text-micro text-muted-foreground">
                      (katalogdan o'chirilgan)
                    </span>
                  )}
                  {/* Qoldiq / band / mavjud — uchalasi ham ko'rinadi:
                      "10 bor, 8 band" degan javob bir qarashda o'qilsin. */}
                  <span className={cn('tabular ml-auto text-body font-semibold',
                    r.qty < 0 && 'text-destructive')}>
                    {r.qty}{r.unit ? ` ${r.unit}` : ''}
                  </span>
                  {r.reserved > 0 && (
                    <span className="tabular w-44 text-right text-caption text-muted-foreground">
                      band: {r.reserved} · mavjud:{' '}
                      <span className={cn(r.available < 0 && 'text-destructive')}>
                        {r.available}
                      </span>
                    </span>
                  )}
                  <span className="tabular w-40 text-right text-caption text-muted-foreground">
                    {r.move_count === 0
                      ? 'harakat yo\'q'
                      : `${r.move_count} harakat · ${r.updated_at ? f.dateFmt(r.updated_at) : ''}`}
                  </span>
                </button>

                {openId === r.product_id && (
                  <div className="mb-2 rounded-md border bg-background p-3">
                    {/* --- yangi harakat --- */}
                    {/* Kirim va chiqim — rahbar-menejer ishi
                        (`ombor.harakat`). Brokerga qoldiq KO'RINADI:
                        u tenderga nima yetishini bilishi kerak, lekin
                        jurnalga yozmaydi. */}
                    {!can('ombor.harakat') ? (
                      <div className="text-caption text-muted-foreground">
                        Ombor harakatini rahbar yoki menejer yozadi.
                      </div>
                    ) : (<>
                    <div className="grid gap-2 sm:grid-cols-4">
                      <div>
                        <div className="mb-1 text-caption font-semibold text-muted-foreground">
                          Turi
                        </div>
                        <Select value={kind} onValueChange={setKind}>
                          <SelectTrigger className="bg-card text-body">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {(data?.kinds || []).map((k) => (
                              <SelectItem key={k.code} value={k.code}>{k.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <div className="mb-1 text-caption font-semibold text-muted-foreground">
                          Miqdor{kind === 'adjust' ? ' (± bo\'lishi mumkin)' : ''}
                        </div>
                        <Input inputMode="decimal" value={qty}
                          onChange={(e) => setQty(e.target.value)} />
                      </div>
                      <div>
                        <div className="mb-1 text-caption font-semibold text-muted-foreground">
                          Hujjat (nakladnoy / akt)
                        </div>
                        <Input value={docRef} onChange={(e) => setDocRef(e.target.value)} />
                      </div>
                      <div>
                        <div className="mb-1 text-caption font-semibold text-muted-foreground">
                          Izoh{kind === 'adjust' ? ' (majburiy)' : ''}
                        </div>
                        <Input value={moveNote} onChange={(e) => setMoveNote(e.target.value)} />
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Button size="sm" disabled={busy || !qty}
                        onClick={() => run(addMove, '')}>
                        <Icon name="plus" size={13} /> Yozish
                      </Button>
                      {r.import_qty != null && (
                        <span className="text-caption text-muted-foreground">
                          Tender-AI importida: {r.import_qty}
                          {r.import_at ? ` · ${f.dateFmt(r.import_at)}` : ''}
                        </span>
                      )}
                    </div>
                    </>)}

                    {/* --- tarix --- */}
                    <div className="mt-3 border-t pt-2">
                      {!open ? (
                        <Skeleton className="h-16 w-full" />
                      ) : open.moves.length === 0 ? (
                        <div className="text-caption text-muted-foreground">
                          Harakat yo'q — qoldiq kiritilmagan.
                        </div>
                      ) : (
                        <ul className="divide-y">
                          {open.moves.map((m) => (
                            <li key={m.id}
                              className="flex flex-wrap items-baseline gap-2 py-1.5 text-caption">
                              <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                                KIND_CLASS[m.kind] || 'bg-muted')}>
                                {m.kind_label}
                              </span>
                              <span className={cn('tabular font-semibold',
                                m.qty < 0 ? 'text-destructive' : 'text-ok-strong')}>
                                {m.qty > 0 ? '+' : ''}{m.qty}
                              </span>
                              {m.doc_ref && <span>{m.doc_ref}</span>}
                              {m.opportunity_name && (
                                <span className="text-muted-foreground">
                                  · {m.opportunity_name}
                                </span>
                              )}
                              {m.note && (
                                <span className="text-muted-foreground">· {m.note}</span>
                              )}
                              <span className="ml-auto tabular text-muted-foreground">
                                {m.created_by || '—'}
                                {m.created_at ? ` · ${f.dateFmt(m.created_at)}` : ''}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {data && data.over_reserved.length > 0 && (
          <div className="mt-3 rounded-md border border-soon/40 bg-soon-soft px-3 py-2 text-caption text-soon-strong">
            {data.over_reserved.length} ta mahsulot butunlay band. Ajratish
            uchun kirim qiling yoki rezervni bo'shating.
          </div>
        )}

        {data && data.negative.length > 0 && (
          <div className="mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-caption text-destructive">
            {data.negative.length} ta mahsulotning qoldig'i manfiy — kirim
            hujjati kiritilmagan bo'lishi mumkin. Tekshiring.
          </div>
        )}
      </section>
    </div>
  )
}

/** Qoldiqlar ro'yxatidagi bitta qator — boshqa ekranlarda ham kerak
 *  bo'lsa shu yerdan olinadi. */
export function stockLabel(r: StockBalance): string {
  return `${r.product_name}: ${r.qty}${r.unit ? ` ${r.unit}` : ''}`
}
