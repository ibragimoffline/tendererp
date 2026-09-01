import { cn } from '@/lib/utils'
import type { Opportunity } from '@/types'

// ERP komponentlari uchun umumiy mayda qismlar.
//
// TIL HAQIDA: 1-bosqichda ERP interfeysi FAQAT O'ZBEKCHA. Sabab — status va
// ustuvorlik yorliqlari SERVERDAN keladi (`/erp/meta`, api/erp/opportunity.py)
// va u yerda ham faqat o'zbekcha; ularni frontendда tarjima qilish ikkinchi,
// ajralib ketadigan manba yaratardi. Yon paneldagi bo'lim nomi esa uchala
// tilda (`nav.opportunities`) — u umumiy navigatsiya qismi.

/** Rol ierarxiyasi — backenddagi `api/auth.py` ROLE_RANK bilan BIR XIL.
 *
 *  NEGA EKRANDA HAM BOR: huquqni SERVER hal qiladi (403), lekin brokerga
 *  ochilmaydigan bo'limni KO'RSATIB qo'yish ham xato — u bosadi va xato
 *  oladi. Ya'ni bu ro'yxat huquq emas, KO'RINISH qoidasi.
 *
 *  Yagona nusxa shu yerda: `App.tsx` va `Dashboard.tsx` avval rol
 *  nomlarini o'zlari solishtirardi va yangi rol qo'shilganda ikkalasini
 *  ham eslab tuzatish kerak edi. */
export const ROLE_RANK: Record<string, number> = {
  broker: 1, menejer: 2, rahbar: 3, admin: 4,
}

/** `role` kamida `need` darajasidami. Noma'lum rol — eng past daraja:
 *  tanimagan narsaga huquq berilmaydi. */
export const roleAtLeast = (role: string | undefined, need: string) =>
  (ROLE_RANK[role || ''] || 0) >= (ROLE_RANK[need] || 99)

// --- HUQUQLAR -------------------------------------------------------------
// Matritsa SERVERDA (`api/erp/perm.py`) va u `GET /erp/auth/me` javobida
// keladi. Bu yerda faqat o'qish qulayligi: har komponentga `user` ni
// uzatib yurish (prop drilling) o'rniga bitta joyda saqlanadi.
//
// BU HIMOYA EMAS — himoya serverda, har so'rovda. Bu KO'RINISH qoidasi:
// bosilganda 403 beradigan tugma ko'rsatilmasin.

let PERMS: Record<string, string | null> = {}

/** Kirgandan keyin (va `me` yangilanganda) chaqiriladi. */
export function setPerms(p?: Record<string, string | null> | null) {
  PERMS = p || {}
}

/** Amalga ruxsat bormi. Noma'lum amal — yo'q (server ham rad etadi). */
export const can = (action: string) => Boolean(PERMS[action])

/** Daraja: 'full' | 'own' | 'read' | null. */
export const permLevel = (action: string) => PERMS[action] ?? null

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
