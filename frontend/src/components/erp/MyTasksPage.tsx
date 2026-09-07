import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat, DEADLINE_CLASS } from '@/format'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Icon from '../Icon'
import type { ErpBroker, MyTask, MyTasks, TaskInput, Yuklama } from '@/types'
import { ALL, ErpError, can, permLevel } from './erpShared'

//: Filtrda "sukut" qiymati. Radix Select bo'sh satrni qabul qilmaydi.
const SELF = '__self__'

/** Ro'yxat filtri. Bo'sh satr = "hammasi" (Radix uchun 'all' ga
 *  aylantiriladi). */
interface Filtr {
  kontekst: string
  status: string
  priority: string
  overdue: boolean
  q: string
}

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
  // KENGAYTIRILGAN RO'YXAT (28-patch): umumiy vazifalar, filtrlar va
  // yakunlanganlar. `data` (guruhlangan "bugun/kechikkan") o'z
  // joyida QOLADI — u kunni boshlash uchun va uni filtr almashtirib
  // yo'qotib qo'ymaslik kerak.
  const [filtr, setFiltr] = useState<Filtr>({ kontekst: '', status: '',
                                              priority: '', overdue: false,
                                              q: '' })
  const [royxat, setRoyxat] = useState<MyTask[] | null>(null)
  const [yangi, setYangi] = useState<TaskInput | null>(null)
  const [yuklama, setYuklama] = useState<Yuklama[] | null>(null)
  const [busy, setBusy] = useState(false)
  const filtrlangan = !!(filtr.kontekst || filtr.status || filtr.priority
                         || filtr.overdue || filtr.q)
  const yaratadi = can('vazifa.yaratish')
  const biriktiradi = can('vazifa.biriktirish')

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

  // FILTRLANGAN ro'yxat faqat KERAK BO'LGANDA so'raladi: filtrsiz
  // holatda guruhlangan ko'rinish yetadi va ikkinchi so'rov
  // ortiqcha bo'lardi.
  const royxatniYukla = useCallback(() => {
    if (!filtrlangan) { setRoyxat(null); return }
    api.taskList({
      broker_id: brokerId && brokerId !== ALL ? brokerId : undefined,
      kontekst: filtr.kontekst || undefined,
      status: filtr.status || undefined,
      priority: filtr.priority || undefined,
      overdue: filtr.overdue || undefined,
      q: filtr.q.trim() || undefined,
    }).then(setRoyxat).catch((e: Error) => setError(e.message))
  }, [brokerId, filtr, filtrlangan])

  useEffect(() => { royxatniYukla() }, [royxatniYukla])

  function qaytaYukla() { load(); royxatniYukla() }

  async function yarat() {
    if (!yangi?.title.trim()) return
    setBusy(true)
    try {
      await api.taskCreate({ ...yangi, title: yangi.title.trim() })
      setYangi(null)
      setError(null)
      qaytaYukla()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

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

        {/* --- FILTRLAR (§7) --- */}
        <Select value={filtr.kontekst || 'all'}
          onValueChange={(v) => setFiltr((p) => ({
            ...p, kontekst: v === 'all' ? '' : v }))}>
          <SelectTrigger className="h-9 w-auto min-w-36 bg-card text-body"
            data-testid="filtr-kontekst">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Barcha turlar</SelectItem>
            <SelectItem value="karta">Tender vazifalari</SelectItem>
            <SelectItem value="umumiy">Umumiy vazifalar</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filtr.status || 'all'}
          onValueChange={(v) => setFiltr((p) => ({
            ...p, status: v === 'all' ? '' : v }))}>
          <SelectTrigger className="h-9 w-auto min-w-32 bg-card text-body"
            data-testid="filtr-status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Barcha holat</SelectItem>
            <SelectItem value="yangi">Yangi</SelectItem>
            <SelectItem value="bajarilmoqda">Bajarilmoqda</SelectItem>
            <SelectItem value="bajarildi">Bajarildi</SelectItem>
            <SelectItem value="bekor">Bekor qilindi</SelectItem>
          </SelectContent>
        </Select>

        <button type="button" data-testid="filtr-kechikkan"
          onClick={() => setFiltr((p) => ({ ...p, overdue: !p.overdue }))}
          className={cn('h-9 rounded-md border px-3 text-caption transition-colors',
            filtr.overdue ? 'border-urgent bg-urgent-soft font-semibold text-urgent-strong'
              : 'bg-card hover:bg-accent')}>
          Kechikkan
        </button>

        <Input value={filtr.q} data-testid="filtr-qidiruv"
          onChange={(e) => setFiltr((p) => ({ ...p, q: e.target.value }))}
          placeholder="Vazifa qidirish…" className="h-9 w-48" />

        {yaratadi && (
          <Button size="sm" className="ml-auto" data-testid="vazifa-yangi"
            onClick={() => setYangi(yangi ? null : {
              title: '', assignee_broker_id: null, due_at: null,
              note: null, priority: 'medium', opportunity_id: null })}>
            <Icon name="plus" size={14} /> Yangi vazifa
          </Button>
        )}
      </div>

      {/* --- YANGI VAZIFA (§27) --- */}
      {yangi && (
        <div className="rounded-lg border bg-card p-3" data-testid="vazifa-forma">
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="sm:col-span-2">
              <span className="text-caption text-muted-foreground">Nomi</span>
              <Input value={yangi.title} data-testid="vazifa-nom"
                onChange={(e) => setYangi({ ...yangi, title: e.target.value })}
                placeholder="Masalan: sertifikatni yangilash" />
            </label>
            <label>
              <span className="text-caption text-muted-foreground">Izoh</span>
              <Input value={yangi.note || ''}
                onChange={(e) => setYangi({ ...yangi, note: e.target.value })} />
            </label>
            <label>
              <span className="text-caption text-muted-foreground">Muddat</span>
              <Input type="date" value={yangi.due_at || ''}
                data-testid="vazifa-muddat"
                onChange={(e) => setYangi({ ...yangi,
                  due_at: e.target.value || null })} />
            </label>
            <label>
              <span className="text-caption text-muted-foreground">Mas'ul</span>
              {/* BIRIKTIRISH HUQUQI YO'Q bo'lsa ro'yxat KO'RSATILMAYDI:
                  server baribir rad etardi va tanlov "buzuq" bo'lib
                  ko'rinardi (filtr bilan bir xil qoida). */}
              <Select value={String(yangi.assignee_broker_id ?? SELF)}
                onValueChange={(v) => setYangi({ ...yangi,
                  assignee_broker_id: v === SELF ? null : Number(v) })}>
                <SelectTrigger data-testid="vazifa-masul">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={SELF}>O‘zimga</SelectItem>
                  {biriktiradi && brokers.filter((b) => b.active).map((b) => (
                    <SelectItem key={b.id} value={String(b.id)}>
                      {b.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label>
              <span className="text-caption text-muted-foreground">Ustuvorlik</span>
              <Select value={yangi.priority || 'medium'}
                onValueChange={(v) => setYangi({ ...yangi, priority: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Past</SelectItem>
                  <SelectItem value="medium">O‘rta</SelectItem>
                  <SelectItem value="high">Yuqori</SelectItem>
                </SelectContent>
              </Select>
            </label>
          </div>
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setYangi(null)}>
              Bekor
            </Button>
            <Button size="sm" disabled={busy || !yangi.title.trim()}
              data-testid="vazifa-saqla" onClick={() => void yarat()}>
              Yaratish
            </Button>
          </div>
        </div>
      )}

      {error && <ErpError msg={error} />}
      {!data && !error && <Skeleton className="h-64 w-full rounded-lg" />}

      {/* FILTR YOQILGANDA guruhlangan ko'rinish o'rniga tekis
          ro'yxat: "kechikkan/bugun/keyingi" filtr ostida ma'nosini
          yo'qotadi (masalan "bajarilgan" da hammasi "keyingi" ga
          tushib qolardi). */}
      {filtrlangan ? (
        <div className="space-y-2" data-testid="filtrlangan-royxat">
          {royxat === null && <Skeleton className="h-40 w-full rounded-lg" />}
          {royxat?.length === 0 && (
            <div className="rounded-lg border bg-card px-4 py-8 text-center text-body text-muted-foreground">
              Bu filtrga mos vazifa yo'q.
            </div>
          )}
          {!!royxat?.length && (
            <Group title={`Topildi: ${royxat.length}`} items={royxat}
              onOpen={onOpenOpportunity} onChanged={qaytaYukla} />
          )}
        </div>
      ) : data && (
        <div className="space-y-4">
          <Group title="Kechikkan" tone="urgent" items={data.overdue}
            onOpen={onOpenOpportunity} onChanged={qaytaYukla} />
          <Group title="Bugun" tone="soon" items={data.today}
            onOpen={onOpenOpportunity} onChanged={qaytaYukla} />
          <Group title="Keyingi" items={data.later}
            onOpen={onOpenOpportunity} onChanged={qaytaYukla} />

          {data.total === 0 && (
            <div className="rounded-lg border bg-card px-4 py-8 text-center text-body text-muted-foreground">
              Vazifa yo'q. Yangisini "Yangi vazifa" tugmasi bilan yoki
              karta ichidan qo'shishingiz mumkin.
            </div>
          )}
        </div>
      )}

      {/* --- YUKLAMA (§8, §21) --- */}
      {can('vazifa.yuklama') && (
        <section className="rounded-lg border bg-card">
          <button type="button" data-testid="yuklama-och"
            className="flex w-full items-center gap-2 px-4 py-2 text-left text-caption font-semibold"
            onClick={() => {
              if (yuklama) { setYuklama(null); return }
              api.workload().then(setYuklama)
                .catch((e: Error) => setError(e.message))
            }}>
            <Icon name="stats" size={14} />
            Hodimlar yuklamasi
          </button>
          {yuklama && (
            <div className="overflow-x-auto">
              <table className="w-full text-body">
                <thead className="text-caption text-muted-foreground">
                  <tr className="border-t">
                    <th className="px-4 py-1.5 text-left">Hodim</th>
                    <th className="px-2 py-1.5 text-right">Ochiq ish</th>
                    <th className="px-2 py-1.5 text-right">Kechikkan</th>
                    <th className="px-2 py-1.5 text-right">Ochiq tender</th>
                    <th className="px-4 py-1.5 text-right">Bajarilgan</th>
                  </tr>
                </thead>
                <tbody>
                  {yuklama.map((y) => (
                    <tr key={y.broker_id} className="border-t"
                      data-testid={`yuklama-${y.broker_id}`}>
                      <td className="px-4 py-1.5">{y.full_name}</td>
                      <td className="tabular px-2 py-1.5 text-right">
                        {y.ochiq_vazifa}
                      </td>
                      <td className={cn('tabular px-2 py-1.5 text-right',
                        y.kechikkan > 0 && 'font-semibold text-urgent-strong')}>
                        {y.kechikkan}
                      </td>
                      <td className="tabular px-2 py-1.5 text-right">
                        {y.ochiq_karta}
                      </td>
                      <td className="tabular px-4 py-1.5 text-right text-muted-foreground">
                        {y.bajarilgan}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {/* Bu BAHO EMAS — ochiq aytiladi, aks holda raqamlar
                  "kim yaxshi ishlayapti" degan xulosaga aylanardi. */}
              <p className="px-4 py-2 text-micro text-muted-foreground">
                Bu ish taqsimlash uchun — baho emas.
              </p>
            </div>
          )}
        </section>
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
          // UMUMIY vazifada tender muddati yo'q — `null` beriladi.
          const d = f.deadline(t.opportunity?.deadline_at ?? null)
          return (
            <li key={t.id} data-testid={`task-${t.id}`}
              className="flex flex-wrap items-baseline gap-2 px-4 py-2 text-body">
              {/* BAJARILDI — shu yerdan: kartani ochish shart emas.
                  Yakunlangan vazifada belgi TURADI va uni yechish
                  qayta ochadi (§9): xato bosilgan "bajarildi" ni
                  tuzatib bo'lmasa, odam yangi vazifa yaratardi va
                  ro'yxatda ikkita bir xil qator qolardi. */}
              <input type="checkbox" checked={!t.ochiq}
                data-testid={`task-done-${t.id}`}
                title={t.ochiq ? 'Bajarildi deb belgilash' : 'Qayta ochish'}
                onChange={() => api
                  .taskStatus(t.id, t.ochiq ? 'bajarildi' : 'yangi')
                  .then(onChanged).catch(() => {})} />
              <span className={cn('font-medium',
                !t.ochiq && 'text-muted-foreground line-through')}>
                {t.title}
              </span>
              {/* USTUVORLIK faqat YUQORI bo'lganda ko'rinadi: "o'rta"
                  ni har qatorda ko'rsatish ro'yxatni shovqinga
                  aylantirardi va yuqorisi ko'zga tashlanmasdi. */}
              {t.priority === 'high' && (
                <span className="rounded bg-urgent-soft px-1.5 py-px text-micro font-semibold text-urgent-strong">
                  {t.priority_label}
                </span>
              )}
              {t.status === 'bajarilmoqda' && (
                <span className="rounded bg-secondary px-1.5 py-px text-micro text-primary">
                  {t.status_label}
                </span>
              )}
              {t.status === 'bekor' && (
                <span className="rounded bg-muted px-1.5 py-px text-micro text-muted-foreground">
                  {t.status_label}
                </span>
              )}
              {t.due_at && (
                <span className={cn('tabular text-caption',
                  t.overdue ? 'font-semibold text-urgent-strong' : 'text-muted-foreground')}>
                  {f.dateFmt(t.due_at)}
                </span>
              )}
              {t.assignee?.name && (
                <span className="text-caption text-muted-foreground">{t.assignee.name}</span>
              )}

              {/* KONTEKST OCHIQ KO'RSATILADI (§3): umumiy vazifa
                  bilan tender vazifasini ro'yxatda darhol ajratish
                  kerak, aks holda odam "bu qaysi tenderga tegishli?"
                  degan savolga javob topa olmasdi. */}
              {t.opportunity ? (
                <button type="button" data-testid={`task-opp-${t.id}`}
                  className="ml-auto max-w-[24rem] truncate text-caption text-primary hover:underline"
                  onClick={() => onOpen(t.opportunity!.id)}>
                  {t.opportunity.title || `Karta #${t.opportunity.id}`}
                </button>
              ) : (
                <span className="ml-auto rounded bg-muted px-1.5 py-px text-micro text-muted-foreground">
                  umumiy
                </span>
              )}
              {t.opportunity?.client_name && (
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
