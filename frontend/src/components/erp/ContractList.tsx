import { useEffect, useState } from 'react'
import { api, ApiError } from '@/api'
import { useFormat } from '@/format'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { Contract, ContractInput, ContractStatus, Submission } from '@/types'
import { ErpError } from './erpShared'
import ContractPrint from './ContractPrint'

// KARTADAGI SHARTNOMALAR (5A-1).
//
// Taklif topshirilgach zanjir shu yerda yopiladi: raqam, summa, muddat va
// holat kartaning o'zida qoladi — xatda yoki Excelda emas.
//
// Summa QO'LDA YOZILMAYDI (agar kiritilmasa): u taklifdan, u ham bo'lmasa
// kartadagi snapshotdan olinadi — bir xil raqamni ikkinchi marta yozish
// xato manbai.
//
// Shartnoma O'CHIRILMAYDI: noto'g'risi "Bekor qilingan" ga o'tkaziladi.

const STATUS_CLASS: Record<string, string> = {
  draft: 'bg-muted text-muted-foreground',
  signed: 'bg-secondary text-primary',
  executing: 'bg-soon-soft text-soon-strong',
  done: 'bg-ok-soft text-ok-strong',
  terminated: 'bg-muted text-muted-foreground line-through',
}

interface ContractListProps {
  oppId: number
  statuses: ContractStatus[]
  submissions: Submission[]
  createdBy?: string | null
}

const EMPTY: ContractInput = { number: '', signed_at: null, starts_at: null, ends_at: null }

export default function ContractList(
  { oppId, statuses, submissions, createdBy }: ContractListProps,
) {
  const f = useFormat()
  const [items, setItems] = useState<Contract[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dupId, setDupId] = useState<number | null>(null)
  const [add, setAdd] = useState<ContractInput | null>(null)
  const [busy, setBusy] = useState(false)
  // Shartnoma ILOVASI (spetsifikatsiya). Shartnoma MATNI ERP da yo'q —
  // huquqiy matn yurist ishi.
  const [printId, setPrintId] = useState<number | null>(null)

  useEffect(() => {
    setItems(null); setError(null); setAdd(null)
    api.contracts(oppId).then(setItems)
      .catch((e: ApiError) => setError(
        e.status === 503 ? "Shartnoma jadvali yo'q: schema_patch_erp_5.sql qo'llanmagan."
          : e.message))
  }, [oppId])

  async function run(p: Promise<Contract[]>) {
    setBusy(true); setError(null); setDupId(null)
    try { setItems(await p); setAdd(null) } catch (e) {
      const err = e as ApiError
      const d = err.detail as { message?: string; contract_id?: number } | null
      if (err.status === 409 && d?.contract_id) {
        setDupId(d.contract_id); setError(d.message || 'Bu raqam band.')
      } else setError(err.message)
    } finally { setBusy(false) }
  }

  if (error && !items) return <ErpError msg={error} />

  if (printId !== null) {
    return <ContractPrint contractId={printId} onClose={() => setPrintId(null)} />
  }

  return (
    <section className="mt-5">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-caption font-semibold text-muted-foreground">Shartnomalar</h3>
        {add === null && (
          <Button variant="outline" size="sm" className="ml-auto"
            onClick={() => setAdd({ ...EMPTY, created_by: createdBy ?? null })}>
            <Icon name="plus" size={13} /> Shartnoma
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-2">
          <ErpError msg={error} />
          {dupId !== null && (
            <div className="mt-1 text-caption text-muted-foreground">
              Mavjud shartnoma № {dupId} — ro'yxatdan qidiring.
            </div>
          )}
        </div>
      )}

      {add !== null && (
        <div className="mb-2 space-y-2 rounded-md border p-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-micro text-muted-foreground">Shartnoma raqami</div>
              <Input autoFocus value={add.number ?? ''}
                onChange={(e) => setAdd({ ...add, number: e.target.value })} />
            </div>
            <div>
              <div className="mb-1 text-micro text-muted-foreground">
                Summa (bo'sh — taklifdan/snapshotdan)
              </div>
              <Input className="tabular" inputMode="decimal"
                value={add.amount == null ? '' : String(add.amount)}
                onChange={(e) => setAdd({
                  ...add, amount: e.target.value ? Number(e.target.value) : null,
                })} />
            </div>
            <div>
              <div className="mb-1 text-micro text-muted-foreground">Imzolangan sana</div>
              <Input type="date" value={add.signed_at ?? ''}
                onChange={(e) => setAdd({ ...add, signed_at: e.target.value || null })} />
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <div className="mb-1 text-micro text-muted-foreground">Boshlanishi</div>
                <Input type="date" value={add.starts_at ?? ''}
                  onChange={(e) => setAdd({ ...add, starts_at: e.target.value || null })} />
              </div>
              <div className="flex-1">
                <div className="mb-1 text-micro text-muted-foreground">Tugashi</div>
                <Input type="date" value={add.ends_at ?? ''}
                  onChange={(e) => setAdd({ ...add, ends_at: e.target.value || null })} />
              </div>
            </div>
            {submissions.length > 0 && (
              <div className="sm:col-span-2">
                <div className="mb-1 text-micro text-muted-foreground">
                  Qaysi taklif asosida (ixtiyoriy)
                </div>
                <Select value={add.submission_id ? String(add.submission_id) : ''}
                  onValueChange={(v) => setAdd({ ...add, submission_id: Number(v) })}>
                  <SelectTrigger className="h-9 w-full bg-card text-body">
                    <SelectValue placeholder="—" />
                  </SelectTrigger>
                  <SelectContent>
                    {submissions.map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        v{s.version} · {f.money(s.price, s.currency)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Button size="sm" disabled={busy}
              onClick={() => run(api.addContract(oppId, add))}>
              Qo'shish
            </Button>
            <Button variant="outline" size="sm" onClick={() => setAdd(null)}>Bekor</Button>
          </div>
        </div>
      )}

      <ul className="space-y-1">
        {(items || []).map((k) => (
          <li key={k.id} className="rounded-md border px-3 py-2">
            <div className="flex flex-wrap items-baseline gap-2 text-body">
              <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                STATUS_CLASS[k.status] || 'bg-muted')}>
                {k.status_label || k.status}
              </span>
              <span className="font-medium">{k.number || 'raqamsiz'}</span>
              <span className="tabular">{f.money(k.amount, k.currency)}</span>
              {k.signed_at && (
                <span className="tabular text-caption text-muted-foreground">
                  imzolandi {f.dateFmt(k.signed_at)}
                </span>
              )}
              {/* MUDDAT ikki uchli: boshlanishi ham, tugashi ham.
                  Ilgari faqat "gacha" ko'rinardi — kiritilgan
                  "Boshlanishi" sanasi hech qayerda chiqmasdi va
                  shartnoma qachondan kuchga kirgani noma'lum qolardi. */}
              {(k.starts_at || k.ends_at) && (
                <span className="tabular text-caption text-muted-foreground">
                  · {k.starts_at ? f.dateFmt(k.starts_at) : '…'}
                  {' — '}
                  {k.ends_at ? f.dateFmt(k.ends_at) : '…'}
                </span>
              )}
              {k.submission && (
                <span className="text-micro text-muted-foreground">
                  taklif v{k.submission.version}
                </span>
              )}
            </div>

            {/* Holat — o'chirish YO'Q: noto'g'risi "Bekor qilingan" ga o'tadi */}
            <div className="mt-1.5 flex flex-wrap items-center gap-1">
              <button type="button"
                onClick={() => setPrintId(k.id)}
                className="rounded border px-2 py-0.5 text-micro transition-colors hover:bg-accent">
                Ilova (spetsifikatsiya)
              </button>
              <span className="mx-1 text-micro text-muted-foreground">|</span>
              {statuses.map((s) => (
                <button key={s.code} type="button" disabled={busy || s.code === k.status}
                  onClick={() => run(api.setContractStatus(k.id, s.code))}
                  className={cn('rounded px-2 py-0.5 text-micro transition-colors',
                    s.code === k.status
                      ? 'bg-secondary font-semibold text-primary'
                      : 'hover:bg-accent')}>
                  {s.label}
                </button>
              ))}
            </div>
          </li>
        ))}
        {items !== null && items.length === 0 && add === null && (
          <li className="py-2 text-body text-muted-foreground">
            Shartnoma qayd etilmagan.
          </li>
        )}
      </ul>
    </section>
  )
}
