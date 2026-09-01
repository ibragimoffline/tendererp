import { useState } from 'react'
import { useFormat, DEADLINE_CLASS } from '@/format'
import { cn } from '@/lib/utils'
import type { ErpStatus, Opportunity } from '@/types'
import StatusChangeDialog from './StatusChangeDialog'
import { OPP_LABEL, PriorityBadge, can } from './erpShared'

// KANBAN — 9 ustun, ustunlar `/erp/meta` dan (frontendda ro'yxat takrorlanmaydi).
//
// Drag-and-drop KUTUBXONASIZ: HTML5 `draggable` + `onDrop` yetarli, yangi
// bog'liqlik olib kelishga arzimaydi. Ko'chirish OPTIMISTIK emas — server
// javobini kutamiz, chunki o'tish rad etilishi mumkin (yakuniydan izohsiz
// qaytish 400) va karta "ko'chdi-yu qaytdi" deb sakrashi chalkash bo'lardi.
// Buning o'rniga ko'chayotgan ustun so'rov davomida so'nadi.

interface OpportunityBoardProps {
  items: Opportunity[]
  statuses: ErpStatus[]
  lostReasons?: { code: string; label: string }[]
  onMove: (o: Opportunity, status: string, note: string | null,
           lostReason?: string | null) => Promise<void>
  onOpen: (id: number) => void
}

export default function OpportunityBoard(
  { items, statuses, lostReasons, onMove, onOpen }: OpportunityBoardProps,
) {
  const f = useFormat()
  const [dragId, setDragId] = useState<number | null>(null)
  const [over, setOver] = useState<string | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  // Tasdiq talab qiladigan o'tish: yakuniyga kirish yoki yakuniydan chiqish
  const [ask, setAsk] = useState<{ o: Opportunity; to: ErpStatus } | null>(null)

  async function move(o: Opportunity, to: ErpStatus, note: string | null,
                      lostReason?: string | null) {
    setBusy(o.id)
    try { await onMove(o, to.code, note, lostReason) } finally { setBusy(null) }
  }

  function drop(to: ErpStatus) {
    setOver(null)
    const o = items.find((x) => x.id === dragId)
    setDragId(null)
    if (!o || o.status === to.code) return
    // Yakuniy ustunga tashlash — `karta.yopish` huquqi (kompaniya
    // sozlamasi bilan brokerdan olinishi mumkin). Huquq bo'lmasa
    // karta O'Z JOYIDA qoladi: server ham 403 berardi.
    if ((to.final || o.is_final) && !can('karta.yopish')) return
    if (to.final || o.is_final) { setAsk({ o, to }); return }
    move(o, to, null)
  }

  return (
    <>
      <div className="flex gap-3 overflow-x-auto pb-3">
        {statuses.map((s) => {
          const col = items.filter((o) => o.status === s.code)
          const sum = col.reduce((a, o) => a + (o.tender.start_price || 0), 0)
          return (
            <div
              key={s.code}
              onDragOver={(e) => { e.preventDefault(); setOver(s.code) }}
              onDragLeave={() => setOver((c) => (c === s.code ? null : c))}
              onDrop={() => drop(s)}
              className={cn(
                'flex w-64 shrink-0 flex-col rounded-lg border bg-muted/40 p-2 transition-colors',
                over === s.code && 'border-primary bg-secondary',
              )}
            >
              <div className="mb-2 flex items-baseline justify-between px-1">
                <span className="text-caption font-semibold">{s.label}</span>
                <span className="tabular text-micro text-muted-foreground">{col.length}</span>
              </div>
              {sum > 0 && (
                <div className="mb-2 px-1 text-micro text-muted-foreground tabular">
                  {f.shortMoney(sum, col[0]?.tender.currency)}
                </div>
              )}

              <div className="flex flex-col gap-2">
                {col.map((o) => {
                  const d = f.deadline(o.tender.deadline_at)
                  return (
                    <article
                      key={o.id}
                      draggable
                      onDragStart={() => setDragId(o.id)}
                      onDragEnd={() => { setDragId(null); setOver(null) }}
                      onClick={() => onOpen(o.id)}
                      className={cn(
                        'cursor-pointer rounded-md border bg-card p-2.5 text-left shadow-xs transition-opacity hover:border-primary',
                        (dragId === o.id || busy === o.id) && 'opacity-50',
                      )}
                    >
                      <div className="line-clamp-2 text-body font-medium leading-snug">
                        {OPP_LABEL(o)}
                      </div>
                      {o.client && (
                        <div className="mt-1 line-clamp-1 text-caption text-muted-foreground">
                          {o.client.name}
                        </div>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <PriorityBadge o={o} />
                        {d && d.level !== 'none' && (
                          <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                            DEADLINE_CLASS[d.level])}>
                            {d.text}
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 flex items-baseline justify-between gap-2">
                        <span className="line-clamp-1 text-micro text-muted-foreground">
                          {o.broker?.name || '—'}
                        </span>
                        <span className="tabular text-micro">
                          {f.shortMoney(o.tender.start_price, o.tender.currency)}
                        </span>
                      </div>
                    </article>
                  )
                })}
                {col.length === 0 && (
                  <div className="rounded-md border border-dashed px-2 py-4 text-center text-micro text-muted-foreground">
                    bo'sh
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {ask && (
        <StatusChangeDialog
          o={ask.o} to={ask.to} lostReasons={lostReasons}
          onCancel={() => setAsk(null)}
          onConfirm={(note, reason) => {
            const a = ask; setAsk(null); move(a.o, a.to, note, reason)
          }}
        />
      )}
    </>
  )
}
