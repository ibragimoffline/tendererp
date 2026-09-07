import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { cn } from '@/lib/utils'
import type { ProfitRow } from '@/types'

// KARTADAGI FOYDA — "bu tenderdan qancha ishladik?"
//
// Uch son va ularning har biri boshqa joydan keladi:
//   daromad — chiqarilgan fakturalarning QQS SIZ summasi;
//   tannarx — sarflangan tovarning MUZLATILGAN tannarxi;
//   foyda   — ayirma.
//
// QQS daromadga KIRMAYDI: u davlatniki, biz faqat yig'ib beramiz. Shuning
// uchun u alohida ko'rsatiladi — "nega faktura 2.24 mln, foyda esa 2 mln
// dan hisoblanyapti?" degan savol tug'ilmasin.
//
// HISOB TO'LIQ BO'LMASA — OCHIQ AYTILADI. "Foyda 800 ming" degan raqamdan
// ko'ra "800 ming, lekin 3 ta chiqimning tannarxi noma'lum" degani ancha
// foydali.

export default function ProfitLine({ oppId }: { oppId: number }) {
  const f = useFormat()
  const [p, setP] = useState<ProfitRow | null>(null)

  useEffect(() => {
    // Faktura yoki ombor sxemasi qo'llanmagan bo'lsa (503) blok jim
    // yashiriladi — karta shu tufayli buzilmasligi kerak.
    api.cardProfit(oppId).then(setP).catch(() => setP(null))
  }, [oppId])

  // Pul harakati bo'lmagan kartada blok ko'rsatilmaydi: nol-nol-nol
  // qator hech narsa aytmaydi.
  if (!p || (!p.revenue && !p.cost)) return null

  return (
    <section className="mt-5">
      <h3 className="mb-2 text-body font-semibold">Natija</h3>
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-caption">
        <span>
          <span className="text-muted-foreground">Daromad (QQS siz): </span>
          <span className="tabular font-semibold">
            {f.money(p.revenue, p.currency)}
          </span>
          {p.vat > 0 && (
            <span className="text-muted-foreground">
              {' '}+ QQS {f.money(p.vat, p.currency)}
            </span>
          )}
        </span>
        <span>
          <span className="text-muted-foreground">Tannarx: </span>
          <span className="tabular font-semibold">
            {f.money(p.cost, p.currency)}
          </span>
        </span>
        <span>
          <span className="text-muted-foreground">Foyda: </span>
          <span className={cn('tabular font-semibold',
            p.profit > 0 ? 'text-ok-strong'
              : p.profit < 0 ? 'text-destructive' : '')}>
            {f.money(p.profit, p.currency)}
          </span>
          {p.margin != null && (
            <span className="text-muted-foreground"> ({p.margin}%)</span>
          )}
        </span>
        {p.invoices > 0 && (
          <span className="text-muted-foreground">
            {p.invoices} ta faktura
          </span>
        )}
      </div>

      {!p.complete && (
        <p className="mt-1 text-caption text-soon-strong">
          Hisob to'liq emas: {p.unknown_cost_moves} ta chiqimda tannarx
          yo'q (katalogda narx ko'rsatilmagan) — haqiqiy foyda bundan kam.
        </p>
      )}
    </section>
  )
}
