import { useEffect, useState } from 'react'
import { api, ApiError } from '@/api'
import { useFormat, DEADLINE_CLASS } from '@/format'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Slider } from '@/components/ui/slider'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import type {
  ComplianceResult, ErpBroker, ErpClient, ErpStatus, Opportunity, OpportunityInput,
  TenderDiff,
} from '@/types'
import StatusChangeDialog from './StatusChangeDialog'
import ContractList from './ContractList'
import SubmissionPanel from './SubmissionPanel'
import TaskList from './TaskList'
import ReservePanel from './ReservePanel'
import InvoiceLinks from './InvoiceLinks'
import ProfitLine from './ProfitLine'
import { ErpError, OPP_LABEL, StatusBadge, can } from './erpShared'
import TahlilPanel from './TahlilPanel'

// OPPORTUNITY KARTASI (drawer).
//
// Chap tomon — SNAPSHOT: ishga olingan paytdagi tender ma'lumoti. U ATAYLAB
// muzlatilgan va bu yerdan tahrirlanmaydi (erp_arxitektura.md 2.2).
// O'ng tomon — xodim maydonlari, status va tarix.
//
// CHEKLIST — kartaning MIJOZI hujjatlariga qarab. Qoidalar tender-ai'da
// (DOC_TYPES, matndan talab aniqlash, 1400 qator) va ERP ularni
// TAKRORLAMAYDI: mijoz hujjatlari serverdan tender-ai'ga yuboriladi, bu yerga
// tayyor natija keladi (`GET /erp/opportunities/{id}/compliance`).
//
// Narx hisobi, ombor qoldig'i va tender hujjatlari ERP'da KO'RSATILMAYDI —
// ular tender-ai ning ishi. Karta ularga havola beradi (yangi oyna).
// Sabab: bir xil panelni ikki ilovada saqlash ikki marta qarishga olib keladi.

interface OpportunityCardProps {
  id: number
  statuses: ErpStatus[]
  /** shartnoma holatlari (`/erp/meta`) */
  contractStatuses?: { code: string; label: string }[]
  /** yutqazish sabablari (`/erp/meta`) — 'lost' ga o'tishda so'raladi */
  lostReasons?: { code: string; label: string }[]
  brokers: ErpBroker[]
  clients: ErpClient[]
  priorities: { code: string; label: string }[]
  onClose: () => void
  /** Karta o'zgardi — ro'yxatni yangilash uchun */
  onChanged: (o: Opportunity) => void
  /** Tender-AI interfeysining manzili (`/erp/meta` -> tender_web).
   *  Kartadagi "Tender-AI panelida ochish" havolasi shundan quriladi. */
  tenderWeb?: string
}

export default function OpportunityCard(props: OpportunityCardProps) {
  const { id, statuses, brokers, clients, priorities, lostReasons,
          contractStatuses, onClose, onChanged, tenderWeb } = props
  const f = useFormat()
  const [o, setO] = useState<Opportunity | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<OpportunityInput | null>(null)
  const [saving, setSaving] = useState(false)
  // "Qayta taqsimlashni so'rash" — brokerda kartani o'tkazish
  // huquqi yo'q, lekin so'rovi IZ QOLDIRISHI kerak.
  const [sorov, setSorov] = useState<string | null>(null)
  const [sorovNatija, setSorovNatija] = useState<string | null>(null)
  const [ask, setAsk] = useState<ErpStatus | null>(null)
  // Snapshot jonli tenderdan farq qiladimi — karta bilan birga yuklanadi
  // (bitta yengil so'rov) va SNAPSHOTNI O'ZGARTIRMAYDI.
  const [diff, setDiff] = useState<TenderDiff | null>(null)
  const [diffOpen, setDiffOpen] = useState(false)
  // Cheklist faqat SO'RALGANDA yuklanadi — karta ochilishi sekinlashmasin
  const [checklist, setChecklist] = useState<ComplianceResult | null>(null)
  const [checklistOpen, setChecklistOpen] = useState(false)
  const [checklistError, setChecklistError] = useState<string | null>(null)
  const [submissionOpen, setSubmissionOpen] = useState(false)

  useEffect(() => {
    setO(null); setError(null)
    setDiff(null); setDiffOpen(false)
    setChecklist(null); setChecklistOpen(false); setChecklistError(null)
    setSubmissionOpen(false)
    api.opportunity(id)
      .then((x) => { setO(x); setForm(toForm(x)) })
      .catch((e: Error) => setError(e.message))
    // Farq — ma'lumot, majburiyat emas: so'rov yiqilsa karta baribir ochiladi.
    api.tenderDiff(id).then(setDiff).catch(() => setDiff(null))
  }, [id])

  // Cheklist tender-ai orqali keladi. U yiqilgan bo'lsa ERP ishlayveradi —
  // xato SHU BLOKDA ko'rsatiladi, karta yopilmaydi.
  useEffect(() => {
    if (!o || !checklistOpen || checklist) return
    setChecklistError(null)
    api.compliance(o.id)
      .then(setChecklist)
      .catch((e: ApiError) => setChecklistError(
        e.status === 503 ? 'Tender-AI javob bermadi — cheklist hozir mavjud emas.'
          : e.message))
  }, [o, checklistOpen, checklist])

  function apply(x: Opportunity) { setO(x); setForm(toForm(x)); onChanged(x) }

  async function save() {
    if (!form || !o) return
    setSaving(true); setError(null)
    try { apply(await api.updateOpportunity(o.id, form)) } catch (e) {
      setError((e as Error).message)
    } finally { setSaving(false) }
  }

  async function setStatus(s: ErpStatus, note: string | null,
                           lostReason?: string | null) {
    if (!o) return
    setError(null)
    try {
      apply(await api.setStatus(o.id, {
        status: s.code, changed_by: o.broker?.name ?? null, note,
        lost_reason: lostReason ?? null,
      }))
    } catch (e) { setError((e as Error).message) }
  }

  const d = o ? f.deadline(o.tender.deadline_at) : null
  const set = (patch: Partial<OpportunityInput>) =>
    setForm((x) => (x ? { ...x, ...patch } : x))

  // TAHRIRLASH IKKI SHARTGA BOG'LIQ va ikkalasi ham EKRANDA ko'rinadi.
  //
  //  1. HUQUQ — brokerda `karta.tahrirlash` faqat o'z kartasiga
  //     (server ham shuni tekshiradi; bu yerda faqat ko'rinish).
  //  2. YAKUNLANGAN KARTA — "Yutildi / Yutqazildi / Rad etildi" dan
  //     keyin maydonlar qotadi. Ilgari yopilgan kartani ham to'liq
  //     tahrirlash mumkin edi: yutilgan tenderning summasi yoki mijozi
  //     jimgina o'zgarib ketardi va buni hech narsa qayd qilmasdi.
  //     Tuzatish yo'li yopilmagan — avval statusni qaytarish kerak, u
  //     esa IZOH so'raydi va tarixda qoladi.
  const editable = !!o && !o.is_final && can('karta.tahrirlash')

  return (
    <Sheet open onOpenChange={(x) => { if (!x) onClose() }}>
      <SheetContent side="right" closeLabel="Yopish"
        className="w-[46rem] max-w-[95vw] overflow-y-auto p-0 sm:max-w-[95vw]">
        <SheetHeader className="sticky top-0 z-10 border-b bg-card px-5 py-3 pr-14">
          <SheetTitle className="line-clamp-1 text-body font-semibold">
            {o ? OPP_LABEL(o) : 'Karta'}
          </SheetTitle>
          <SheetDescription className="tabular text-caption">
            {o ? `Karta #${o.id} · Tender #${o.tender.tender_ref || o.tender_id}` : ''}
          </SheetDescription>
        </SheetHeader>

        <div className="px-5 pb-10 pt-3">
          {error && <div className="mb-3"><ErpError msg={error} /></div>}
          {!o && !error && (
            <div className="space-y-3">
              <Skeleton className="h-6 w-2/3" /><Skeleton className="h-32 w-full" />
            </div>
          )}

          {o && form && (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <StatusBadge o={o} />
                {d && d.level !== 'none' && (
                  <span className={cn('rounded px-2 py-0.5 text-caption font-semibold',
                    DEADLINE_CLASS[d.level])}>{d.text}</span>
                )}
                {o.closed_at && (
                  <span className="text-caption text-muted-foreground">
                    Yopilgan: {f.dateFmt(o.closed_at)}
                  </span>
                )}
                {o.lost_reason && (
                  <span className="rounded bg-muted px-2 py-0.5 text-caption text-muted-foreground">
                    Sabab: {lostReasons?.find((r) => r.code === o.lost_reason)?.label
                      || o.lost_reason}
                  </span>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {/* --- SNAPSHOT (o'zgarmas) --- */}
                <section className="rounded-lg border bg-muted/40 p-3">
                  <h3 className="mb-2 text-caption font-semibold text-muted-foreground">
                    Tender ma'lumoti (ishga olingan paytdagi nusxa)
                  </h3>

                  {/* SNAPSHOT O'ZGARMAYDI — bu faqat xabar. Qaysi qiymat
                      to'g'ri ekanini odam hal qiladi: muddat ko'chgan bo'lsa
                      reja, narx qayta e'lon qilingan bo'lsa hisob eskiradi. */}
                  {diff && !diff.exists && (
                    <div className="mb-2 rounded-md border border-soon/40 bg-soon-soft px-2.5 py-1.5 text-caption text-soon-strong">
                      Tender manbada yo'q (o'chirilgan yoki arxivlangan).
                      Kartadagi nusxa o'z joyida qoladi.
                    </div>
                  )}
                  {/* Manba tenderni yopgan, karta esa ochiq. TAKLIF, buyruq
                      emas: manba g'olibni bermaydi, "yutdikmi?" ni odam biladi. */}
                  {diff && diff.suggest_close && (
                    <div className="mb-2 rounded-md border border-soon/40 bg-soon-soft px-2.5 py-1.5 text-caption text-soon-strong">
                      Tender manbada yopilgan
                      {diff.source?.status_name ? ` (${diff.source.status_name})` : ''} —
                      kartani yakunlash kerakmi?
                    </div>
                  )}
                  {diff && diff.exists && diff.changed.length > 0 && (
                    <div className="mb-2 rounded-md border border-soon/40 bg-soon-soft px-2.5 py-1.5 text-caption text-soon-strong">
                      <button type="button" className="font-semibold underline"
                        onClick={() => setDiffOpen((v) => !v)}>
                        Tenderda {diff.changed.length} maydon o'zgargan
                      </button>
                      {diffOpen && (
                        <ul className="mt-1.5 space-y-1">
                          {diff.changed.map((ch) => (
                            <li key={ch.field}>
                              <span className="font-medium">{ch.label}:</span>{' '}
                              <span className="line-through opacity-70">
                                {fmtDiff(ch.was)}
                              </span>{' '}
                              → {fmtDiff(ch.now)}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  <dl className="space-y-1.5 text-body">
                    <Row k="Buyurtmachi" v={o.tender.customer_name} />
                    <Row k="Hudud" v={o.tender.region_name} />
                    <Row k="Boshlang'ich narx"
                      v={f.money(o.tender.start_price, o.tender.currency)} />
                    <Row k="Deadline" v={f.dateFmt(o.tender.deadline_at)} />
                    <Row k="Manba" v={o.tender.source_platform} />
                  </dl>
                  <div className="mt-3 flex flex-wrap gap-3">
                    {o.tender.source_url && (
                      <a className="inline-flex items-center gap-1 text-caption font-semibold text-primary hover:underline"
                        href={o.tender.source_url} target="_blank" rel="noopener noreferrer">
                        Manbada ochish <Icon name="external" size={11} />
                      </a>
                    )}
                    {/* Tender-AI dagi to'liq panel: hujjatlar, narx hisobi,
                        ombor qoldig'i, Go/No-Go — hammasi o'sha yerda qoladi
                        va ERP'da takrorlanmaydi. */}
                    {tenderWeb && (
                      <a className="inline-flex items-center gap-1 text-caption font-semibold text-primary hover:underline"
                        href={`${tenderWeb}/?tender=${o.tender_id}`}
                        target="_blank" rel="noopener noreferrer">
                        Tender-AI panelida ochish <Icon name="external" size={11} />
                      </a>
                    )}
                  </div>
                </section>

                {/* --- XODIM MAYDONLARI --- */}
                <section className="space-y-3">
                  <div>
                    <Label>Status</Label>
                    <Select value={o.status} onValueChange={(v) => {
                      const s = statuses.find((x) => x.code === v)
                      if (!s || s.code === o.status) return
                      if (s.final || o.is_final) setAsk(s)
                      else setStatus(s, null)
                    }}>
                      <SelectTrigger className="h-9 w-full bg-card text-body">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {/* YAKUNIY status (yutildi / yutqazildi / rad) —
                            alohida huquq (`karta.yopish`) va u kompaniya
                            sozlamasi bilan brokerdan olib qo'yilishi
                            mumkin ("Broker kartani o'zi yakunlaydi").
                            Ro'yxatdan CHIQARIB tashlanadi: tanlanib
                            403 olinadigan variant — yolg'on va'da. */}
                        {statuses.filter((s) => !s.final || can('karta.yopish'))
                          .map((s) => (
                          <SelectItem key={s.code} value={s.code}>{s.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Broker mas'ulni O'ZI o'zgartira olmaydi
                      (`karta.biriktirish` unda yo'q), lekin
                      "menga to'g'ri kelmadi" deya oladi — aks holda
                      u menejerni og'zaki qidiradi va iz qolmaydi. */}
                  {!can('karta.biriktirish') && can('karta.taqsimlash_sorovi') && (
                    <div className="rounded-md border border-dashed p-2">
                      {sorov === null ? (
                        <button type="button"
                          className="text-caption underline"
                          onClick={() => { setSorov(''); setSorovNatija(null) }}>
                          Qayta taqsimlashni so'rash
                        </button>
                      ) : (
                        <div className="space-y-2">
                          <Input autoFocus placeholder="Sabab (majburiy)"
                            value={sorov}
                            onChange={(e) => setSorov(e.target.value)} />
                          <div className="flex gap-2">
                            <Button size="sm" disabled={!sorov.trim()}
                              onClick={async () => {
                                try {
                                  await api.requestReassign(o.id, sorov)
                                  setSorov(null)
                                  setSorovNatija('So‘rov menejerga yuborildi.')
                                  // Tarixda ko'rinishi uchun kartani
                                  // qayta o'qiymiz.
                                  apply(await api.opportunity(o.id))
                                } catch (e) {
                                  setSorovNatija((e as Error).message)
                                }
                              }}>So'rash</Button>
                            <Button size="sm" variant="outline"
                              onClick={() => setSorov(null)}>Bekor</Button>
                          </div>
                        </div>
                      )}
                      {sorovNatija && (
                        <div className="mt-1 text-caption text-muted-foreground">
                          {sorovNatija}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="flex gap-2">
                    <div className="flex-1">
                      <Label>Mas'ul</Label>
                      <Select value={form.broker_id ? String(form.broker_id) : ''}
                        disabled={!editable}
                        onValueChange={(v) => set({ broker_id: Number(v) })}>
                        <SelectTrigger className="h-9 w-full bg-card text-body">
                          <SelectValue placeholder="—" />
                        </SelectTrigger>
                        <SelectContent>
                          {brokers.map((b) => (
                            <SelectItem key={b.id} value={String(b.id)}>{b.full_name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex-1">
                      <Label>Mijoz</Label>
                      <Select value={form.client_id ? String(form.client_id) : ''}
                        disabled={!editable}
                        onValueChange={(v) => set({ client_id: Number(v) })}>
                        <SelectTrigger className="h-9 w-full bg-card text-body">
                          <SelectValue placeholder="—" />
                        </SelectTrigger>
                        <SelectContent>
                          {clients.map((c) => (
                            <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <Label>Ustuvorlik</Label>
                    <div className="flex gap-1.5">
                      {priorities.map((p) => (
                        <button key={p.code} type="button" disabled={!editable}
                          onClick={() => set({ priority: p.code })}
                          className={cn('rounded-md border px-3 py-1.5 text-body transition-colors',
                            'disabled:cursor-not-allowed disabled:opacity-60',
                            form.priority === p.code
                              ? 'border-primary bg-secondary font-semibold text-primary'
                              : 'enabled:hover:bg-accent')}>
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <Label>Yutish ehtimoli (xodim bahosi)</Label>
                    <div className="flex items-center gap-3">
                      <Slider className="flex-1" min={0} max={100} step={5}
                        disabled={!editable}
                        value={[form.win_probability ?? 0]}
                        onValueChange={([v]) => set({ win_probability: v })} />
                      <span className="tabular w-12 text-right text-body">
                        {form.win_probability == null ? '—' : `${form.win_probability}%`}
                      </span>
                    </div>
                  </div>

                  <div>
                    <Label>Izoh</Label>
                    <textarea
                      disabled={!editable}
                      className="min-h-16 w-full rounded-md border bg-card px-3 py-2 text-body outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-70"
                      value={form.note ?? ''}
                      onChange={(e) => set({ note: e.target.value || null })} />
                  </div>

                  {/* "Keyingi vazifa" maydoni OLIB TASHLANDI: u
                      `erp.opportunity` ustuniga yozilardi va hech
                      qayerda ko'rinmasdi — vazifalar ro'yxati ham,
                      "mening ishlarim" ham, eslatma ham
                      `erp.opportunity_task` dan o'qiydi. Endi ish
                      pastdagi "Vazifalar" ro'yxatiga yoziladi. */}

                  {editable ? (
                    <Button size="sm" disabled={saving} onClick={save}>
                      {saving ? 'Saqlanmoqda…' : 'Saqlash'}
                    </Button>
                  ) : (
                    <p className="text-caption text-muted-foreground">
                      {o.is_final
                        ? 'Karta yakunlangan — maydonlar tahrirlanmaydi. '
                          + 'Tuzatish kerak bo\'lsa avval statusni ochiq '
                          + 'holatga qaytaring (izoh so\'raladi va tarixda qoladi).'
                        : 'Kartani tahrirlash — rahbar yoki menejer huquqi.'}
                    </p>
                  )}
                </section>
              </div>

              <TaskList oppId={o.id} brokers={brokers}
                createdBy={o.broker?.name ?? null} />

              {/* Ombordan ajratilgan tovar. Status o'zgarganda rezerv
                  o'zi yopiladi, shuning uchun karta yangilanadi. */}
              <ReservePanel oppId={o.id} oppStatus={o.status}
                onChanged={() => { /* qoldiq keyingi ochilishda yangilanadi */ }} />

              {/* Zanjir: taklif -> shartnoma -> FAKTURA -> to'lov */}
              <InvoiceLinks oppId={o.id} />

              {/* "Bu tenderdan qancha ishladik?" — zanjirning natijasi */}
              <ProfitLine oppId={o.id} />

              {/* Taklif -> SHARTNOMA zanjirining oxirgi bo'g'ini */}
              {!!contractStatuses?.length && (
                <ContractList oppId={o.id} statuses={contractStatuses}
                  submissions={[]} createdBy={o.broker?.name ?? null} />
              )}

              {/* --- TENDER-AI TAHLILI (qaror paytidagi surat) ---
                  Qo'lda ochilgan kartada bo'lmaydi va u holda blok
                  umuman ko'rsatilmaydi. */}
              <TahlilPanel oppId={o.id} />

              {/* --- TARIX --- */}
              <section className="mt-5">
                <h3 className="mb-2 text-caption font-semibold text-muted-foreground">Tarix</h3>
                <ol className="space-y-1.5">
                  {(o.history || []).map((h) => (
                    <li key={h.id} className="flex flex-wrap items-baseline gap-2 border-l-2 pl-3 text-body">
                      <span className="tabular text-micro text-muted-foreground">
                        {f.dateFmt(h.changed_at)}
                      </span>
                      <span className="font-medium">
                        {h.from_label ? `${h.from_label} → ${h.to_label}` : h.to_label}
                      </span>
                      {h.changed_by && (
                        <span className="text-caption text-muted-foreground">{h.changed_by}</span>
                      )}
                      {h.note && <span className="text-caption">— {h.note}</span>}
                    </li>
                  ))}
                </ol>
              </section>

              {/* --- TAKLIF: narx + cheklist + hujjatlar bir joyda --- */}
              <section className="mt-5">
                <button type="button"
                  onClick={() => setSubmissionOpen((v) => !v)}
                  className={cn('rounded-md px-3 py-1.5 text-body transition-colors',
                    submissionOpen ? 'bg-secondary font-semibold text-primary'
                      : 'hover:bg-accent')}>
                  Taklif va topshirish
                </button>
                {submissionOpen && (
                  <div className="mt-2">
                    <SubmissionPanel oppId={o.id} onChanged={apply} />
                  </div>
                )}
              </section>

              {/* --- CHEKLIST: mijoz hujjatlariga qarab --- */}
              <section className="mt-5">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <button type="button"
                    onClick={() => setChecklistOpen((v) => !v)}
                    className={cn('rounded-md px-3 py-1.5 text-body transition-colors',
                      checklistOpen ? 'bg-secondary font-semibold text-primary' : 'hover:bg-accent')}>
                    Hujjatlar cheklisti
                  </button>
                  {o.client
                    ? <span className="text-caption text-muted-foreground">
                        {o.client.name} hujjatlari bo'yicha
                      </span>
                    : <span className="text-caption text-muted-foreground">
                        mijoz tanlanmagan — kompaniya hujjatlari bo'yicha
                      </span>}
                </div>

                {checklistOpen && checklistError && <ErpError msg={checklistError} />}
                {checklistOpen && !checklist && !checklistError && (
                  <Skeleton className="h-32 w-full rounded-lg" />
                )}
                {checklistOpen && checklist && <Checklist data={checklist} />}
              </section>

            </>
          )}
        </div>

        {ask && o && (
          <StatusChangeDialog o={o} to={ask} lostReasons={lostReasons}
            onCancel={() => setAsk(null)}
            onConfirm={(note, reason) => {
              const s = ask; setAsk(null); setStatus(s, note, reason)
            }} />
        )}
      </SheetContent>
    </Sheet>
  )
}

// ---------------------------------------------------------------------------
function toForm(o: Opportunity): OpportunityInput {
  return {
    broker_id: o.broker?.id ?? null,
    client_id: o.client?.id ?? null,
    priority: o.priority,
    win_probability: o.win_probability,
    note: o.note,
    next_task: o.next_task,
    next_task_at: o.next_task_at,
  }
}

/** Farq qiymati: uzun matn qisqartiriladi, bo'sh qiymat "—". */
function fmtDiff(v: string | number | null): string {
  if (v === null || v === '') return '—'
  const s = String(v)
  return s.length > 60 ? `${s.slice(0, 60)}…` : s
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="mb-1 text-caption font-semibold text-muted-foreground">{children}</div>
}

function Row({ k, v }: { k: string; v?: string | null }) {
  return (
    <div className="flex gap-2">
      <dt className="w-36 shrink-0 text-caption text-muted-foreground">{k}</dt>
      <dd className="flex-1">{v || '—'}</dd>
    </div>
  )
}

const CHECK_CLASS: Record<string, string> = {
  ok: 'bg-ok-soft text-ok-strong',
  expiring_soon: 'bg-soon-soft text-soon-strong',
  expired: 'bg-urgent-soft text-urgent-strong',
  missing: 'bg-urgent-soft text-urgent-strong',
}
const CHECK_LABEL: Record<string, string> = {
  ok: 'bor', expiring_soon: 'muddati tugayapti',
  expired: 'muddati tugagan', missing: "yo'q",
}

/** Cheklist natijasi. QOIDALAR BU YERDA EMAS — ular tender-ai'da hisoblanadi
 *  va bu komponent faqat javobni chizadi. Shu tufayli qoidalar o'zgarsa ERP
 *  o'zgarmaydi. */
function Checklist({ data }: { data: ComplianceResult }) {
  const s = data.summary
  return (
    <div className="rounded-lg border">
      <div className="flex flex-wrap items-center gap-1.5 border-b px-3 py-2">
        <span className="rounded bg-ok-soft px-1.5 py-px text-micro font-semibold text-ok-strong">
          tayyor: {s.ready}
        </span>
        {s.expiring_soon > 0 && (
          <span className="rounded bg-soon-soft px-1.5 py-px text-micro font-semibold text-soon-strong">
            muddati tugayapti: {s.expiring_soon}
          </span>
        )}
        {s.expired > 0 && (
          <span className="rounded bg-urgent-soft px-1.5 py-px text-micro font-semibold text-urgent-strong">
            muddati tugagan: {s.expired}
          </span>
        )}
        {s.missing > 0 && (
          <span className="rounded bg-urgent-soft px-1.5 py-px text-micro font-semibold text-urgent-strong">
            yo'q: {s.missing}
          </span>
        )}
      </div>

      <ul className="divide-y">
        {data.items.map((it) => (
          <li key={it.doc_type} className="flex flex-wrap items-baseline gap-2 px-3 py-2 text-body">
            <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
              CHECK_CLASS[it.status] || 'bg-muted text-muted-foreground')}>
              {CHECK_LABEL[it.status] || it.status}
            </span>
            <span className="font-medium">{it.label}</span>
            {it.required_by === 'tender' && (
              <span className="rounded bg-secondary px-1.5 py-px text-micro text-primary"
                title={it.evidence || undefined}>
                tenderda talab qilingan
              </span>
            )}
            {it.document?.valid_until && (
              <span className="tabular text-micro text-muted-foreground">
                gacha {it.document.valid_until}
                {it.days_left != null && ` (${it.days_left} kun)`}
              </span>
            )}
          </li>
        ))}
      </ul>

      {/* MVP chekloviни YASHIRMAYMIZ (tender-ai dagi bilan bir xil matn) */}
      <div className="border-t px-3 py-2 text-micro text-muted-foreground">
        {s.disclaimer}
      </div>
    </div>
  )
}
