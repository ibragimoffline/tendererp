import { useMemo, useState } from 'react'
import { useFormat, DEADLINE_CLASS } from '@/format'
import Icon from '../Icon'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { Opportunity } from '@/types'
import { OPP_LABEL, PriorityBadge, StatusBadge } from './erpShared'

// JADVAL ko'rinishi — Kanban "qaysi bosqichda" degan savolga javob bersa,
// jadval "qaysi biri qachon va qanchaga" degan savolga javob beradi.
// Saralash MIJOZ tomonida: ro'yxat bitta so'rovda to'liq keladi (kartalar soni
// yuzlab, minglab emas), server tomonida sahifalash 1-bosqichda ortiqcha.

type SortKey = 'title' | 'client' | 'broker' | 'deadline' | 'price' | 'status'

interface OpportunityTableProps {
  items: Opportunity[]
  onOpen: (id: number) => void
}

const VAL: Record<SortKey, (o: Opportunity) => string | number> = {
  title: (o) => (OPP_LABEL(o) || '').toLowerCase(),
  client: (o) => (o.client?.name || '').toLowerCase(),
  broker: (o) => (o.broker?.name || '').toLowerCase(),
  // Muddatsiz kartalar HAR DOIM oxirida: "sana yo'q" — "juda uzoq" degani emas.
  deadline: (o) => o.tender.deadline_at || '9999',
  price: (o) => o.tender.start_price ?? -1,
  status: (o) => o.status_label || o.status,
}

const COLS: { key: SortKey; label: string; className?: string }[] = [
  { key: 'title', label: 'Tender' },
  { key: 'client', label: 'Mijoz' },
  { key: 'broker', label: "Mas'ul" },
  { key: 'deadline', label: 'Deadline' },
  { key: 'price', label: 'Summa', className: 'text-right' },
  { key: 'status', label: 'Status' },
]

export default function OpportunityTable({ items, onOpen }: OpportunityTableProps) {
  const f = useFormat()
  const [sort, setSort] = useState<SortKey>('deadline')
  const [asc, setAsc] = useState(true)

  const rows = useMemo(() => {
    const get = VAL[sort]
    return [...items].sort((a, b) => {
      const x = get(a), y = get(b)
      const r = typeof x === 'number' && typeof y === 'number'
        ? x - y
        : String(x).localeCompare(String(y))
      return asc ? r : -r
    })
  }, [items, sort, asc])

  function toggle(k: SortKey) {
    if (k === sort) setAsc((v) => !v)
    else { setSort(k); setAsc(true) }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {COLS.map((c) => (
            <TableHead key={c.key} className={cn('cursor-pointer select-none', c.className)}
              onClick={() => toggle(c.key)}>
              <span className="inline-flex items-center gap-1">
                {c.label}
                {sort === c.key && <Icon name={asc ? 'sortAsc' : 'sortDesc'} size={11} />}
              </span>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((o) => {
          const d = f.deadline(o.tender.deadline_at)
          return (
            <TableRow key={o.id} className="cursor-pointer" onClick={() => onOpen(o.id)}>
              <TableCell className="max-w-[24rem]">
                <div className="line-clamp-1 font-medium">{OPP_LABEL(o)}</div>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span className="line-clamp-1 text-micro text-muted-foreground">
                    {o.tender.customer_name || '—'}
                  </span>
                  <PriorityBadge o={o} />
                </div>
              </TableCell>
              <TableCell>{o.client?.name || '—'}</TableCell>
              <TableCell>{o.broker?.name || '—'}</TableCell>
              <TableCell>
                {d && d.level !== 'none' ? (
                  <span className={cn('rounded px-1.5 py-px text-caption font-semibold',
                    DEADLINE_CLASS[d.level])}>
                    {d.text}
                  </span>
                ) : <span className="text-muted-foreground">—</span>}
                <div className="mt-0.5 text-micro text-muted-foreground tabular">
                  {f.dateFmt(o.tender.deadline_at)}
                </div>
              </TableCell>
              <TableCell className="text-right tabular">
                {f.money(o.tender.start_price, o.tender.currency)}
              </TableCell>
              <TableCell><StatusBadge o={o} /></TableCell>
            </TableRow>
          )
        })}
        {rows.length === 0 && (
          <TableRow>
            <TableCell colSpan={COLS.length} className="py-8 text-center text-muted-foreground">
              Karta yo'q — tender panelidan "Ishga olish" tugmasi bilan qo'shiladi.
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  )
}
