import { useMemo } from 'react'

// Formatlash — pul, sana, muddat. Tender-AI dagi `format.ts` ning ERP uchun
// kerakli qismi, LEKIN i18n qatlamisiz: ERP interfeysi o'zbekcha (status va
// ustuvorlik yorliqlari ham serverdan o'zbekcha keladi, ularni tarjima qilish
// ikkinchi, ajralib ketadigan manba yaratardi).

const LOCALE = 'uz-UZ'

type Num = number | null | undefined
type Str = string | null | undefined

export function money(v: Num, c?: Str): string {
  if (v == null) return '—'
  const cur = (c || '').trim()
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 }).format(v)
    + (cur ? ` ${cur}` : '')
}

/** Katta summalar uchun qisqartma: 1.2 mlrd, 340 mln. Kanban kartasi va
 *  hisobot jadvallarida to'liq raqam o'qilmaydi — ustun kengligi yetmaydi. */
export function shortMoney(v: Num, c?: Str): string {
  if (v == null) return '—'
  const cur = (c || '').trim()
  const abs = Math.abs(v)
  const fmt = (n: number, suf: string) =>
    `${new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 }).format(n)} ${suf}`
  const body = abs >= 1e9 ? fmt(v / 1e9, 'mlrd')
    : abs >= 1e6 ? fmt(v / 1e6, 'mln')
      : abs >= 1e3 ? fmt(v / 1e3, 'ming')
        : new Intl.NumberFormat(LOCALE).format(v)
  return cur ? `${body} ${cur}` : body
}

export function dateFmt(iso: Str): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  return new Intl.DateTimeFormat(LOCALE, {
    day: '2-digit', month: '2-digit', year: 'numeric',
  }).format(d)
}

/** Sana VA vaqt. Voqealar ketma-ketligi muhim bo'lgan joyda
 *  (kirish urinishlari, jurnal) sananing o'zi yetarli emas. */
export function dateTimeFmt(iso: Str): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  return new Intl.DateTimeFormat(LOCALE, {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(d)
}

export type DeadlineLevel = 'none' | 'expired' | 'urgent' | 'soon' | 'ok'

/** Muddatgacha qolgan vaqt. Chegaralar tender-ai dagi bilan bir xil:
 *  3 kundan kam — qizil, 7 kundan kam — sariq. */
export function deadline(iso: Str): { level: DeadlineLevel; text: string } | null {
  if (!iso) return { level: 'none', text: 'muddatsiz' }
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const ms = d.getTime() - Date.now()
  if (ms < 0) return { level: 'expired', text: 'muddati o‘tgan' }
  const days = Math.floor(ms / 86_400_000)
  if (days < 1) {
    const h = Math.max(1, Math.floor(ms / 3_600_000))
    return { level: 'urgent', text: `${h} soat qoldi` }
  }
  if (days < 3) return { level: 'urgent', text: `${days} kun qoldi` }
  if (days < 7) return { level: 'soon', text: `${days} kun qoldi` }
  return { level: 'ok', text: `${days} kun qoldi` }
}

/** Daraja -> Tailwind sinflari. Sinf nomlari DINAMIK QURILMAYDI (JIT ularni
 *  topa olmaydi), shuning uchun to'liq yozilgan — tender-ai dagi bilan bir xil. */
export const DEADLINE_CLASS: Record<DeadlineLevel, string> = {
  none: 'bg-muted text-muted-foreground',
  ok: 'bg-ok-soft text-ok-strong',
  soon: 'bg-soon-soft text-soon-strong',
  urgent: 'bg-urgent-soft text-urgent-strong',
  expired: 'bg-muted text-muted-foreground line-through',
}

export function useFormat() {
  return useMemo(() => ({
    money, shortMoney, dateFmt, dateTimeFmt, deadline,
    num: (v: Num) => (v == null ? '—' : new Intl.NumberFormat(LOCALE).format(v)),
  }), [])
}
