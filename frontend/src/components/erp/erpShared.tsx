import { cn } from '@/lib/utils'
import type { Opportunity } from '@/types'

// ERP komponentlari uchun umumiy mayda qismlar.
//
// TIL HAQIDA: 1-bosqichda ERP interfeysi FAQAT O'ZBEKCHA. Sabab — status va
// ustuvorlik yorliqlari SERVERDAN keladi (`/erp/meta`, api/erp/opportunity.py)
// va u yerda ham faqat o'zbekcha; ularni frontendда tarjima qilish ikkinchi,
// ajralib ketadigan manba yaratardi. Yon paneldagi bo'lim nomi esa uchala
// tilda (`nav.opportunities`) — u umumiy navigatsiya qismi.

/** Radix Select bo'sh satrni qiymat sifatida qabul qilmaydi (Filters.tsx dagi
 *  bilan bir xil cheklov) — "hammasi" varianti maxsus belgi bilan yuritiladi. */
export const ALL = '__all__'
export const toSelect = (v: string) => (v === '' ? ALL : v)
export const toFilter = (v: string) => (v === ALL ? '' : v)

/** Ustuvorlik nishoni. Rang faqat "yuqori"da qichqiradi: hamma narsa rangli
 *  bo'lsa hech narsa ajralib turmaydi. */
export const PRIORITY_CLASS: Record<string, string> = {
  high: 'bg-urgent-soft text-urgent-strong',
  medium: 'bg-secondary text-primary',
  low: 'bg-muted text-muted-foreground',
}

/** Yakuniy statuslar — kodda ham, bazada ham bir xil ro'yxat. Bu yerda faqat
 *  KO'RINISH uchun: qoidalar serverda. */
export const FINAL_CLASS: Record<string, string> = {
  won: 'bg-ok-soft text-ok-strong',
  lost: 'bg-urgent-soft text-urgent-strong',
  rejected: 'bg-muted text-muted-foreground',
}

export function StatusBadge({ o, className }: { o: Opportunity; className?: string }) {
  return (
    <span className={cn(
      'rounded px-2 py-0.5 text-caption font-semibold whitespace-nowrap',
      FINAL_CLASS[o.status] || 'bg-secondary text-primary', className,
    )}>
      {o.status_label || o.status}
    </span>
  )
}

export function PriorityBadge({ o }: { o: Opportunity }) {
  return (
    <span className={cn('rounded px-1.5 py-px text-micro font-semibold',
      PRIORITY_CLASS[o.priority] || PRIORITY_CLASS.low)}>
      {o.priority_label || o.priority}
    </span>
  )
}

/** Xato satri — komponentlar xatoni JIMGINA YUTMAYDI (loyiha kelishuvi). */
export function ErpError({ msg }: { msg: string }) {
  return (
    <div className="rounded-lg border border-urgent/40 bg-urgent-soft px-4 py-3 text-body text-urgent-strong">
      {msg}
    </div>
  )
}

/** Sxema qo'llanmagan holat — ilova yiqilmaydi, sabab ochiq aytiladi:
 *  qaysi patch, qanday buyruq bilan qo'llanadi. */
export function SchemaMissing({ patch = 'schema_patch_erp_1.sql' }: { patch?: string }) {
  return (
    <div className="rounded-lg border border-soon/40 bg-soon-soft px-4 py-3 text-body text-soon-strong">
      ERP jadvallari bazada yo'q. Operator <code>{patch}</code> ni qo'llashi
      kerak: <code>psql "dbname=xtxarid user=postgres host=localhost" -f {patch}</code>
    </div>
  )
}

export const OPP_LABEL = (o: Opportunity) =>
  o.tender.title || `Tender #${o.tender.tender_ref || o.tender_id}`
