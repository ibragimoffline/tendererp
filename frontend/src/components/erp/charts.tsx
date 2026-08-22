import { useId, useState } from 'react'
import { cn } from '@/lib/utils'

// GRAFIK PRIMITIVLARI — kutubxonasiz.
//
// NEGA KUTUBXONA YO'Q: bu yerda kerak bo'lgan uch shakl (gorizontal
// ustun, guruhlangan ustun, nisbat chizig'i) sof CSS va SVG bilan
// chiziladi. Kutubxona 300 KB olib keladi va o'z rang tizimini
// majburlaydi — bizda esa ranglar allaqachon o'lchangan tokenlar.
//
// QOIDALAR (butun ilovada bir xil):
//   * SERIYA RANGI QAT'IY TARTIBDA — `--chart-1..4`, hech qachon
//     aylantirilmaydi. Filtr seriyalar sonini o'zgartirsa, qolganlari
//     QAYTA BO'YALMAYDI: rang narsaga tegishli, uning o'rniga emas.
//   * To'ldirishlar orasida 2px SIRT tirqishi — yonma-yon ranglar
//     bir-biriga qo'shilib ketmasin (rang ko'rish buzilishida ham).
//   * Matn HECH QACHON seriya rangida emas — u tokenli siyohda; rang
//     faqat yonidagi belgida.
//   * Ikki va undan ortiq seriya bo'lsa LEGENDA MAJBURIY: identifikatsiya
//     rangning o'ziga tashlab qo'yilmaydi.
//   * O'q va to'r — RECESSIV: ular ma'lumot emas, o'lchov.
//
// Hamma shakl `title` (native tooltip) va hover holatiga ega: HTML
// grafik interaktiv bo'lishi kerak, aks holda u rasm.

export const SERIES = ['var(--chart-1)', 'var(--chart-2)',
  'var(--chart-3)', 'var(--chart-4)'] as const

/** Nisbatni ko'rsatuvchi gorizontal ustun — MIQDOR uchun.
 *
 *  Uzunlik nolga bog'langan (boshqacha bo'lsa nisbat yolg'on bo'ladi).
 *  Qiymat ustunning yonida turadi, ustidа emas: qisqa ustunlarda matn
 *  ustunga sig'maydi va tashqarida ko'chib yurgan raqam o'qishni
 *  qiyinlashtiradi. */
export function BarRow({ label, value, max, hint, tone = 'primary', onClick }: {
  label: string
  value: number
  max: number
  /** O'ng chetdagi ikkinchi darajali qiymat (masalan summa) */
  hint?: string
  tone?: 'primary' | 'ok' | 'urgent' | 'muted'
  onClick?: () => void
}) {
  const pct = max > 0 ? Math.max(value > 0 ? 2 : 0, (value / max) * 100) : 0
  const fill = {
    primary: 'bg-primary', ok: 'bg-ok', urgent: 'bg-urgent',
    muted: 'bg-muted-foreground/40',
  }[tone]
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      className={cn('group flex w-full items-center gap-3 rounded px-1 py-1 text-left text-body',
        onClick && 'hover:bg-muted')}
      title={`${label}: ${value}${hint ? ` · ${hint}` : ''}`}>
      <span className="w-40 shrink-0 truncate">{label}</span>
      {/* To'r emas, o'lchov yo'lakchasi: u recessiv va ustun uzunligini
          taqqoslash uchun umumiy asos beradi. */}
      <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
        <span className={cn('block h-full rounded-full transition-[width]', fill)}
          style={{ width: `${pct}%` }} />
      </span>
      <span className="tabular w-10 shrink-0 text-right font-medium">{value}</span>
      {hint !== undefined && (
        <span className="tabular w-28 shrink-0 truncate text-right text-caption text-muted-foreground">
          {hint}
        </span>
      )}
    </Tag>
  )
}

export interface Group {
  label: string
  values: number[]
}

/** Guruhlangan ustunlar — VAQT bo'yicha o'zgarish uchun.
 *
 *  Nega chiziq emas: bu yerda oylik SANOQ, uzluksiz o'lchov emas.
 *  Chiziq oylar orasida qiymat bor degan ma'noni beradi — yo'q.
 *
 *  Nega yig'ma (stacked) emas: yig'ma ustunda faqat pastki qavatni
 *  taqqoslash mumkin, qolganlari suzib yuradi. Bu yerda esa aynan
 *  "yutilgan va yutqazilganni taqqoslash" kerak. */
export function GroupedBars({ groups, series, height = 132, format }: {
  groups: Group[]
  series: { label: string; color: string }[]
  height?: number
  format?: (v: number) => string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const id = useId()
  const max = Math.max(1, ...groups.flatMap((g) => g.values))
  const fmt = format || ((v: number) => String(v))

  return (
    <div>
      <div className="flex items-end gap-1.5 overflow-x-auto pb-1"
        style={{ height }}>
        {groups.map((g, gi) => (
          <div key={g.label}
            className={cn('flex min-w-9 flex-1 flex-col justify-end gap-1 rounded px-0.5 pt-1 transition-colors',
              hover === gi && 'bg-muted')}
            onMouseEnter={() => setHover(gi)}
            onMouseLeave={() => setHover(null)}
            title={`${g.label}: ` + series
              .map((s, i) => `${s.label} ${fmt(g.values[i] ?? 0)}`).join(' · ')}>
            {/* Ustunlar bitta guruh ichida yonma-yon; ular orasida 2px
                sirt tirqishi (`gap`) — ranglar qo'shilib ketmasin. */}
            <div className="flex flex-1 items-end justify-center gap-[2px]">
              {series.map((s, si) => {
                const v = g.values[si] ?? 0
                const h = v > 0 ? Math.max(3, (v / max) * 100) : 0
                return (
                  <span key={s.label}
                    aria-label={`${g.label} ${s.label} ${v}`}
                    className="w-full max-w-3 rounded-t-[4px] transition-[height]"
                    style={{ height: `${h}%`, background: s.color,
                      minHeight: v > 0 ? 3 : 0 }} />
                )
              })}
            </div>
            <span className="truncate text-center text-micro text-muted-foreground">
              {g.label}
            </span>
          </div>
        ))}
      </div>

      {/* Hover qatori — qiymatlar ustunlar ustida emas, shu yerda.
          Har ustunga raqam yozish grafikni jadvalga aylantiradi. */}
      <div aria-live="polite" id={id}
        className="mt-1 min-h-5 text-caption text-muted-foreground">
        {hover != null && (
          <span>
            <b className="text-foreground">{groups[hover].label}</b>
            {series.map((s, i) => (
              <span key={s.label} className="ml-3 whitespace-nowrap">
                <span className="mr-1 inline-block size-2 rounded-[2px] align-middle"
                  style={{ background: s.color }} />
                {s.label} <span className="tabular text-foreground">
                  {fmt(groups[hover].values[i] ?? 0)}
                </span>
              </span>
            ))}
          </span>
        )}
      </div>
    </div>
  )
}

/** Legenda — IKKI va undan ortiq seriya uchun MAJBURIY.
 *  Bitta seriyada legenda yo'q: sarlavhaning o'zi uni nomlaydi. */
export function Legend({ series }: {
  series: { label: string; color: string }[]
}) {
  if (series.length < 2) return null
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-muted-foreground">
      {series.map((s) => (
        <span key={s.label} className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-[3px]"
            style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  )
}

/** Katta raqam — grafik EMAS.
 *
 *  Bitta son uchun grafik chizish shu sonni o'qishni qiyinlashtiradi.
 *  Sarlavha ustida, izoh ostida: ko'z yuqoridan pastga tushadi. */
export function Stat({ label, value, hint, tone, onClick }: {
  label: string
  value: string | number
  hint?: string
  tone?: 'ok' | 'urgent' | 'soon'
  onClick?: () => void
}) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      className={cn('rounded-lg border bg-card px-3.5 py-3 text-left transition-colors',
        onClick && 'hover:border-primary/40 hover:bg-accent/40')}>
      <div className="text-caption text-muted-foreground">{label}</div>
      <div className={cn('tabular mt-0.5 text-title font-semibold leading-tight',
        tone === 'ok' && 'text-ok-strong',
        tone === 'urgent' && 'text-urgent-strong',
        tone === 'soon' && 'text-soon-strong')}>
        {value}
      </div>
      {hint && (
        <div className="mt-0.5 truncate text-micro text-muted-foreground">{hint}</div>
      )}
    </Tag>
  )
}

/** Bo'lim qutisi — hamma panel bitta shaklda bo'lsin. */
export function Panel({ title, hint, action, children, className }: {
  title: string
  hint?: string
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={cn('rounded-lg border bg-card p-4', className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-body font-semibold">{title}</h3>
          {hint && (
            <p className="mt-0.5 text-caption text-muted-foreground">{hint}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

/** Bo'sh holat — "ma'lumot yo'q" bilan "hali kiritilmagan" farqi. */
export function Empty({ msg, hint }: { msg: string; hint?: string }) {
  return (
    <div className="rounded-md border border-dashed px-3 py-6 text-center">
      <p className="text-body text-muted-foreground">{msg}</p>
      {hint && <p className="mt-1 text-caption text-muted-foreground">{hint}</p>}
    </div>
  )
}
