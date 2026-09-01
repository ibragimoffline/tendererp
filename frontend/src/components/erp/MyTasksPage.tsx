import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat, DEADLINE_CLASS } from '@/format'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { ErpBroker, MyTask, MyTasks } from '@/types'
import { ALL, ErpError, permLevel } from './erpShared'

//: Filtrda "sukut" qiymati. Radix Select bo'sh satrni qabul qilmaydi.
const SELF = '__self__'

// "MENING ISHLARIM" — kunni shu ekrandan boshlash uchun.
//
// Kanban "qaysi bosqichda" degan savolga javob beradi, bu esa "bugun nima
// qilishim kerak" degan savolga. Uchta guruh: KECHIKKAN (eng yuqorida —
// ular allaqachon muammo), bugungi, keyingi.
//
// Eslatma skripti (api/erp/remind.py) AYNAN shu ro'yxatdan o'qiydi: ekranda
// ko'ringan narsa xabarda ham keladi, ikkinchi mantiq yo'q.

interface MyTasksPageProps {
  brokers: ErpBroker[]
  onOpenOpportunity: (oppId: number) => void
}

/** Filtr uchun alohida qiymat: "" — SUKUT (server o'zi hal qiladi: hisob
 *  hodimga bog'langan bo'lsa o'shaniki), ALL — hamma, son — aniq hodim.
 *  Ilgari "" "hamma" degani edi; endi "hamma" ochiq so'raladi, chunki
 *  ekranning nomi "MENING ishlarim". */
export default function MyTasksPage({ brokers, onOpenOpportunity }: MyTasksPageProps) {
  const [data, setData] = useState<MyTasks | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [brokerId, setBrokerId] = useState('')
  const [days, setDays] = useState(7)

  const load = useCallback(() => {
    setError(null)
    api.myTasks({
      broker_id: brokerId && brokerId !== ALL ? brokerId : undefined,
      everyone: brokerId === ALL ? true : undefined,
      days,
    })
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [brokerId, days])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* EGALIK: brokerga faqat O'ZINIKI ko'rinadi (server ham shunday
            filtrlaydi, `api/erp/egalik.py`). Boshqa hodimni tanlash
            imkonini QOLDIRSAK, tanlov ishlamas edi — ro'yxat baribir
            o'zinikini qaytarardi va bu "buzuq filtr" bo'lib ko'rinardi. */}
        {permLevel('hisobot.deadline') !== 'own' && (
        <Select value={brokerId || SELF} onValueChange={(v) => setBrokerId(v === SELF ? '' : v)}>
          <SelectTrigger className="h-9 w-auto min-w-44 bg-card text-body">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {/* Hisob hodimga bog'lanmagan bo'lsa (masalan administrator)
                "meniki" degani ma'nosiz — u holda sukut hammaniki. */}
            <SelectItem value={SELF}>
              {data?.self_broker_id ? 'Mening ishlarim' : "Barcha mas'ullar"}
            </SelectItem>
            <SelectItem value={ALL}>Barcha mas'ullar</SelectItem>
            {brokers.filter((b) => b.active).map((b) => (
              <SelectItem key={b.id} value={String(b.id)}>{b.full_name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        )}

        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="h-9 w-auto min-w-36 bg-card text-body">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">Bugun va kechikkan</SelectItem>
            <SelectItem value="7">Yaqin 7 kun</SelectItem>
            <SelectItem value="30">Yaqin 30 kun</SelectItem>
          </SelectContent>
        </Select>

        {data && (
          <span className="tabular text-caption text-muted-foreground">
            {data.total} vazifa
          </span>
        )}
      </div>

      {error && <ErpError msg={error} />}
      {!data && !error && <Skeleton className="h-64 w-full rounded-lg" />}

      {data && (
        <div className="space-y-4">
          <Group title="Kechikkan" tone="urgent" items={data.overdue}
            onOpen={onOpenOpportunity} onChanged={load} />
          <Group title="Bugun" tone="soon" items={data.today}
            onOpen={onOpenOpportunity} onChanged={load} />
          <Group title="Keyingi" items={data.later}
            onOpen={onOpenOpportunity} onChanged={load} />

          {data.total === 0 && (
            <div className="rounded-lg border bg-card px-4 py-8 text-center text-body text-muted-foreground">
              Vazifa yo'q — karta ochib "Vazifa" tugmasi bilan qo'shiladi.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Group({ title, items, tone, onOpen, onChanged }: {
  title: string
  items: MyTask[]
  tone?: 'urgent' | 'soon'
  onOpen: (oppId: number) => void
  onChanged: () => void
}) {
  const f = useFormat()
  if (!items.length) return null

  return (
    <section className="rounded-lg border bg-card">
      <div className={cn('border-b px-4 py-2 text-caption font-semibold',
        tone === 'urgent' && 'bg-urgent-soft text-urgent-strong',
        tone === 'soon' && 'bg-soon-soft text-soon-strong')}>
        {title} ({items.length})
      </div>
      <ul className="divide-y">
        {items.map((t) => {
          const d = f.deadline(t.opportunity.deadline_at)
          return (
            <li key={t.id} className="flex flex-wrap items-baseline gap-2 px-4 py-2 text-body">
              {/* Bajarildi — shu yerdan: kartani ochish shart emas */}
              <input type="checkbox" checked={false}
                title="Bajarildi deb belgilash"
                onChange={() => api.setTaskDone(t.id, true).then(onChanged).catch(() => {})} />
              <span className="font-medium">{t.title}</span>
              {t.due_at && (
                <span className={cn('tabular text-caption',
                  t.overdue ? 'font-semibold text-urgent-strong' : 'text-muted-foreground')}>
                  {f.dateFmt(t.due_at)}
                </span>
              )}
              {t.assignee?.name && (
                <span className="text-caption text-muted-foreground">{t.assignee.name}</span>
              )}

              <button type="button"
                className="ml-auto max-w-[24rem] truncate text-caption text-primary hover:underline"
                onClick={() => onOpen(t.opportunity.id)}>
                {t.opportunity.title || `Karta #${t.opportunity.id}`}
              </button>
              {t.opportunity.client_name && (
                <span className="text-caption text-muted-foreground">
                  {t.opportunity.client_name}
                </span>
              )}
              {/* Tender muddati — vazifa muddatidan MUHIMROQ bo'lishi mumkin */}
              {d && d.level !== 'none' && (
                <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                  DEADLINE_CLASS[d.level])}>
                  tender: {d.text}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
