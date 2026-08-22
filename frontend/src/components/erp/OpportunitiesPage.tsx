import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { ErpBroker, ErpClient, ErpMeta, Opportunity } from '@/types'
import OpportunityBoard from './OpportunityBoard'
import OpportunityCard from './OpportunityCard'
import OpportunityStats from './OpportunityStats'
import OpportunityTable from './OpportunityTable'
import { ALL, ErpError, toFilter, toSelect } from './erpShared'

// "ISHDAGI TENDERLAR" bo'limi — Kanban / Jadval / Hisobot.
//
// HOLAT SHU YERDA: lug'atlar (statuslar, brokerlar, mijozlar) sahifa
// ochilganda BIR MARTA yuklanadi va pastga props bilan uzatiladi; kartalar
// ro'yxati ham shu yerda, chunki uni uchala ko'rinish ham baham ko'radi.
// Status o'zgarganda ro'yxat qayta so'ralmaydi — server yangilangan kartani
// qaytaradi va u joyiga qo'yiladi (bir so'rov, sakramaydigan interfeys).

type View = 'board' | 'table' | 'stats'

const VIEWS: { key: View; label: string }[] = [
  { key: 'board', label: 'Kanban' },
  { key: 'table', label: 'Jadval' },
  { key: 'stats', label: 'Hisobot' },
]

interface OpportunitiesPageProps {
  /** Tender-AI dan `/?opp=<id>` havolasi bilan kelinganda ochiladigan karta */
  focusId?: number | null
  /** Tender-AI interfeysi manzili — kartadagi havola uchun */
  tenderWeb?: string
}

export default function OpportunitiesPage({ focusId, tenderWeb }: OpportunitiesPageProps) {
  const [view, setView] = useState<View>('board')
  const [meta, setMeta] = useState<ErpMeta | null>(null)
  const [brokers, setBrokers] = useState<ErpBroker[]>([])
  const [clients, setClients] = useState<ErpClient[]>([])
  const [items, setItems] = useState<Opportunity[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openId, setOpenId] = useState<number | null>(focusId ?? null)

  // Filtrlar. Bo'sh satr = "hammasi" (Radix Select cheklovi uchun ALL bilan).
  const [status, setStatus] = useState('')
  const [brokerId, setBrokerId] = useState('')
  const [clientId, setClientId] = useState('')
  const [q, setQ] = useState('')
  const [openOnly, setOpenOnly] = useState(true)

  useEffect(() => { setOpenId(focusId ?? null) }, [focusId])

  useEffect(() => {
    Promise.all([api.meta(), api.brokers(), api.clients()])
      .then(([m, b, c]) => { setMeta(m); setBrokers(b); setClients(c) })
      .catch((e: Error) => setError(e.message))
  }, [])

  const load = useCallback(() => {
    if (meta && !meta.schema_ready) return
    setError(null)
    api.opportunities({
      status: status || undefined,
      broker_id: brokerId || undefined,
      client_id: clientId || undefined,
      q: q || undefined,
      open_only: openOnly || undefined,
    }).then(setItems).catch((e: Error) => setError(e.message))
  }, [meta, status, brokerId, clientId, q, openOnly])

  // Qidiruvda har harfga so'rov yubormaymiz — 300 ms kutamiz.
  useEffect(() => {
    const id = setTimeout(load, q ? 300 : 0)
    return () => clearTimeout(id)
  }, [load, q])

  /** Kartani ro'yxatda joyiga qo'yish (yoki filtrga tushmasa olib tashlash). */
  function replace(o: Opportunity) {
    setItems((xs) => {
      if (!xs) return xs
      const next = xs.map((x) => (x.id === o.id ? o : x))
      return openOnly && o.is_final ? next.filter((x) => x.id !== o.id) : next
    })
  }

  async function move(o: Opportunity, statusCode: string, note: string | null,
                      lostReason?: string | null) {
    try {
      replace(await api.setStatus(o.id, {
        status: statusCode, changed_by: o.broker?.name ?? null, note,
        lost_reason: lostReason ?? null,
      }))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="space-y-3">
      {/* --- Ko'rinish almashtirgichi va filtrlar --- */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1">
          {VIEWS.map((v) => (
            <Button key={v.key} size="sm"
              variant={view === v.key ? 'default' : 'outline'}
              onClick={() => setView(v.key)}>
              {v.label}
            </Button>
          ))}
        </div>

        {view !== 'stats' && (
          <>
            <Select value={toSelect(brokerId)} onValueChange={(v) => setBrokerId(toFilter(v))}>
              <SelectTrigger className="h-9 w-auto min-w-36 bg-card text-body">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Barcha mas'ullar</SelectItem>
                {brokers.map((b) => (
                  <SelectItem key={b.id} value={String(b.id)}>{b.full_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={toSelect(clientId)} onValueChange={(v) => setClientId(toFilter(v))}>
              <SelectTrigger className="h-9 w-auto min-w-36 bg-card text-body">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Barcha mijozlar</SelectItem>
                {clients.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {view === 'table' && (
              <Select value={toSelect(status)} onValueChange={(v) => setStatus(toFilter(v))}>
                <SelectTrigger className="h-9 w-auto min-w-36 bg-card text-body">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>Barcha statuslar</SelectItem>
                  {(meta?.statuses || []).map((s) => (
                    <SelectItem key={s.code} value={s.code}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            <Input className="h-9 w-56" placeholder="Tender yoki buyurtmachi…"
              value={q} onChange={(e) => setQ(e.target.value)} />

            <label className="flex cursor-pointer items-center gap-1.5 text-body">
              <input type="checkbox" checked={openOnly}
                onChange={(e) => setOpenOnly(e.target.checked)} />
              faqat ochiq
            </label>
          </>
        )}
      </div>

      {error && <ErpError msg={error} />}

      {view === 'stats' ? (
        <OpportunityStats onOpen={setOpenId} />
      ) : items === null ? (
        <Skeleton className="h-64 w-full rounded-lg" />
      ) : view === 'board' ? (
        <OpportunityBoard items={items} statuses={meta?.statuses || []}
          lostReasons={meta?.lost_reasons} onMove={move} onOpen={setOpenId} />
      ) : (
        <div className={cn('rounded-lg border bg-card')}>
          <OpportunityTable items={items} onOpen={setOpenId} />
        </div>
      )}

      {openId !== null && meta && (
        <OpportunityCard
          id={openId}
          statuses={meta.statuses}
          priorities={meta.priorities}
          lostReasons={meta.lost_reasons}
          contractStatuses={meta.contract_statuses}
          brokers={brokers}
          clients={clients}
          onClose={() => setOpenId(null)}
          onChanged={replace}
          tenderWeb={tenderWeb}
        />
      )}
    </div>
  )
}
