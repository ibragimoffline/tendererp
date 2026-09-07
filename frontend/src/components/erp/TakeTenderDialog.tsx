import { useEffect, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { api, ApiError } from '@/api'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { ErpBroker, ErpClient, ErpMeta, Opportunity, OpportunityInput } from '@/types'

// "ISHGA OLISH" — tender ro'yxatdan kompaniyaning ichki ish kartasiga aylanadi.
// Tender paneli bilan ERP orasidagi YAGONA ulanish nuqtasi (erp_arxitektura.md
// 2.4): tender moduli ERP haqida boshqa hech narsa bilmaydi.
//
// Komponent o'zi holatni so'raydi: ishga olingan bo'lsa nishon, bo'lmasa tugma.
// ERP jadvallari bazada bo'lmasa (patch qo'llanmagan) — UMUMAN ko'rinmaydi:
// tender panelida ishlamaydigan tugma turgani yolg'on va'da bo'lardi.

/** Forma boshlang'ich holati. Snapshot maydonlari YO'Q — ular serverda
 *  tenderdan olinadi. */
const EMPTY: OpportunityInput = {
  broker_id: null, client_id: null, priority: 'medium', win_probability: null,
  note: null, next_task: null, next_task_at: null, created_by: null,
}

interface TakeTenderDialogProps {
  tenderId: number
  onClose: () => void
  onOpenOpportunity?: (oppId: number) => void
}

/** "ISHGA OLISH" formasi.
 *
 *  Tender-AI dagi tender panelidan `/?take=<tender_id>` havolasi bilan
 *  ochiladi (`ErpLink.tsx`). Tender ma'lumotini forma SO'RAMAYDI: snapshot
 *  serverda, `POST /erp/tenders/{id}/take` ichida tenderdan olinadi —
 *  mijozdan kelgan nom yoki summaga ishonilmaydi. */
export default function TakeTenderDialog(
  { tenderId, onClose, onOpenOpportunity }: TakeTenderDialogProps,
) {
  return (
    <TakeForm
      tenderId={tenderId}
      onClose={onClose}
      onDone={(opp) => onOpenOpportunity?.(opp.id)}
      onOpenOpportunity={onOpenOpportunity}
    />
  )
}


// ---------------------------------------------------------------------------
// Forma
// ---------------------------------------------------------------------------
interface TakeFormProps {
  tenderId: number
  onClose: () => void
  onDone: (opp: Opportunity) => void
  onOpenOpportunity?: (oppId: number) => void
}

function TakeForm({ tenderId, onClose, onDone, onOpenOpportunity }: TakeFormProps) {
  const [meta, setMeta] = useState<ErpMeta | null>(null)
  const [brokers, setBrokers] = useState<ErpBroker[]>([])
  const [clients, setClients] = useState<ErpClient[]>([])
  const [form, setForm] = useState<OpportunityInput>(EMPTY)
  const [error, setError] = useState<string | null>(null)
  // 409 da mavjud kartaga havola: xato matni yetarli emas, foydalanuvchi
  // "qaysi karta?" degan savolga javob olishi kerak.
  const [dupId, setDupId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [newBroker, setNewBroker] = useState<string | null>(null)
  const [newClient, setNewClient] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.meta(), api.brokers(), api.clients()])
      .then(([m, b, c]) => { setMeta(m); setBrokers(b); setClients(c) })
      .catch((e: Error) => setError(e.message))
  }, [])

  const set = (patch: Partial<OpportunityInput>) => setForm((f) => ({ ...f, ...patch }))
  const brokerName = brokers.find((b) => b.id === form.broker_id)?.full_name || null

  async function addBroker() {
    if (!newBroker?.trim()) return
    try {
      const b = await api.addBroker({ full_name: newBroker.trim() })
      setBrokers((xs) => [...xs, b]); set({ broker_id: b.id }); setNewBroker(null)
    } catch (e) { setError((e as Error).message) }
  }

  async function addClient() {
    if (!newClient?.trim()) return
    try {
      const c = await api.createClient({ name: newClient.trim() })
      setClients((xs) => [...xs, c]); set({ client_id: c.id }); setNewClient(null)
    } catch (e) { setError((e as Error).message) }
  }

  async function submit() {
    setSaving(true); setError(null); setDupId(null)
    try {
      // created_by — auth yo'q: tanlangan brokerning nomi (erp_arxitektura.md 5.1)
      onDone(await api.takeTender(tenderId, { ...form, created_by: brokerName }))
    } catch (e) {
      const err = e as ApiError
      const d = err.detail as { message?: string; opportunity_id?: number } | null
      if (err.status === 409 && d?.opportunity_id) {
        setDupId(d.opportunity_id)
        setError(d.message || 'Bu mijoz uchun allaqachon ishga olingan.')
      } else {
        setError(err.message)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-foreground/40 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content className={cn(
          'fixed left-1/2 top-1/2 z-50 w-[min(34rem,calc(100vw-2rem))] max-h-[90vh] overflow-y-auto',
          '-translate-x-1/2 -translate-y-1/2 rounded-lg border bg-popover p-5 shadow-lg',
          'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
        )}>
          <Dialog.Title className="text-lead font-semibold">Tenderni ishga olish</Dialog.Title>
          <Dialog.Description className="mt-1 text-body text-muted-foreground">
            Tender ma'lumotlari kartaga NUSXALANADI: keyin manbada o'zgarsa ham
            karta o'zgarmaydi.
          </Dialog.Description>

          <div className="mt-4 space-y-3.5">
            {/* --- Mas'ul broker --- */}
            <Field label="Mas'ul (broker)">
              <div className="flex gap-2">
                <Select
                  value={form.broker_id ? String(form.broker_id) : ''}
                  onValueChange={(v) => set({ broker_id: Number(v) })}
                >
                  <SelectTrigger className="h-9 flex-1 bg-card text-body">
                    <SelectValue placeholder="Tanlang" />
                  </SelectTrigger>
                  <SelectContent>
                    {brokers.filter((b) => b.active).map((b) => (
                      <SelectItem key={b.id} value={String(b.id)}>{b.full_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {/* NOMI VA HOLATI: `Icon` `aria-hidden`, ya'ni bu tugmada
                    ekran o'quvchisi uchun matn UMUMAN yo'q edi — u "tugma"
                    deb o'qilardi, xolos. `aria-expanded` esa pastda forma
                    ochilganini aytadi. */}
                <Button variant="outline" size="sm" type="button"
                  aria-label="Yangi broker qo'shish"
                  aria-expanded={newBroker !== null}
                  onClick={() => setNewBroker(newBroker === null ? '' : null)}>
                  <Icon name="plus" size={13} />
                </Button>
              </div>
              {newBroker !== null && (
                <div className="mt-2 flex gap-2">
                  <Input autoFocus value={newBroker} placeholder="Yangi broker ismi"
                    onChange={(e) => setNewBroker(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addBroker() } }} />
                  <Button size="sm" type="button" onClick={addBroker}>Qo'shish</Button>
                </div>
              )}
            </Field>

            {/* --- Mijoz korxona --- */}
            <Field label="Mijoz korxona"
              hint="Bir tenderga ikki mijoz nomidan kirish mumkin — har biriga alohida karta.">
              <div className="flex gap-2">
                <Select
                  value={form.client_id ? String(form.client_id) : ''}
                  onValueChange={(v) => set({ client_id: Number(v) })}
                >
                  <SelectTrigger className="h-9 flex-1 bg-card text-body">
                    <SelectValue placeholder="Tanlang" />
                  </SelectTrigger>
                  <SelectContent>
                    {clients.filter((c) => c.active).map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" size="sm" type="button"
                  aria-label="Yangi mijoz korxona qo'shish"
                  aria-expanded={newClient !== null}
                  onClick={() => setNewClient(newClient === null ? '' : null)}>
                  <Icon name="plus" size={13} />
                </Button>
              </div>
              {newClient !== null && (
                <div className="mt-2 flex gap-2">
                  <Input autoFocus value={newClient} placeholder="Yangi korxona nomi"
                    onChange={(e) => setNewClient(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addClient() } }} />
                  <Button size="sm" type="button" onClick={addClient}>Qo'shish</Button>
                </div>
              )}
            </Field>

            {/* --- Ustuvorlik --- */}
            <Field label="Ustuvorlik">
              <div className="flex gap-1.5">
                {(meta?.priorities || []).map((p) => (
                  <button
                    key={p.code} type="button"
                    onClick={() => set({ priority: p.code })}
                    className={cn(
                      'rounded-md border px-3 py-1.5 text-body transition-colors',
                      form.priority === p.code
                        ? 'border-primary bg-secondary font-semibold text-primary'
                        : 'hover:bg-accent',
                    )}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </Field>

            {/* --- Yutish ehtimoli --- */}
            <Field label="Yutish ehtimoli (xodim bahosi)"
              hint="Bu Go/No-Go tavsiyasi va moslik balli EMAS — ular alohida ko'rsatiladi.">
              <div className="flex items-center gap-3">
                <Slider
                  className="flex-1"
                  min={0} max={100} step={5}
                  value={[form.win_probability ?? 0]}
                  onValueChange={([v]) => set({ win_probability: v })}
                />
                <span className="tabular w-12 text-right text-body">
                  {form.win_probability == null ? '—' : `${form.win_probability}%`}
                </span>
              </div>
            </Field>

            {/* --- Izoh va keyingi vazifa --- */}
            <Field label="Izoh">
              <textarea
                className="min-h-16 w-full rounded-md border bg-card px-3 py-2 text-body outline-none focus-visible:border-primary"
                value={form.note ?? ''}
                onChange={(e) => set({ note: e.target.value || null })}
              />
            </Field>

            <div className="flex gap-2">
              <Field label="Keyingi vazifa" className="flex-1">
                <Input value={form.next_task ?? ''} placeholder="Masalan: mijozga KP yuborish"
                  onChange={(e) => set({ next_task: e.target.value || null })} />
              </Field>
              <Field label="Muddati">
                <Input type="date" value={form.next_task_at ?? ''}
                  onChange={(e) => set({ next_task_at: e.target.value || null })} />
              </Field>
            </div>

            {error && (
              <div className="rounded-md border border-urgent/40 bg-urgent-soft px-3 py-2 text-body text-urgent-strong">
                {error}
                {dupId && onOpenOpportunity && (
                  <button type="button" className="ml-2 font-semibold underline"
                    onClick={() => onOpenOpportunity(dupId)}>
                    Mavjud kartani ochish
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" size="sm" type="button" onClick={onClose}>Bekor</Button>
            <Button size="sm" type="button" disabled={saving} onClick={submit}>
              {saving ? 'Saqlanmoqda…' : 'Ishga olish'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function Field({ label, hint, className, children }: {
  label: string; hint?: string; className?: string; children: React.ReactNode
}) {
  return (
    <div className={className}>
      <div className="mb-1 text-caption font-semibold text-muted-foreground">{label}</div>
      {children}
      {hint && <div className="mt-1 text-micro text-muted-foreground">{hint}</div>}
    </div>
  )
}
