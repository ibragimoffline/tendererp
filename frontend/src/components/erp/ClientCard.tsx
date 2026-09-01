import { useEffect, useState } from 'react'
import { api, ApiError } from '@/api'
import { useFormat } from '@/format'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import type {
  ClientContactInput, ClientDocument, ClientDocumentInput, ClientFull,
  ClientInput, DocumentType, ImportResult,
} from '@/types'
import { ErpError, can } from './erpShared'

// KORXONA PASSPORTI (drawer). `id === null` bo'lsa — yangi korxona yaratish.
//
// Passport nima uchun kerak: ariza hujjatlarini mijoz nomidan to'ldirish
// uchun INN, bank rekvizitlari va rahbar ismi shart. Ular tizimda bo'lmasa
// broker ularni har safar qo'ldan qidiradi.
//
// Hujjat turlari — TENDER-AI dagi kanonik ro'yxat (`compliance.DOC_TYPES`),
// ERP backendi orqali keladi (`GET /erp/document-types`). ERP o'z nusxasini
// SAQLAMAYDI: ikki ro'yxat vaqt o'tib ajralib ketardi va cheklist mijoz
// hujjatini tanimay qolardi.

type TabKey = 'passport' | 'contacts' | 'documents' | 'opportunities'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'passport', label: 'Passport' },
  { key: 'contacts', label: 'Aloqa shaxslari' },
  { key: 'documents', label: 'Hujjatlar' },
  { key: 'opportunities', label: 'Kartalar' },
]

const FIELDS: { key: keyof ClientInput; label: string; wide?: boolean }[] = [
  { key: 'name', label: 'Korxona nomi', wide: true },
  { key: 'inn', label: 'INN (9 raqam)' },
  { key: 'oked', label: 'OKED' },
  { key: 'legal_form', label: 'Tashkiliy shakl (MCHJ / AJ / YaTT)' },
  { key: 'tax_mode', label: 'Soliq rejimi' },
  { key: 'address_legal', label: 'Yuridik manzil', wide: true },
  { key: 'address_actual', label: 'Faktik manzil', wide: true },
  { key: 'bank_name', label: 'Bank' },
  { key: 'bank_mfo', label: 'MFO' },
  { key: 'bank_account', label: 'Hisob raqami', wide: true },
  { key: 'director_name', label: 'Rahbar' },
  { key: 'phone', label: 'Telefon' },
  { key: 'email', label: 'Email' },
  { key: 'note', label: 'Izoh', wide: true },
]

const EMPTY_FORM: ClientInput = { name: '', active: true }

interface ClientCardProps {
  /** null — yangi korxona yaratish rejimi */
  id: number | null
  onClose: () => void
  onSaved: (c: ClientFull) => void
  onOpenOpportunity?: (oppId: number) => void
}

export default function ClientCard({ id, onClose, onSaved, onOpenOpportunity }: ClientCardProps) {
  const f = useFormat()
  const [c, setC] = useState<ClientFull | null>(null)
  const [form, setForm] = useState<ClientInput>(EMPTY_FORM)
  const [tab, setTab] = useState<TabKey>('passport')
  const [error, setError] = useState<string | null>(null)
  const [dupId, setDupId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setError(null); setDupId(null)
    if (id === null) { setC(null); setForm(EMPTY_FORM); return }
    api.client(id)
      .then((x) => { setC(x); setForm(toForm(x)) })
      .catch((e: Error) => setError(e.message))
  }, [id])

  function apply(x: ClientFull) { setC(x); setForm(toForm(x)); onSaved(x) }

  async function save() {
    setSaving(true); setError(null); setDupId(null)
    try {
      apply(id === null ? await api.createClient(form) : await api.updateClient(id, form))
    } catch (e) {
      const err = e as ApiError
      const d = err.detail as { message?: string; client_id?: number } | null
      // Takror INN — 409 da MAVJUD korxona id si keladi, foydalanuvchi unga
      // o'tishi kerak, aks holda ikkinchi karta yaratib yuboradi.
      if (err.status === 409 && d?.client_id) {
        setDupId(d.client_id); setError(d.message || 'Bu INN allaqachon ro\'yxatda.')
      } else setError(err.message)
    } finally { setSaving(false) }
  }

  const set = (patch: Partial<ClientInput>) => setForm((x) => ({ ...x, ...patch }))

  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" closeLabel="Yopish"
        className="w-[46rem] max-w-[95vw] overflow-y-auto p-0 sm:max-w-[95vw]">
        <SheetHeader className="sticky top-0 z-10 border-b bg-card px-5 py-3 pr-14">
          <SheetTitle className="line-clamp-1 text-body font-semibold">
            {id === null ? 'Yangi korxona' : (c?.name || 'Korxona')}
          </SheetTitle>
          <SheetDescription className="tabular text-caption">
            {c ? `INN: ${c.inn || '—'}` : 'Passportni to\'ldiring'}
          </SheetDescription>
        </SheetHeader>

        <div className="px-5 pb-10 pt-3">
          {error && (
            <div className="mb-3">
              <ErpError msg={error} />
              {dupId !== null && (
                <button type="button" className="mt-1 text-caption font-semibold text-primary underline"
                  onClick={() => { setError(null); setDupId(null); onSaved({ id: dupId } as ClientFull) }}>
                  Mavjud korxonani ochish
                </button>
              )}
            </div>
          )}

          {id !== null && !c && !error && <Skeleton className="h-48 w-full" />}

          {(id === null || c) && (
            <>
              {/* Yangi korxona yaratilayotganda tablar yo'q: aloqa shaxsi va
                  hujjat qo'shish uchun avval korxona saqlanishi kerak. */}
              {id !== null && (
                <div className="mb-3 flex flex-wrap gap-1.5 border-b pb-2">
                  {TABS.map((x) => (
                    <button key={x.key} type="button" onClick={() => setTab(x.key)}
                      className={cn('rounded-md px-3 py-1.5 text-body transition-colors',
                        tab === x.key ? 'bg-secondary font-semibold text-primary' : 'hover:bg-accent')}>
                      {x.label}
                      {x.key === 'documents' && c && c.documents.length > 0 &&
                        <span className="ml-1 text-micro text-muted-foreground">{c.documents.length}</span>}
                      {x.key === 'opportunities' && c && c.opportunities.length > 0 &&
                        <span className="ml-1 text-micro text-muted-foreground">{c.opportunities.length}</span>}
                    </button>
                  ))}
                </div>
              )}

              {(tab === 'passport' || id === null) && (
                <>
                  {c && c.missing.length > 0 && (
                    <div className="mb-3 rounded-lg border border-soon/40 bg-soon-soft px-3 py-2 text-body text-soon-strong">
                      Ariza uchun yetishmayapti: {c.missing.map(labelOf).join(', ')}
                    </div>
                  )}
                  <div className="grid gap-3 sm:grid-cols-2">
                    {FIELDS.map((fl) => (
                      <div key={fl.key} className={fl.wide ? 'sm:col-span-2' : undefined}>
                        <div className="mb-1 text-caption font-semibold text-muted-foreground">
                          {fl.label}
                        </div>
                        <Input
                          value={(form[fl.key] as string | null) ?? ''}
                          onChange={(e) => set({ [fl.key]: e.target.value || null } as Partial<ClientInput>)}
                        />
                      </div>
                    ))}
                    {/* QQS — HISOB-FAKTURA shu javobga qarab chiqadi
                        (5B-2). Uch holat: to'lovchi / to'lovchi emas /
                        HALI SO'RALMAGAN. Oxirgisi `false` bilan bir xil
                        emas: "bilmaymiz" deb turgani ochiq savol, uni
                        jimgina 0% ga aylantirib yubormaymiz. */}
                    <div className="sm:col-span-2 grid gap-3 border-t pt-3 sm:grid-cols-2">
                      <div>
                        <div className="mb-1 text-caption font-semibold text-muted-foreground">
                          QQS to'lovchimi
                        </div>
                        <Select
                          value={form.vat_payer === true ? 'yes'
                            : form.vat_payer === false ? 'no' : 'unknown'}
                          onValueChange={(v) => set({
                            vat_payer: v === 'yes' ? true : v === 'no' ? false : null,
                          })}>
                          <SelectTrigger className="bg-card text-body">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="unknown">Hali so'ralmagan</SelectItem>
                            <SelectItem value="yes">Ha, to'lovchi</SelectItem>
                            <SelectItem value="no">Yo'q (aylanma solig'i)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <div className="mb-1 text-caption font-semibold text-muted-foreground">
                          Stavka (%) — faktura qatoriga sukut
                        </div>
                        <Input inputMode="decimal" disabled={form.vat_payer !== true}
                          value={form.vat_rate ?? ''}
                          onChange={(e) => set({
                            vat_rate: e.target.value === '' ? null : Number(e.target.value),
                          })} />
                      </div>
                    </div>

                    <label className="flex cursor-pointer items-center gap-2 text-body sm:col-span-2">
                      <input type="checkbox" checked={form.active ?? true}
                        onChange={(e) => set({ active: e.target.checked })} />
                      Faol (ro'yxatlarda ko'rinadi)
                    </label>
                  </div>
                  {can('mijoz.tahrirlash') && (
                    <Button size="sm" className="mt-4" disabled={saving} onClick={save}>
                      {saving ? 'Saqlanmoqda…' : 'Saqlash'}
                    </Button>
                  )}
                </>
              )}

              {id !== null && c && tab === 'contacts' && (
                <Contacts c={c} onChanged={apply} onError={setError} />
              )}
              {id !== null && c && tab === 'documents' && (
                <Documents c={c} onChanged={apply} onError={setError} />
              )}
              {id !== null && c && tab === 'opportunities' && (
                <div>
                  <div className="mb-3 flex flex-wrap gap-4 text-body">
                    <Stat label="Kartalar" v={c.summary.opp_n} />
                    <Stat label="Ishda" v={c.summary.open_n} />
                    <Stat label="Yutilgan" v={c.summary.won_n} />
                    <Stat label="Yutqazilgan" v={c.summary.lost_n} />
                    <Stat label="Yutish foizi"
                      v={c.summary.win_rate == null ? '—' : `${c.summary.win_rate}%`} />
                    {/* Aralash valyutada summa BERILMAYDI (server `null`
                        qaytaradi): "1200 USD + 15 mln UZS" degan son hech
                        narsani anglatmaydi. */}
                    <Stat label="Yutilgan summa"
                      v={c.summary.won_total != null && c.summary.currency
                        ? f.shortMoney(c.summary.won_total, c.summary.currency)
                        : c.summary.mixed_currency ? 'aralash valyuta' : '—'} />
                  </div>
                  <ul className="space-y-1">
                    {c.opportunities.map((o) => (
                      <li key={o.id}>
                        <button type="button" disabled={!onOpenOpportunity}
                          onClick={() => onOpenOpportunity?.(o.id)}
                          className="flex w-full flex-wrap items-baseline gap-2 rounded-md px-2 py-1 text-left text-body enabled:hover:bg-accent">
                          <span className="line-clamp-1 flex-1 font-medium">
                            {o.title || `#${o.tender_ref || o.tender_id}`}
                          </span>
                          <span className="text-caption text-muted-foreground">{o.broker_name || '—'}</span>
                          <span className="text-caption">{o.status}</span>
                          <span className="tabular text-caption">
                            {f.shortMoney(o.start_price, o.currency)}
                          </span>
                        </button>
                      </li>
                    ))}
                    {c.opportunities.length === 0 && (
                      <li className="py-4 text-center text-body text-muted-foreground">
                        Bu korxona nomidan hali tender ishga olinmagan.
                      </li>
                    )}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

// ---------------------------------------------------------------------------
function toForm(c: ClientFull): ClientInput {
  return {
    name: c.name, inn: c.inn, oked: c.oked, legal_form: c.legal_form,
    tax_mode: c.tax_mode, address_legal: c.address_legal,
    address_actual: c.address_actual, bank_name: c.bank_name,
    bank_mfo: c.bank_mfo, bank_account: c.bank_account,
    director_name: c.director_name, phone: c.phone, email: c.email,
    note: c.note, active: c.active,
    vat_payer: c.vat_payer, vat_rate: c.vat_rate,
  }
}

const LABELS: Record<string, string> = {
  inn: 'INN', legal_form: 'tashkiliy shakl', address_legal: 'yuridik manzil',
  bank_account: 'hisob raqami', bank_mfo: 'MFO', director_name: 'rahbar',
  phone: 'telefon',
}
const labelOf = (k: string) => LABELS[k] || k

function Stat({ label, v }: { label: string; v: number | string }) {
  return (
    <div>
      <div className="text-caption text-muted-foreground">{label}</div>
      <div className="tabular text-lead font-semibold">{v}</div>
    </div>
  )
}

// --- aloqa shaxslari --------------------------------------------------------
function Contacts({ c, onChanged, onError }: {
  c: ClientFull; onChanged: (x: ClientFull) => void; onError: (m: string) => void
}) {
  const [add, setAdd] = useState<ClientContactInput | null>(null)

  async function run(p: Promise<ClientFull>) {
    try { onChanged(await p); setAdd(null) } catch (e) { onError((e as Error).message) }
  }

  return (
    <div className="space-y-2">
      <ul className="space-y-1">
        {c.contacts.map((k) => (
          <li key={k.id} className="flex flex-wrap items-baseline gap-2 rounded-md border px-3 py-2 text-body">
            <span className="font-medium">{k.full_name}</span>
            {k.is_primary && (
              <span className="rounded bg-secondary px-1.5 py-px text-micro font-semibold text-primary">
                asosiy
              </span>
            )}
            <span className="text-caption text-muted-foreground">{k.position || '—'}</span>
            <span className="tabular text-caption">{k.phone || ''}</span>
            <span className="text-caption">{k.email || ''}</span>
            {can('mijoz.aloqa') && (
              <button type="button" className="ml-auto text-caption text-urgent-strong hover:underline"
                onClick={() => run(api.deleteContact(k.id))}>
                o'chirish
              </button>
            )}
          </li>
        ))}
        {c.contacts.length === 0 && (
          <li className="py-3 text-body text-muted-foreground">Aloqa shaxsi kiritilmagan.</li>
        )}
      </ul>

      {add === null ? (can('mijoz.aloqa') && (
        <Button variant="outline" size="sm" onClick={() => setAdd({ full_name: '' })}>
          <Icon name="plus" size={13} /> Aloqa shaxsi
        </Button>
      )) : (
        <div className="space-y-2 rounded-md border p-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <Input autoFocus placeholder="Ism familiya" value={add.full_name}
              onChange={(e) => setAdd({ ...add, full_name: e.target.value })} />
            <Input placeholder="Lavozimi" value={add.position ?? ''}
              onChange={(e) => setAdd({ ...add, position: e.target.value || null })} />
            <Input placeholder="Telefon" value={add.phone ?? ''}
              onChange={(e) => setAdd({ ...add, phone: e.target.value || null })} />
            <Input placeholder="Email" value={add.email ?? ''}
              onChange={(e) => setAdd({ ...add, email: e.target.value || null })} />
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-body">
            <input type="checkbox" checked={!!add.is_primary}
              onChange={(e) => setAdd({ ...add, is_primary: e.target.checked })} />
            Asosiy aloqa shaxsi
          </label>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => run(api.addContact(c.id, add))}>Qo'shish</Button>
            <Button variant="outline" size="sm" onClick={() => setAdd(null)}>Bekor</Button>
          </div>
        </div>
      )}
    </div>
  )
}

// --- hujjatlar --------------------------------------------------------------
const EMPTY_DOC: ClientDocumentInput = { doc_type: '', name: '' }

function Documents({ c, onChanged, onError }: {
  c: ClientFull; onChanged: (x: ClientFull) => void; onError: (m: string) => void
}) {
  const [types, setTypes] = useState<DocumentType[]>([])
  const [add, setAdd] = useState<ClientDocumentInput | null>(null)

  useEffect(() => { api.documentTypes().then(setTypes).catch(() => {}) }, [])

  async function reload() {
    try { onChanged(await api.client(c.id)) } catch (e) { onError((e as Error).message) }
  }

  async function create() {
    if (!add) return
    try {
      await api.addClientDocument(c.id, add)
      setAdd(null); reload()
    } catch (e) { onError((e as Error).message) }
  }

  async function remove(d: ClientDocument) {
    try { await api.deleteClientDocument(d.id); reload() } catch (e) {
      onError((e as Error).message)
    }
  }

  const typeLabel = (code: string) => types.find((t) => t.code === code)?.label || code

  return (
    <div className="space-y-2">
      <p className="text-caption text-muted-foreground">
        Bu hujjatlar tender cheklistida shu mijoz nomidan qatnashilganda
        tekshiriladi. Muddat bo'sh qoldirilsa — hujjat muddatsiz deb olinadi.
      </p>

      <ImportBlock clientId={c.id} onDone={reload} onError={onError} />

      <ul className="space-y-1">
        {c.documents.map((d) => (
          <li key={d.id} className="flex flex-wrap items-baseline gap-2 rounded-md border px-3 py-2 text-body">
            <Icon name="clip" size={11} className="text-muted-foreground" />
            <span className="font-medium">{d.name}</span>
            <span className="text-caption text-muted-foreground">{typeLabel(d.doc_type)}</span>
            {d.number && <span className="tabular text-caption">№ {d.number}</span>}
            <span className="tabular text-caption text-muted-foreground">
              {d.valid_until ? `gacha ${d.valid_until}` : 'muddatsiz'}
            </span>
            {can('mijoz.hujjat') && (
              <button type="button" className="ml-auto text-caption text-urgent-strong hover:underline"
                onClick={() => remove(d)}>
                o'chirish
              </button>
            )}
          </li>
        ))}
        {c.documents.length === 0 && (
          <li className="py-3 text-body text-muted-foreground">Hujjat kiritilmagan.</li>
        )}
      </ul>

      {add === null ? (can('mijoz.hujjat') && (
        <Button variant="outline" size="sm" onClick={() => setAdd(EMPTY_DOC)}>
          <Icon name="plus" size={13} /> Hujjat
        </Button>
      )) : (
        <div className="space-y-2 rounded-md border p-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <Select value={add.doc_type || undefined}
              onValueChange={(v) => setAdd({ ...add, doc_type: v })}>
              <SelectTrigger className="h-9 bg-card text-body">
                <SelectValue placeholder="Hujjat turi" />
              </SelectTrigger>
              <SelectContent>
                {types.map((t) => (
                  <SelectItem key={t.code} value={t.code}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input placeholder="Hujjat nomi" value={add.name}
              onChange={(e) => setAdd({ ...add, name: e.target.value })} />
            <Input placeholder="Raqami" value={add.number ?? ''}
              onChange={(e) => setAdd({ ...add, number: e.target.value || null })} />
            <div className="flex gap-2">
              <div className="flex-1">
                <div className="mb-1 text-micro text-muted-foreground">Berilgan</div>
                <Input type="date" value={add.issued_at ?? ''}
                  onChange={(e) => setAdd({ ...add, issued_at: e.target.value || null })} />
              </div>
              <div className="flex-1">
                <div className="mb-1 text-micro text-muted-foreground">Amal qiladi</div>
                <Input type="date" value={add.valid_until ?? ''}
                  onChange={(e) => setAdd({ ...add, valid_until: e.target.value || null })} />
              </div>
            </div>
            <Input className="sm:col-span-2" placeholder="Havola yoki fayl yo'li"
              value={add.file_ref ?? ''}
              onChange={(e) => setAdd({ ...add, file_ref: e.target.value || null })} />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={create}>Qo'shish</Button>
            <Button variant="outline" size="sm" onClick={() => setAdd(null)}>Bekor</Button>
          </div>
        </div>
      )}
    </div>
  )
}


// --- shablon va import -------------------------------------------------------
// NEGA SHABLON: bir korxonaning 10 ta hujjatini forma orqali kiritish — bazani
// birinchi marta to'ldirishdagi eng katta to'siq. Shablon TALAB ETILADIGAN
// hujjatlar ro'yxati bilan oldindan to'ldirilgan keladi.
//
// TARTIB katalog importi (P0-4) bilan bir xil: fayl -> DRY-RUN (bazaga
// tegilmaydi, natija ko'rsatiladi) -> tasdiqlash. "Yukladim va nima
// bo'lganini bilmayman" holati bo'lmasligi kerak.
//
// Faylni TENDER-AI o'qiydi (shablon qoidalari o'sha yerda), yozishni ERP
// qiladi — hujjatlar ERP bazasida.
function ImportBlock({ clientId, onDone, onError }: {
  clientId: number; onDone: () => void; onError: (m: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportResult | null>(null)
  const [busy, setBusy] = useState(false)

  async function pick(f: File | null) {
    setFile(f); setPreview(null)
    if (!f) return
    setBusy(true)
    try {
      setPreview(await api.importClientDocuments(clientId, f, true))
    } catch (e) {
      onError((e as Error).message); setFile(null)
    } finally { setBusy(false) }
  }

  async function confirm() {
    if (!file) return
    setBusy(true)
    try {
      await api.importClientDocuments(clientId, file, false)
      setFile(null); setPreview(null); onDone()
    } catch (e) {
      onError((e as Error).message)
    } finally { setBusy(false) }
  }

  return (
    <div className="rounded-md border bg-muted/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* Havola emas, TUGMA: endpoint himoyalangan va `<a href>`
            `Authorization` sarlavhasini yubormaydi. */}
        <button type="button" disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md border bg-card px-3 py-1.5 text-body transition-colors hover:bg-accent"
          onClick={() => api.downloadClientTemplate(clientId, 'xlsx')
            .catch((e) => onError((e as Error).message))}>
          <Icon name="clip" size={13} /> Shablon (.xlsx)
        </button>
        <button type="button" className="text-caption text-primary hover:underline"
          onClick={() => api.downloadClientTemplate(clientId, 'csv')
            .catch((e) => onError((e as Error).message))}>
          .csv
        </button>
        <label className="ml-auto inline-flex cursor-pointer items-center gap-1.5 rounded-md border bg-card px-3 py-1.5 text-body transition-colors hover:bg-accent">
          <Icon name="plus" size={13} />
          {busy ? 'Tekshirilmoqda…' : "To'ldirilgan faylni yuklash"}
          <input type="file" className="hidden" accept=".xlsx,.csv"
            onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </label>
      </div>

      {preview && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap items-center gap-1.5 text-body">
            <span className="rounded bg-ok-soft px-1.5 py-px text-micro font-semibold text-ok-strong">
              qabul: {preview.rows_ok}
            </span>
            {preview.rows_error > 0 && (
              <span className="rounded bg-urgent-soft px-1.5 py-px text-micro font-semibold text-urgent-strong">
                xato qator: {preview.rows_error}
              </span>
            )}
            <span className="text-caption text-muted-foreground">
              {preview.inserted} qo'shiladi · {preview.updated} yangilanadi
            </span>
          </div>

          {/* Xatolar YASHIRILMAYDI: qaysi qator, qaysi ustun, nega. */}
          {preview.errors.length > 0 && (
            <ul className="space-y-0.5 text-caption text-urgent-strong">
              {preview.errors.slice(0, 8).map((e, i) => (
                <li key={i}>{e.row}-qator · {e.column}: {e.message}</li>
              ))}
              {preview.errors.length > 8 && (
                <li className="text-muted-foreground">
                  …yana {preview.errors.length - 8} ta
                </li>
              )}
            </ul>
          )}

          {preview.rows.length > 0 && (
            <ul className="space-y-0.5 text-caption">
              {preview.rows.slice(0, 6).map((r) => (
                <li key={r.row}>
                  <span className="text-muted-foreground">{r.row}-qator ·</span>{' '}
                  {r.label || r.doc_type} — {r.name}
                  {r.valid_until ? ` (gacha ${r.valid_until})` : ' (muddatsiz)'}
                </li>
              ))}
              {preview.rows.length > 6 && (
                <li className="text-muted-foreground">
                  …yana {preview.rows.length - 6} ta
                </li>
              )}
            </ul>
          )}

          <div className="flex gap-2">
            <Button size="sm" disabled={busy || preview.rows_ok === 0} onClick={confirm}>
              Import qilish
            </Button>
            <Button variant="outline" size="sm"
              onClick={() => { setFile(null); setPreview(null) }}>
              Bekor
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
