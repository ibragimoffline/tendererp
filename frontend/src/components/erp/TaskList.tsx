import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { ErpBroker, OpportunityTask, TaskInput } from '@/types'
import { ErpError } from './erpShared'

// KARTA VAZIFALARI (3-bosqich).
//
// Ilgari kartada bitta "keyingi vazifa" maydoni bor edi: ikkinchi ish
// yozilsa birinchisi yo'qolardi va muddat o'tib ketganini hech kim
// eslatmasdi. Endi ro'yxat, muddat va mas'ul bor — eslatma skripti
// (api/erp/remind.py) aynan shu ro'yxatdan o'qiydi.
//
// KECHIKKANNI SERVER BELGILAYDI (`overdue`): brauzer soati noto'g'ri
// bo'lishi mumkin, "kechikdi" degan xabar esa qarorga ta'sir qiladi.

interface TaskListProps {
  oppId: number
  brokers: ErpBroker[]
  /** kim qo'shdi — auth yo'q, kartaning brokeri nomi */
  createdBy?: string | null
}

const EMPTY: TaskInput = { title: '', assignee_broker_id: null, due_at: null }

export default function TaskList({ oppId, brokers, createdBy }: TaskListProps) {
  const f = useFormat()
  const [items, setItems] = useState<OpportunityTask[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [add, setAdd] = useState<TaskInput | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setItems(null); setError(null); setAdd(null)
    api.tasks(oppId).then(setItems).catch((e: Error) => setError(e.message))
  }, [oppId])

  async function run(p: Promise<OpportunityTask[]>) {
    setBusy(true); setError(null)
    try { setItems(await p); setAdd(null) } catch (e) {
      setError((e as Error).message)
    } finally { setBusy(false) }
  }

  if (error && !items) return <ErpError msg={error} />

  const open = (items || []).filter((t) => !t.done)
  const done = (items || []).filter((t) => t.done)

  return (
    <section className="mt-5">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-caption font-semibold text-muted-foreground">Vazifalar</h3>
        {open.length > 0 && (
          <span className="tabular text-micro text-muted-foreground">
            {open.length} ochiq
            {open.some((t) => t.overdue) && (
              <span className="ml-1 text-urgent-strong">
                · {open.filter((t) => t.overdue).length} kechikkan
              </span>
            )}
          </span>
        )}
        {add === null && (
          <Button variant="outline" size="sm" className="ml-auto"
            onClick={() => setAdd({ ...EMPTY, created_by: createdBy ?? null })}>
            <Icon name="plus" size={13} /> Vazifa
          </Button>
        )}
      </div>

      {error && <div className="mb-2"><ErpError msg={error} /></div>}

      {add !== null && (
        <div className="mb-2 space-y-2 rounded-md border p-3">
          <Input autoFocus placeholder="Nima qilinadi?" value={add.title}
            onChange={(e) => setAdd({ ...add, title: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && add.title.trim()) {
                e.preventDefault(); run(api.addTask(oppId, add))
              }
            }} />
          <div className="flex flex-wrap gap-2">
            <div>
              <div className="mb-1 text-micro text-muted-foreground">Muddat</div>
              <Input type="date" value={add.due_at ?? ''}
                onChange={(e) => setAdd({ ...add, due_at: e.target.value || null })} />
            </div>
            <div className="min-w-44 flex-1">
              <div className="mb-1 text-micro text-muted-foreground">
                Mas'ul (bo'sh — kartaning brokeri)
              </div>
              <Select value={add.assignee_broker_id ? String(add.assignee_broker_id) : ''}
                onValueChange={(v) => setAdd({ ...add, assignee_broker_id: Number(v) })}>
                <SelectTrigger className="h-9 w-full bg-card text-body">
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {brokers.filter((b) => b.active).map((b) => (
                    <SelectItem key={b.id} value={String(b.id)}>{b.full_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" disabled={busy || !add.title.trim()}
              onClick={() => run(api.addTask(oppId, add))}>
              Qo'shish
            </Button>
            <Button variant="outline" size="sm" onClick={() => setAdd(null)}>Bekor</Button>
          </div>
        </div>
      )}

      <ul className="space-y-1">
        {open.map((t) => (
          <li key={t.id} className={cn(
            'flex flex-wrap items-baseline gap-2 rounded-md border px-3 py-2 text-body',
            t.overdue && 'border-urgent/40 bg-urgent-soft',
          )}>
            <input type="checkbox" checked={false} disabled={busy}
              onChange={() => run(api.setTaskDone(t.id, true))}
              title="Bajarildi deb belgilash" />
            <span className="font-medium">{t.title}</span>
            {t.due_at && (
              <span className={cn('tabular text-caption',
                t.overdue ? 'font-semibold text-urgent-strong' : 'text-muted-foreground')}>
                {f.dateFmt(t.due_at)}{t.overdue && ' · kechikdi'}
              </span>
            )}
            {t.assignee?.name && (
              <span className="text-caption text-muted-foreground">{t.assignee.name}</span>
            )}
            {t.reminded_at && (
              <span className="text-micro text-muted-foreground"
                title={`Eslatma yuborilgan: ${f.dateFmt(t.reminded_at)}`}>
                eslatilgan
              </span>
            )}
            <button type="button" disabled={busy}
              className="ml-auto text-caption text-urgent-strong hover:underline"
              onClick={() => run(api.deleteTask(t.id))}>
              o'chirish
            </button>
          </li>
        ))}
        {open.length === 0 && add === null && (
          <li className="py-2 text-body text-muted-foreground">
            Ochiq vazifa yo'q.
          </li>
        )}
      </ul>

      {done.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-caption text-muted-foreground">
            Bajarilgan ({done.length})
          </summary>
          <ul className="mt-1 space-y-0.5">
            {done.map((t) => (
              <li key={t.id} className="flex flex-wrap items-baseline gap-2 px-3 text-caption text-muted-foreground">
                <input type="checkbox" checked disabled={busy}
                  onChange={() => run(api.setTaskDone(t.id, false))} />
                <span className="line-through">{t.title}</span>
                {t.done_at && <span className="tabular">{f.dateFmt(t.done_at)}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
