import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat, DEADLINE_CLASS } from '@/format'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import Icon from '../Icon'
import { BarRow, Empty, GroupedBars, Legend, Panel, SERIES, Stat } from './charts'
import type {
  AuditReport, AuthUser, ErpAnalytics, ErpStats, MyTasks, Opportunity,
  ProfitReport,
} from '@/types'

// BOSHQARUV PANELI — kunni shu ekrandan boshlanadi.
//
// TARTIB — SAVOLLAR BO'YICHA, modullar bo'yicha emas:
//
//   1. "Bugun nima qilishim kerak?"   -> mening ishlarim, muddatlar
//   2. "Ishlar qanday ketyapti?"      -> voronka, oylik natija
//   3. "Pul qayerda?"                 -> foyda, qarzdorlik
//   4. "E'tibor talab qiladigan bormi?" -> qotib qolganlar, audit
//
// Modul bo'yicha terilgan panel ("Ombor", "Fakturalar", ...) menyuning
// takroriga aylanadi va hech qanday savolga javob bermaydi.
//
// HAR KIM O'ZINIKINI KO'RADI — va bu ikki BOSHQA panel.
//
// Kompaniya bo'yicha ko'rsatkich (`/erp/stats`, `/erp/analytics`,
// `/erp/profit`, `/erp/audit`) `manager` huquqini talab qiladi va
// brokerda 403 qaytaradi. Shuning uchun brokerga xato ham, bo'sh quti
// ham ko'rsatilmaydi: unga O'Z ishlari va O'Z kartalari chiqadi.
//
// 403 ni XATO deb ko'rsatish eng yomon yechim bo'lardi — broker har
// kuni ochadigan ekranda "ruxsat yo'q" yozuvi turgan bo'lardi.

interface Props {
  user: AuthUser
  onOpenOpportunity: (id: number) => void
  onGo: (view: string) => void
}

export default function Dashboard({ user, onOpenOpportunity, onGo }: Props) {
  const f = useFormat()
  const isManager = user.role === 'manager' || user.role === 'admin'

  const [stats, setStats] = useState<ErpStats | null>(null)
  const [an, setAn] = useState<ErpAnalytics | null>(null)
  const [tasks, setTasks] = useState<MyTasks | null>(null)
  const [profit, setProfit] = useState<ProfitReport | null>(null)
  const [inv, setInv] = useState<{ count: number; debt: number } | null>(null)
  const [audit, setAudit] = useState<AuditReport | null>(null)
  const [mine, setMine] = useState<Opportunity[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Kompaniya ko'rsatkichlari yopiq (403) — bu XATO EMAS, bu ROL.
  const [denied, setDenied] = useState(false)

  useEffect(() => {
    // Har so'rov MUSTAQIL: bittasi yiqilsa qolgan bloklar ko'rinadi.
    // Umumiy `Promise.all` bo'lsa, ombor patchi yo'qligi butun panelni
    // o'chirib qo'yardi.
    api.myTasks({ days: 7 }).then(setTasks).catch(() => setTasks(null))

    if (isManager) {
      api.stats({ days: 7 }).then(setStats)
        .catch((e: Error) => setError(e.message))
      api.analytics({ stuck_days: 14 }).then(setAn).catch(() => setAn(null))
      api.invoiceStats().then(setInv).catch(() => setInv(null))
      api.profit({ limit: 200 }).then(setProfit).catch(() => setProfit(null))
      api.audit({ days: 30, limit: 5 }).then(setAudit).catch(() => setAudit(null))
    } else {
      // Broker ko'rinishi: O'Z ochiq kartalari. `broker_id` bo'lmasa
      // (hisob hodimga bog'lanmagan) ro'yxat bo'sh qoladi va buni
      // ekranning o'zi aytadi.
      setDenied(true)
      if (user.broker_id) {
        api.opportunities({ broker_id: user.broker_id, open_only: true })
          .then(setMine).catch(() => setMine([]))
      } else {
        setMine([])
      }
    }
  }, [isManager, user.broker_id])

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-body text-destructive">
        {error}
      </div>
    )
  }
  // --- BROKER KO'RINISHI ---
  if (denied) {
    return <MineView user={user} tasks={tasks} mine={mine}
      onOpenOpportunity={onOpenOpportunity} onGo={onGo} />
  }

  if (!stats) return <Skeleton className="h-96 w-full rounded-lg" />

  const cur = stats.currency
  const money = (v: number | null) =>
    (v == null || cur == null ? '—' : f.shortMoney(v, cur))

  // Foyda: bitta valyutada umumiy yig'indi, aralashda — yo'q
  // (`erp_foyda.md` 9). Panelda yolg'on son ko'rsatmaymiz.
  const pt = profit?.totals || null

  const overdue = tasks?.overdue.length || 0
  const today = tasks?.today.length || 0
  const stuck = an?.stuck.length || 0

  return (
    <div className="space-y-4">
      {/* ---------------------------------------------------------------
          1. E'TIBOR TALAB QILADIGANLARI — eng tepada va faqat BOR bo'lsa.
          Doim turadigan "hammasi joyida" qatori e'tiborni o'ldiradi.
          --------------------------------------------------------------- */}
      {(overdue > 0 || stuck > 0 || (audit && !audit.clean)) && (
        <div className="flex flex-wrap gap-2">
          {overdue > 0 && (
            <Flag tone="urgent" icon="alert"
              text={`${overdue} ta vazifa muddati o'tgan`}
              onClick={() => onGo('mytasks')} />
          )}
          {stuck > 0 && (
            <Flag tone="soon" icon="alert"
              text={`${stuck} ta karta ${an!.stuck_days} kundan beri qimirlamagan`}
              onClick={() => onGo('opportunities')} />
          )}
          {audit && !audit.clean && (
            <Flag tone="urgent" icon="alert"
              text={audit.summary.outside_erp > 0
                ? `${audit.summary.outside_erp} ta o'zgarish ERP dan tashqarida`
                : `${audit.summary.after_issue} ta o'zgarish chiqarilgan hujjatda`}
              onClick={() => onGo('opportunities')} />
          )}
        </div>
      )}

      {/* ---------------------------------------------------------------
          2. RAQAMLAR QATORI — grafik EMAS.
          Bitta son uchun grafik chizish uni o'qishni qiyinlashtiradi.
          --------------------------------------------------------------- */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
        <Stat label="Ishda" value={stats.open}
          hint={money(stats.open_total)}
          onClick={() => onGo('opportunities')} />
        <Stat label="Topshirilgan" value={stats.submitted} />
        <Stat label="Yutilgan" value={stats.won} tone="ok"
          hint={money(stats.won_total)} />
        <Stat label="Yutish foizi"
          value={stats.win_rate == null ? '—' : `${stats.win_rate}%`}
          hint={stats.win_rate == null ? "hal bo'lgani yo'q"
            : 'yutilgan / hal bo\'lgan'} />
        {isManager && (
          <Stat label="Foyda"
            value={pt ? f.shortMoney(pt.profit, pt.currency) : '—'}
            tone={pt && pt.profit > 0 ? 'ok' : undefined}
            hint={profit?.mixed_currency ? 'valyutalar aralash'
              : pt?.margin != null ? `${pt.margin}%` : 'daromad yo\'q'} />
        )}
        <Stat label="Qarzdorlik"
          value={inv ? f.shortMoney(inv.debt, cur || 'UZS') : '—'}
          tone={inv && inv.debt > 0 ? 'soon' : undefined}
          hint={inv ? `${inv.count} ta faktura` : undefined}
          onClick={() => onGo('invoices')} />
      </div>

      {stats.mixed_currency && (
        <p className="text-caption text-muted-foreground">
          Kartalar {stats.currencies.join(', ')} valyutalarida — pul
          yig'indilari ko'rsatilmaydi. Kurs bo'yicha qo'shish qaysi kungi
          kurs ekaniga bog'liq bo'lardi; sanoq esa to'g'ri qoladi.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* -------------------------------------------------------------
            3. BUGUN — "nima qilishim kerak?"
            ------------------------------------------------------------- */}
        <Panel title="Bugun"
          hint={tasks ? `${overdue} ta kechikkan, ${today} ta bugungi`
            : undefined}
          action={
            <button type="button" onClick={() => onGo('mytasks')}
              className="text-caption text-primary hover:underline">
              hammasi
            </button>
          }>
          {!tasks || (overdue + today === 0) ? (
            <Empty msg="Bugunga vazifa yo'q."
              hint="Kartalardagi vazifalar shu yerga tushadi." />
          ) : (
            <ul className="divide-y">
              {[...tasks.overdue, ...tasks.today].slice(0, 6).map((t) => (
                <li key={t.id}>
                  <button type="button"
                    onClick={() => onOpenOpportunity(t.opportunity_id)}
                    className="flex w-full items-baseline gap-2 py-1.5 text-left text-body hover:bg-muted">
                    <span className="min-w-0 flex-1 truncate">{t.title}</span>
                    <span className="truncate text-caption text-muted-foreground">
                      {t.opportunity.title || `#${t.opportunity_id}`}
                    </span>
                    {t.due_at && (
                      <span className={cn('shrink-0 rounded px-1.5 py-px text-micro font-semibold',
                        DEADLINE_CLASS[f.deadline(t.due_at)?.level || 'none'])}>
                        {f.deadline(t.due_at)?.text}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* -------------------------------------------------------------
            4. YAQIN MUDDATLAR — kartalar bo'yicha
            ------------------------------------------------------------- */}
        <Panel title="Yaqin muddatlar"
          hint={`Keyingi ${stats.upcoming_days} kun · muddati o'tganlari tepada`}>
          {stats.upcoming.length === 0 ? (
            <Empty msg="Yaqin muddat yo'q." />
          ) : (
            <ul className="divide-y">
              {stats.upcoming.slice(0, 6).map((u) => {
                const d = u.deadline_at ? f.deadline(u.deadline_at) : null
                return (
                  <li key={u.id}>
                    <button type="button" onClick={() => onOpenOpportunity(u.id)}
                      className="flex w-full items-baseline gap-2 py-1.5 text-left text-body hover:bg-muted">
                      <span className="min-w-0 flex-1 truncate">
                        {u.title || `#${u.id}`}
                      </span>
                      <span className="truncate text-caption text-muted-foreground">
                        {u.broker_name || '—'}
                      </span>
                      {d && (
                        <span className={cn('shrink-0 rounded px-1.5 py-px text-micro font-semibold',
                          DEADLINE_CLASS[d.level])}>
                          {d.text}
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>

        {/* -------------------------------------------------------------
            5. VORONKA — MIQDOR, shuning uchun gorizontal ustun.
            Bosqichlar nomi uzun; gorizontal ustunda ular burilmasdan
            o'qiladi.
            ------------------------------------------------------------- */}
        <Panel title="Bosqichlar bo'yicha"
          hint="Hozirgi holat — nechta karta qaysi bosqichda">
          {stats.by_status.every((s) => s.n === 0) ? (
            <Empty msg="Hali karta yo'q."
              hint="Tender panelidan 'ERP da ishga olish' bilan boshlanadi." />
          ) : (
            <div className="space-y-1">
              {stats.by_status.map((s) => (
                <BarRow key={s.code} label={s.label} value={s.n}
                  max={Math.max(1, ...stats.by_status.map((x) => x.n))}
                  hint={s.total ? money(s.total) : ''}
                  tone={s.code === 'won' ? 'ok'
                    : s.code === 'lost' || s.code === 'rejected' ? 'muted'
                      : 'primary'} />
              ))}
            </div>
          )}
        </Panel>

        {/* -------------------------------------------------------------
            6. OYLIK NATIJA — vaqt bo'yicha o'zgarish.
            ------------------------------------------------------------- */}
        <Panel title="Oylik natija"
          hint="Yopilgan kartalar — qaysi oyda nima bilan tugadi">
          {stats.monthly.length === 0 ? (
            <Empty msg="Yopilgan karta yo'q." />
          ) : (
            <>
              <Legend series={MONTHLY_SERIES} />
              <div className="mt-2">
                <GroupedBars
                  series={MONTHLY_SERIES}
                  groups={[...stats.monthly].reverse().map((m) => ({
                    label: m.month.slice(2).replace('-', '/'),
                    values: [m.won, m.lost, m.rejected],
                  }))} />
              </div>
            </>
          )}
        </Panel>
      </div>

      {/* -----------------------------------------------------------------
          7. VORONKA (tahlil) — "qayerda yo'qotamiz?"
          Bu bosqichdagi HOZIRGI holat emas, TARIXI: har bosqichga nechta
          karta yetib borgan.
          ----------------------------------------------------------------- */}
      {an && an.funnel.length > 0 && (
        <Panel title="Voronka"
          hint="Har bosqichga YETIB BORGAN kartalar — hozirgi holati emas, tarixi">
          <div className="space-y-1">
            {an.funnel.map((s) => (
              <BarRow key={s.code} label={s.label || s.code} value={s.reached}
                max={Math.max(1, ...an.funnel.map((x) => x.reached))}
                hint={s.pct == null ? '' : `${s.pct}%`} />
            ))}
          </div>
        </Panel>
      )}

      {/* -----------------------------------------------------------------
          8. FOYDA — faqat rahbarga va faqat pul harakati bo'lsa.
          ----------------------------------------------------------------- */}
      {isManager && profit && profit.by_currency.length > 0 && (
        <Panel title="Foyda"
          hint="Daromad QQS SIZ · tannarx harakat paytida muzlatilgan"
          action={
            <button type="button" onClick={() => onGo('invoices')}
              className="text-caption text-primary hover:underline">
              fakturalar
            </button>
          }>
          <div className="space-y-1.5">
            {profit.by_currency.map((c) => (
              <div key={c.currency}
                className="flex flex-wrap items-baseline gap-x-5 gap-y-1 text-body">
                {profit.mixed_currency && (
                  <span className="w-10 shrink-0 font-semibold">{c.currency}</span>
                )}
                <Money label="Daromad" v={f.shortMoney(c.revenue, c.currency)} />
                <Money label="Tannarx" v={f.shortMoney(c.cost, c.currency)} />
                <Money label="Foyda" v={f.shortMoney(c.profit, c.currency)}
                  cls={c.profit > 0 ? 'text-ok-strong'
                    : c.profit < 0 ? 'text-urgent-strong' : ''}
                  extra={c.margin != null ? `${c.margin}%` : undefined} />
                <span className="text-caption text-muted-foreground">
                  {c.cards} ta karta
                </span>
              </div>
            ))}
          </div>
          {!profit.complete && (
            <p className="mt-2 text-caption text-soon-strong">
              Hisob to'liq emas: {profit.unknown_cost_moves} ta chiqimning
              tannarxi noma'lum. Ular tannarxga qo'shilmadi — haqiqiy foyda
              bundan kam.
            </p>
          )}
        </Panel>
      )}
    </div>
  )
}

/** BROKER PANELI — kompaniya ko'rsatkichlarisiz.
 *
 *  Bu qisqartirilgan nusxa emas, BOSHQA savolga javob: "bugun menda
 *  nima bor?". Shuning uchun bu yerda voronka ham, foyda ham yo'q —
 *  ular brokerning ishiga tegishli emas. */
function MineView({ user, tasks, mine, onOpenOpportunity, onGo }: {
  user: AuthUser
  tasks: MyTasks | null
  mine: Opportunity[] | null
  onOpenOpportunity: (id: number) => void
  onGo: (view: string) => void
}) {
  const f = useFormat()
  if (!tasks && !mine) return <Skeleton className="h-96 w-full rounded-lg" />

  const overdue = tasks?.overdue.length || 0
  const today = tasks?.today.length || 0
  const later = tasks?.later.length || 0
  // Muddati bor kartalar — eng yaqini tepada. Muddat SNAPSHOT ichida:
  // u tenderdan ko'chirilgan va keyin manba o'zgarsa ham o'zgarmaydi.
  const soon = (mine || [])
    .filter((o) => o.tender?.deadline_at)
    .sort((a, b) => String(a.tender.deadline_at)
      .localeCompare(String(b.tender.deadline_at)))

  return (
    <div className="space-y-4">
      {overdue > 0 && (
        <div className="flex flex-wrap gap-2">
          <Flag tone="urgent" icon="alert"
            text={`${overdue} ta vazifa muddati o'tgan`}
            onClick={() => onGo('mytasks')} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Ochiq kartalarim" value={mine?.length ?? '—'}
          onClick={() => onGo('opportunities')} />
        <Stat label="Bugungi vazifa" value={today} />
        <Stat label="Kechikkan" value={overdue}
          tone={overdue ? 'urgent' : undefined}
          onClick={() => onGo('mytasks')} />
        <Stat label="Keyingi kunlarda" value={later} />
      </div>

      {!user.broker_id && (
        <p className="text-caption text-soon-strong">
          Hisobingiz hodimga bog'lanmagan — shuning uchun "mening
          kartalarim" bo'sh. Administratordan hisobni hodimga bog'lashni
          so'rang.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Bugun"
          hint={`${overdue} ta kechikkan, ${today} ta bugungi`}
          action={
            <button type="button" onClick={() => onGo('mytasks')}
              className="text-caption text-primary hover:underline">
              hammasi
            </button>
          }>
          {overdue + today === 0 ? (
            <Empty msg="Bugunga vazifa yo'q."
              hint="Kartalardagi vazifalar shu yerga tushadi." />
          ) : (
            <ul className="divide-y">
              {[...(tasks?.overdue || []), ...(tasks?.today || [])]
                .slice(0, 8).map((t) => (
                  <li key={t.id}>
                    <button type="button"
                      onClick={() => onOpenOpportunity(t.opportunity_id)}
                      className="flex w-full items-baseline gap-2 py-1.5 text-left text-body hover:bg-muted">
                      <span className="min-w-0 flex-1 truncate">{t.title}</span>
                      {t.due_at && (
                        <span className={cn('shrink-0 rounded px-1.5 py-px text-micro font-semibold',
                          DEADLINE_CLASS[f.deadline(t.due_at)?.level || 'none'])}>
                          {f.deadline(t.due_at)?.text}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
            </ul>
          )}
        </Panel>

        <Panel title="Mening kartalarim"
          hint="Ochiq kartalar — muddati yaqinlari tepada">
          {soon.length === 0 ? (
            <Empty msg="Ochiq karta yo'q."
              hint="Tender panelidan 'ERP da ishga olish' bilan boshlanadi." />
          ) : (
            <ul className="divide-y">
              {soon.slice(0, 8).map((o) => {
                const d = o.tender?.deadline_at
                  ? f.deadline(o.tender.deadline_at) : null
                return (
                  <li key={o.id}>
                    <button type="button" onClick={() => onOpenOpportunity(o.id)}
                      className="flex w-full items-baseline gap-2 py-1.5 text-left text-body hover:bg-muted">
                      <span className="min-w-0 flex-1 truncate">
                        {o.tender?.title || `#${o.id}`}
                      </span>
                      <span className="truncate text-caption text-muted-foreground">
                        {o.status_label || o.status}
                      </span>
                      {d && (
                        <span className={cn('shrink-0 rounded px-1.5 py-px text-micro font-semibold',
                          DEADLINE_CLASS[d.level])}>
                          {d.text}
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}

const MONTHLY_SERIES = [
  { label: 'Yutilgan', color: SERIES[3] },
  { label: 'Yutqazilgan', color: SERIES[1] },
  { label: 'Rad etilgan', color: SERIES[2] },
]

function Money({ label, v, cls, extra }: {
  label: string; v: string; cls?: string; extra?: string
}) {
  return (
    <span>
      <span className="text-muted-foreground">{label} </span>
      <span className={cn('tabular font-semibold', cls)}>{v}</span>
      {extra && <span className="text-muted-foreground"> ({extra})</span>}
    </span>
  )
}

/** Diqqat bayrog'i — MATN bilan, faqat rang bilan emas. */
function Flag({ tone, icon, text, onClick }: {
  tone: 'urgent' | 'soon'
  icon: string
  text: string
  onClick: () => void
}) {
  return (
    <button type="button" onClick={onClick}
      className={cn('flex items-center gap-2 rounded-md border px-3 py-1.5 text-caption font-medium transition-colors',
        tone === 'urgent'
          ? 'border-urgent/40 bg-urgent-soft text-urgent-strong hover:border-urgent'
          : 'border-soon/40 bg-soon-soft text-soon-strong hover:border-soon')}>
      <Icon name={icon} size={14} />
      {text}
      <Icon name="right" size={13} />
    </button>
  )
}
