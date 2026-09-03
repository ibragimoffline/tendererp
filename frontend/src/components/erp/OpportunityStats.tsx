import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat, DEADLINE_CLASS } from '@/format'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { ErpAnalytics, ErpStats } from '@/types'
import { ErpError } from './erpShared'
import ProfitPanel from './ProfitPanel'
import AuditPanel from './AuditPanel'

// RAHBAR PANELI — "kim nima ustida ishlayapti va natija qanday" degan savolga
// bir ekranda javob. Barcha hisob BAZADA (GROUP BY), bu yerda faqat ko'rinish.
//
// Grafik kutubxonasi ishlatilmaydi: kerak bo'lgani — nisbatni ko'rsatuvchi
// gorizontal chiziq, u CSS kengligi bilan chiziladi.
//
// ARALASH VALYUTA: kartalar bir nechta valyutada bo'lsa server pul
// yig'indilarini `null` qaytaradi (`mixed_currency`). Bu yerda o'sha
// joyga son EMAS, sabab yoziladi. Nol ko'rsatish yolg'on bo'lardi,
// qo'shib yuborish esa undan ham yomon: "1200 USD + 15 mln UZS" degan
// son hech narsani anglatmaydi.

export default function OpportunityStats({ onOpen }: { onOpen: (id: number) => void }) {
  const f = useFormat()
  const [d, setD] = useState<ErpStats | null>(null)
  const [an, setAn] = useState<ErpAnalytics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.stats({ days: 7 }).then(setD).catch((e: Error) => setError(e.message))
    // Tahlil alohida so'rov: u og'irroq (window funksiyalar) va yig'ma
    // raqamlar undan oldin ko'rinishi kerak.
    api.analytics({ stuck_days: 14 }).then(setAn).catch(() => setAn(null))
  }, [])

  if (error) return <ErpError msg={error} />
  if (!d) return <Skeleton className="h-64 w-full rounded-lg" />

  const max = Math.max(1, ...d.by_status.map((s) => s.n))
  // Pul yig'indisi ko'rsatiladigan valyuta; aralash bo'lsa `null`.
  const cur = d.currency
  /** Pul yoki bo'shliq — aralash valyutada son CHIQARILMAYDI. */
  const money = (v: number | null) =>
    (v == null || cur == null ? '' : f.shortMoney(v, cur))

  return (
    <div className="space-y-5">
      {/* --- Raqamlar qatori --- */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Jami" value={d.total} />
        <Kpi label="Ishda" value={d.open} hint={money(d.open_total)} />
        <Kpi label="Topshirilgan" value={d.submitted} />
        <Kpi label="Yutilgan" value={d.won} hint={money(d.won_total)}
          cls="text-ok-strong" />
        <Kpi label="Yutqazilgan" value={d.lost} cls="text-urgent-strong" />
        <Kpi label="Yutish foizi"
          value={d.win_rate == null ? '—' : `${d.win_rate}%`}
          hint={d.win_rate == null ? 'hal bo\'lgani yo\'q' : 'yutilgan / hal bo\'lgan'} />
      </div>

      {/* --- Status bo'yicha --- */}
      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-3 text-caption font-semibold text-muted-foreground">
          Bosqichlar bo'yicha
        </h3>
        <div className="space-y-1.5">
          {d.by_status.map((s) => (
            <div key={s.code} className="flex items-center gap-3 text-body">
              <span className="w-44 shrink-0 truncate">{s.label}</span>
              <div className="h-2.5 flex-1 rounded bg-muted">
                <div className="h-full rounded bg-primary"
                  style={{ width: `${(s.n / max) * 100}%` }} />
              </div>
              <span className="tabular w-8 text-right">{s.n}</span>
              <span className="tabular w-28 text-right text-caption text-muted-foreground">
                {s.total ? money(s.total) : ''}
              </span>
            </div>
          ))}
        </div>
      </section>

      {d.mixed_currency && (
        <p className="text-caption text-muted-foreground">
          Kartalar {d.currencies.join(', ')} valyutalarida — pul
          yig'indilari ko'rsatilmaydi, sanoq esa to'g'ri qoladi.
        </p>
      )}

      {/* --- Foyda: "qaysi tender qancha pul olib keldi" --- */}
      <ProfitPanel onOpen={onOpen} />

      {/* --- "Kim, qachon va nimani o'zgartirdi" --- */}
      <AuditPanel />

      {/* --- Yaqin deadline'lar --- */}
      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-3 text-caption font-semibold text-muted-foreground">
          {d.upcoming_days} kun ichidagi deadline'lar
        </h3>
        {d.upcoming.length === 0 ? (
          <div className="text-body text-muted-foreground">Yaqin muddatli karta yo'q.</div>
        ) : (
          <ul className="space-y-1.5">
            {d.upcoming.map((u) => {
              const dl = f.deadline(u.deadline_at)
              return (
                <li key={u.id}>
                  <button type="button" onClick={() => onOpen(u.id)}
                    className="flex w-full flex-wrap items-baseline gap-2 rounded-md px-2 py-1 text-left text-body hover:bg-accent">
                    {dl && (
                      <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
                        DEADLINE_CLASS[dl.level])}>{dl.text}</span>
                    )}
                    <span className="line-clamp-1 flex-1 font-medium">{u.title || `#${u.id}`}</span>
                    <span className="text-caption text-muted-foreground">
                      {u.broker_name || '—'}{u.client_name ? ` · ${u.client_name}` : ''}
                    </span>
                    <span className="tabular text-caption">
                      {f.shortMoney(u.start_price, u.currency)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* --- Broker kesimi --- */}
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-caption font-semibold text-muted-foreground">Brokerlar</h3>
          <table className="w-full text-body">
            <thead>
              <tr className="text-caption text-muted-foreground">
                <th className="text-left font-medium">Mas'ul</th>
                <th className="text-right font-medium">Jami</th>
                <th className="text-right font-medium">Ishda</th>
                <th className="text-right font-medium">Yutdi</th>
                <th className="text-right font-medium">Yutqazdi</th>
              </tr>
            </thead>
            <tbody>
              {d.by_broker.map((b) => (
                <tr key={b.id} className="border-t">
                  <td className="py-1">{b.full_name}</td>
                  <td className="tabular py-1 text-right">{b.n}</td>
                  <td className="tabular py-1 text-right">{b.open_n}</td>
                  <td className="tabular py-1 text-right text-ok-strong">{b.won_n}</td>
                  <td className="tabular py-1 text-right">{b.lost_n}</td>
                </tr>
              ))}
              {d.by_broker.length === 0 && (
                <tr><td colSpan={5} className="py-3 text-center text-muted-foreground">
                  Broker qo'shilmagan.
                </td></tr>
              )}
            </tbody>
          </table>
        </section>

        {/* --- Mijoz kesimi --- */}
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-caption font-semibold text-muted-foreground">Mijozlar</h3>
          <table className="w-full text-body">
            <thead>
              <tr className="text-caption text-muted-foreground">
                <th className="text-left font-medium">Korxona</th>
                <th className="text-right font-medium">Kartalar</th>
                <th className="text-right font-medium">Yutdi</th>
                <th className="text-right font-medium">Yutilgan summa</th>
              </tr>
            </thead>
            <tbody>
              {d.by_client.map((c) => (
                <tr key={c.id} className="border-t">
                  <td className="py-1">{c.name}</td>
                  <td className="tabular py-1 text-right">{c.n}</td>
                  <td className="tabular py-1 text-right text-ok-strong">{c.won_n}</td>
                  <td className="tabular py-1 text-right">
                    {c.won_total ? money(c.won_total) || '—' : '—'}
                  </td>
                </tr>
              ))}
              {d.by_client.length === 0 && (
                <tr><td colSpan={4} className="py-3 text-center text-muted-foreground">
                  Mijoz qo'shilmagan.
                </td></tr>
              )}
            </tbody>
          </table>
        </section>
      </div>

      {/* --- BOSQICHDA O'TGAN VAQT --- */}
      {an && (
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-1 text-caption font-semibold text-muted-foreground">
            Bosqichda o'tgan vaqt
          </h3>
          <p className="mb-3 text-micro text-muted-foreground">
            O'rtacha — faqat tugagan turishlar bo'yicha.
          </p>
          <table className="w-full text-body">
            <thead>
              <tr className="text-caption text-muted-foreground">
                <th className="text-left font-medium">Bosqich</th>
                <th className="text-right font-medium">O'rtacha</th>
                <th className="text-right font-medium">Mediana</th>
                <th className="text-right font-medium">Eng uzun</th>
                <th className="text-right font-medium">Hozir turibdi</th>
              </tr>
            </thead>
            <tbody>
              {an.stages.filter((x) => x.finished_n || x.ongoing_n).map((x) => (
                <tr key={x.code} className="border-t">
                  <td className="py-1">{x.label || x.code}</td>
                  <td className="tabular py-1 text-right">
                    {x.avg_days == null ? '—' : `${x.avg_days} kun`}
                  </td>
                  <td className="tabular py-1 text-right text-muted-foreground">
                    {x.median_days == null ? '—' : x.median_days}
                  </td>
                  <td className="tabular py-1 text-right text-muted-foreground">
                    {x.max_days == null ? '—' : x.max_days}
                  </td>
                  <td className="tabular py-1 text-right">
                    {x.ongoing_n || '—'}
                    {x.oldest_days != null && x.ongoing_n > 0 && (
                      <span className="ml-1 text-micro text-muted-foreground">
                        ({x.oldest_days} kun)
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* --- VORONKA --- */}
      {an && an.funnel.some((x) => x.reached > 0) && (
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-1 text-caption font-semibold text-muted-foreground">
            Voronka
          </h3>
          <p className="mb-3 text-micro text-muted-foreground">
            Necha karta shu bosqichga yetib borgan (hozirgi holati emas). Foiz —
            ishga olinganlardan.
          </p>
          <div className="space-y-1.5">
            {an.funnel.filter((x) => x.reached > 0).map((x) => (
              <div key={x.code} className="flex items-center gap-3 text-body">
                <span className="w-44 shrink-0 truncate">{x.label || x.code}</span>
                <div className="h-2.5 flex-1 rounded bg-muted">
                  <div className="h-full rounded bg-primary"
                    style={{ width: `${x.pct ?? 0}%` }} />
                </div>
                <span className="tabular w-8 text-right">{x.reached}</span>
                <span className="tabular w-12 text-right text-caption text-muted-foreground">
                  {x.pct == null ? '' : `${x.pct}%`}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* --- QOTIB QOLGANLAR --- */}
      {an && (
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-caption font-semibold text-muted-foreground">
            {an.stuck_days} kundan beri qimirlamagan kartalar
          </h3>
          {an.stuck.length === 0 ? (
            <div className="text-body text-muted-foreground">
              Qotib qolgan karta yo'q.
            </div>
          ) : (
            <ul className="space-y-1">
              {an.stuck.map((x) => (
                <li key={x.id}>
                  <button type="button" onClick={() => onOpen(x.id)}
                    className="flex w-full flex-wrap items-baseline gap-2 rounded-md px-2 py-1 text-left text-body hover:bg-accent">
                    <span className="tabular rounded bg-soon-soft px-1.5 py-px text-micro font-semibold text-soon-strong">
                      {x.idle_days} kun
                    </span>
                    <span className="line-clamp-1 flex-1 font-medium">
                      {x.title || `#${x.id}`}
                    </span>
                    <span className="text-caption text-muted-foreground">
                      {x.status_label || x.status}
                    </span>
                    <span className="text-caption text-muted-foreground">
                      {x.broker_name || '—'}
                    </span>
                    {x.open_tasks > 0 && (
                      <span className="text-micro text-muted-foreground">
                        {x.open_tasks} ochiq vazifa
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* --- BROKER SIKLI va YUTQAZISH SABABLARI --- */}
      {an && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-lg border bg-card p-4">
            <h3 className="mb-1 text-caption font-semibold text-muted-foreground">
              Ishga olishdan topshirishgacha
            </h3>
            <p className="mb-3 text-micro text-muted-foreground">
              Jarayonni o'lchaydi: qayerda sekinlashuv borligini ko'rsatadi.
            </p>
            <table className="w-full text-body">
              <thead>
                <tr className="text-caption text-muted-foreground">
                  <th className="text-left font-medium">Mas'ul</th>
                  <th className="text-right font-medium">Kartalar</th>
                  <th className="text-right font-medium">Topshirdi</th>
                  <th className="text-right font-medium">O'rtacha</th>
                </tr>
              </thead>
              <tbody>
                {an.by_broker.map((b) => (
                  <tr key={b.id} className="border-t">
                    <td className="py-1">{b.full_name}</td>
                    <td className="tabular py-1 text-right">{b.n}</td>
                    <td className="tabular py-1 text-right">{b.submitted_n}</td>
                    <td className="tabular py-1 text-right">
                      {b.avg_to_submit == null ? '—' : `${b.avg_to_submit} kun`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="rounded-lg border bg-card p-4">
            <h3 className="mb-3 text-caption font-semibold text-muted-foreground">
              Yutqazish sabablari
            </h3>
            {an.lost_reasons.length === 0 ? (
              <div className="text-body text-muted-foreground">
                Yutqazilgan karta yo'q.
              </div>
            ) : (
              <ul className="space-y-1">
                {an.lost_reasons.map((r) => (
                  <li key={r.code} className="flex items-baseline gap-2 text-body">
                    <span className="flex-1">{r.code}</span>
                    <span className="tabular">{r.n}</span>
                    <span className="tabular text-caption text-muted-foreground">
                      {r.total ? money(r.total) : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {/* --- Oylik natija --- */}
      {d.monthly.length > 0 && (
        <section className="rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-caption font-semibold text-muted-foreground">
            Oylar bo'yicha yakun
          </h3>
          <div className="space-y-1.5">
            {d.monthly.map((m) => {
              const tot = Math.max(1, m.won + m.lost + m.rejected)
              return (
                <div key={m.month} className="flex items-center gap-3 text-body">
                  <span className="tabular w-20 shrink-0">{m.month}</span>
                  <div className="flex h-2.5 flex-1 overflow-hidden rounded bg-muted">
                    <div className="h-full bg-ok" style={{ width: `${(m.won / tot) * 100}%` }} />
                    <div className="h-full bg-urgent" style={{ width: `${(m.lost / tot) * 100}%` }} />
                    <div className="h-full bg-muted-foreground/40"
                      style={{ width: `${(m.rejected / tot) * 100}%` }} />
                  </div>
                  <span className="tabular w-24 text-right text-caption text-muted-foreground">
                    {m.won} / {m.lost} / {m.rejected}
                  </span>
                </div>
              )
            })}
          </div>
          <div className="mt-2 text-micro text-muted-foreground">
            yutilgan / yutqazilgan / rad etilgan
          </div>
        </section>
      )}
    </div>
  )
}

function Kpi({ label, value, hint, cls }: {
  label: string; value: number | string; hint?: string; cls?: string
}) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2.5">
      <div className="text-caption text-muted-foreground">{label}</div>
      <div className={cn('tabular text-title font-semibold', cls)}>{value}</div>
      {hint && <div className="text-micro text-muted-foreground">{hint}</div>}
    </div>
  )
}
