import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { cn } from '@/lib/utils'
import type { ProfitReport } from '@/types'

// RAHBAR KO'RINISHI — "qaysi tender qancha pul olib keldi".
//
// Uchta qoida ko'rinishda ham saqlanadi:
//   1. QQS daromad emas — u umuman ko'rsatilmaydi (kartada alohida bor);
//   2. tannarx MUZLATILGAN narxdan — katalog o'zgarsa hisobot o'zgarmaydi;
//   3. hisob to'liq bo'lmasa — bu YASHIRILMAYDI, tepada ogohlantirish
//      turadi va tegishli qatorga belgi qo'yiladi.
//
// ARALASH VALYUTA QO'SHILMAYDI. Yig'indi har valyuta uchun alohida
// chiqadi; bitta umumiy son faqat hamma karta bitta valyutada
// bo'lgandagina. Konvertatsiya yo'q: kurs qaysi kunniki degan savolga
// javob yo'q va noto'g'ri yig'indi yo'q yig'indidan yomonroq.
//
// Endpoint `manager` huquqini talab qiladi: 403 kelsa panel jim
// yashiriladi, chunki brokerga bu bo'lim umuman ko'rinmasligi kerak.

export default function ProfitPanel({ onOpen }: { onOpen: (id: number) => void }) {
  const f = useFormat()
  const [d, setD] = useState<ProfitReport | null>(null)

  useEffect(() => {
    api.profit({ limit: 200 }).then(setD).catch(() => setD(null))
  }, [])

  if (!d || !d.items.length) return null
  const cards = d.by_currency.reduce((n, c) => n + c.cards, 0)

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-3">
        <h3 className="mb-1.5 text-caption font-semibold text-muted-foreground">
          Foyda ({cards} ta karta)
        </h3>
        {/* Har valyuta ALOHIDA qator. Bitta valyuta bo'lsa qator ham
            bitta — ya'ni oddiy holat o'zgarmaydi. */}
        <div className="space-y-0.5">
          {d.by_currency.map((t) => (
            <div key={t.currency}
              className="flex flex-wrap items-baseline gap-x-4 text-caption">
              {d.mixed_currency && (
                <span className="w-10 shrink-0 font-semibold">{t.currency}</span>
              )}
              <span>
                <span className="text-muted-foreground">Daromad </span>
                <span className="tabular font-semibold">
                  {f.shortMoney(t.revenue, t.currency)}
                </span>
              </span>
              <span>
                <span className="text-muted-foreground">Tannarx </span>
                <span className="tabular font-semibold">
                  {f.shortMoney(t.cost, t.currency)}
                </span>
              </span>
              <span>
                <span className="text-muted-foreground">Foyda </span>
                <span className={cn('tabular font-semibold',
                  t.profit > 0 ? 'text-ok-strong'
                    : t.profit < 0 ? 'text-urgent-strong' : '')}>
                  {f.shortMoney(t.profit, t.currency)}
                </span>
                {t.margin != null && (
                  <span className="text-muted-foreground"> ({t.margin}%)</span>
                )}
              </span>
            </div>
          ))}
        </div>
        {d.mixed_currency && (
          <p className="mt-1 text-micro text-muted-foreground">
            Valyutalar aralash — umumiy yig'indi berilmaydi. Kurs bo'yicha
            qo'shish qaysi kungi kurs ekaniga bog'liq bo'lardi.
          </p>
        )}
      </div>

      {!d.complete && (
        <p className="mb-2 text-micro text-soon-strong">
          Hisob to'liq emas: {d.unknown_cost_moves} ta chiqimning tannarxi
          noma'lum. Ular tannarxga qo'shilmadi — haqiqiy foyda bundan kam.
        </p>
      )}

      <div className="space-y-1">
        {d.items.map((r) => (
          <button key={r.opportunity_id} type="button"
            onClick={() => onOpen(r.opportunity_id)}
            className="flex w-full items-center gap-3 rounded px-1 py-1
                       text-left text-body hover:bg-muted">
            <span className="flex-1 truncate">
              {r.title || `#${r.opportunity_id}`}
              {!r.complete && (
                <span className="ml-1 text-micro text-soon-strong"
                  title={`${r.unknown_cost_moves} ta chiqimning tannarxi noma'lum`}>
                  to'liq emas
                </span>
              )}
            </span>
            <span className="tabular w-28 shrink-0 text-right text-caption
                             text-muted-foreground">
              {f.shortMoney(r.revenue, r.currency)}
            </span>
            <span className="tabular w-28 shrink-0 text-right text-caption
                             text-muted-foreground">
              {f.shortMoney(r.cost, r.currency)}
            </span>
            <span className={cn('tabular w-28 shrink-0 text-right font-semibold',
              r.profit > 0 ? 'text-ok-strong'
                : r.profit < 0 ? 'text-urgent-strong' : '')}>
              {f.shortMoney(r.profit, r.currency)}
            </span>
            <span className="tabular w-12 shrink-0 text-right text-caption
                             text-muted-foreground">
              {r.margin == null ? '—' : `${r.margin}%`}
            </span>
          </button>
        ))}
      </div>
      <div className="mt-2 text-micro text-muted-foreground">
        daromad (QQS siz) / tannarx / foyda / foiz
      </div>
    </section>
  )
}
