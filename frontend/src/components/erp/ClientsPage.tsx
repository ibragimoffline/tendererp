import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { ClientRow } from '@/types'
import ClientCard from './ClientCard'
import { ErpError, SchemaMissing, can } from './erpShared'

// "MIJOZLAR" bo'limi (ERP 2-bosqich) — korxona passportlari ro'yxati.
//
// Ro'yxatda passport TO'LIQLIGI ko'rinadi: broker ariza to'ldirishdan oldin
// nimasi yetishmayotganini bilishi kerak. "INN yo'q" degan qator — ish
// boshlanmasdan turib ushlanadigan muammo.
//
// Natija ustunlari (kartalar, yutish foizi) SERVERDA hisoblanadi — bu yerda
// faqat ko'rsatiladi.

interface ClientsPageProps {
  /** Opportunity kartasidan "mijoz passporti" ga o'tilganda */
  focusId?: number | null
  onOpenOpportunity?: (oppId: number) => void
}

export default function ClientsPage({ focusId, onOpenOpportunity }: ClientsPageProps) {
  const [rows, setRows] = useState<ClientRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [schemaMissing, setSchemaMissing] = useState(false)
  const [q, setQ] = useState('')
  const [activeOnly, setActiveOnly] = useState(false)
  const [openId, setOpenId] = useState<number | null>(focusId ?? null)
  const [creating, setCreating] = useState(false)

  useEffect(() => { setOpenId(focusId ?? null) }, [focusId])

  const load = useCallback(() => {
    setError(null)
    api.clients({ q: q || undefined, active_only: activeOnly || undefined })
      .then((r) => { setRows(r); setSchemaMissing(false) })
      .catch((e: Error) => {
        // 503 = schema_patch_erp_2.sql qo'llanmagan
        if (e.message.startsWith('503')) setSchemaMissing(true)
        else setError(e.message)
      })
  }, [q, activeOnly])

  useEffect(() => {
    const id = setTimeout(load, q ? 300 : 0)
    return () => clearTimeout(id)
  }, [load, q])

  if (schemaMissing) return <SchemaMissing patch="schema_patch_erp_2.sql" />

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* Mijoz yaratish — rahbar-menejer ishi (`mijoz.tahrirlash`).
            Broker mijozni KO'RADI (o'z kartalaridagini), lekin
            passportini o'zi ochmaydi: bu buxgalteriya ma'lumoti. */}
        {can('mijoz.tahrirlash') && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Icon name="plus" size={13} />
            Yangi korxona
          </Button>
        )}
        <Input className="h-9 w-64" placeholder="Nom yoki INN…"
          value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="flex cursor-pointer items-center gap-1.5 text-body">
          <input type="checkbox" checked={activeOnly}
            onChange={(e) => setActiveOnly(e.target.checked)} />
          faqat faol
        </label>
      </div>

      {error && <ErpError msg={error} />}

      {rows === null ? (
        <Skeleton className="h-64 w-full rounded-lg" />
      ) : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Korxona</TableHead>
                <TableHead>INN</TableHead>
                <TableHead>Passport</TableHead>
                <TableHead className="text-right">Hujjat</TableHead>
                <TableHead className="text-right">Kartalar</TableHead>
                <TableHead className="text-right">Yutish</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id} className="cursor-pointer" onClick={() => setOpenId(c.id)}>
                  <TableCell>
                    <div className="font-medium">{c.name}</div>
                    <div className="text-micro text-muted-foreground">
                      {[c.legal_form, c.director_name].filter(Boolean).join(' · ') || '—'}
                    </div>
                  </TableCell>
                  <TableCell className="tabular">{c.inn || '—'}</TableCell>
                  <TableCell>
                    {c.missing.length === 0 ? (
                      <span className="rounded bg-ok-soft px-1.5 py-px text-micro font-semibold text-ok-strong">
                        to'liq
                      </span>
                    ) : (
                      <span className="rounded bg-soon-soft px-1.5 py-px text-micro font-semibold text-soon-strong"
                        title={c.missing.join(', ')}>
                        {c.missing.length} maydon yetishmaydi
                      </span>
                    )}
                    {!c.active && (
                      <span className="ml-1.5 rounded bg-muted px-1.5 py-px text-micro text-muted-foreground">
                        faol emas
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="tabular text-right">{c.doc_n}</TableCell>
                  <TableCell className="tabular text-right">
                    {c.opp_n}
                    {c.open_n > 0 && (
                      <span className="ml-1 text-micro text-muted-foreground">
                        ({c.open_n} ishda)
                      </span>
                    )}
                  </TableCell>
                  <TableCell className={cn('tabular text-right',
                    c.win_rate != null && c.win_rate >= 50 && 'text-ok-strong')}>
                    {c.win_rate == null ? '—' : `${c.win_rate}%`}
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    Korxona yo'q — "Yangi korxona" tugmasi bilan qo'shiladi.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {(openId !== null || creating) && (
        <ClientCard
          id={creating ? null : openId}
          onClose={() => { setOpenId(null); setCreating(false) }}
          onSaved={(c) => { load(); if (creating) { setCreating(false); setOpenId(c.id) } }}
          onOpenOpportunity={onOpenOpportunity}
        />
      )}
    </div>
  )
}
