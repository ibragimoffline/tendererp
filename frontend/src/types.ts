export type Nullable<T> = T | null


// ===========================================================================
// ERP 1-bosqich — "Ishga olish" + Opportunity pipeline
// ===========================================================================

/** Kanban ustuni / status tanlagichi uchun bitta status */
export interface ErpStatus {
  code: string
  label: string
  /** yakuniy (won/lost/rejected) — bundan qaytish izoh talab qiladi */
  final: boolean
}

export interface ErpPriority {
  code: string
  label: string
}

/** `/erp/meta` — statuslar, ustuvorliklar va sxema holati bir joyda.
 *  Ro'yxatlar SERVERDA (api/erp/opportunity.py) e'lon qilinadi va frontendda
 *  takrorlanmaydi — ikki manba ajralib ketmasligi uchun. */
export interface ErpMeta {
  /** false = schema_patch_erp_1.sql bazaga qo'llanmagan */
  schema_ready: boolean
  clients_ready?: boolean
  /** false = schema_patch_erp_3.sql qo'llanmagan (vazifalar ishlamaydi) */
  tasks_ready?: boolean
  statuses: ErpStatus[]
  priorities: ErpPriority[]
  /** yutqazish sabablari — kod ro'yxati serverdan (erkin matn emas) */
  lost_reasons?: { code: string; label: string }[]
  /** false = schema_patch_erp_4.sql qo'llanmagan (takliflar ishlamaydi) */
  submissions_ready?: boolean
  /** false = schema_patch_erp_5.sql qo'llanmagan (shartnomalar ishlamaydi) */
  contracts_ready?: boolean
  contract_statuses?: ContractStatus[]
  /** false = schema_patch_erp_8.sql qo'llanmagan (ombor ishlamaydi) */
  stock_ready?: boolean
  stock_kinds?: { code: string; label: string }[]
  /** false = schema_patch_erp_11.sql qo'llanmagan (fakturalar ishlamaydi) */
  invoice_ready?: boolean
  invoice_statuses?: { code: string; label: string }[]
  payment_methods?: { code: string; label: string }[]
  /** BO'SH = eksport formati sozlanmagan; interfeys tugmani ko'rsatmaydi */
  invoice_export_formats?: { code: string; label: string }[]
  /** false = schema_patch_erp_24.sql qo'llanmagan (sabab hujjati yo'q) */
  fayl_ready?: boolean
  /** Fayl BIRIKTIRILADIGAN holatlar — SERVERDAN. Ekran o'z ro'yxatini
   *  tutmaydi: ikki ro'yxat vaqt o'tib ajralib ketardi. */
  fayl_holatlar?: string[]
  /** Ruxsat etilgan kengaytmalar (`.pdf`, `.docx`...) — `<input accept>` */
  fayl_turlar?: string[]
  /** Bir fayl uchun chegara, baytda */
  fayl_max_hajm?: number
  auth_ready?: boolean
  /** tender-ai interfeysining manzili — kartadagi havola uchun */
  tender_web?: string
}

/** Tenderning MUZLATILGAN nusxasi — ishga olingan paytdagi holat.
 *  Jonli tender o'zgarsa bu o'zgarmaydi (erp_arxitektura.md 2.2). */
export interface OpportunitySnapshot {
  source_platform: Nullable<string>
  /** manbadagi asl raqam (tender.source_id) */
  tender_ref: Nullable<string>
  customer_name: Nullable<string>
  title: Nullable<string>
  start_price: Nullable<number>
  currency: Nullable<string>
  deadline_at: Nullable<string>
  region_name: Nullable<string>
  source_url: Nullable<string>
}

export interface OpportunityRef {
  id: number
  name: Nullable<string>
}

export interface OpportunityHistoryItem {
  id: number
  from_status: Nullable<string>
  to_status: string
  from_label: Nullable<string>
  to_label: Nullable<string>
  changed_by: Nullable<string>
  note: Nullable<string>
  changed_at: Nullable<string>
}

export interface Opportunity {
  id: number
  tender_id: number
  tender: OpportunitySnapshot
  broker: Nullable<OpportunityRef>
  client: Nullable<OpportunityRef>
  priority: string
  priority_label: Nullable<string>
  win_probability: Nullable<number>
  note: Nullable<string>
  next_task: Nullable<string>
  next_task_at: Nullable<string>
  status: string
  status_label: Nullable<string>
  is_final: boolean
  status_changed_at: Nullable<string>
  closed_at: Nullable<string>
  /** faqat 'lost' statusida to'ladi (kod) */
  lost_reason?: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
  updated_at: Nullable<string>
  /** faqat bitta karta so'ralganda (`GET /erp/opportunities/{id}`) */
  history?: OpportunityHistoryItem[]
}

/** Xodim kiritadigan maydonlar. Snapshot serverda tenderdan olinadi. */
export interface OpportunityInput {
  broker_id: Nullable<number>
  client_id: Nullable<number>
  priority: string
  win_probability: Nullable<number>
  note: Nullable<string>
  next_task: Nullable<string>
  next_task_at: Nullable<string>
  /** auth yo'q: tanlangan brokerning nomi */
  created_by?: Nullable<string>
}

export interface ErpBroker {
  id: number
  full_name: string
  email: Nullable<string>
  phone: Nullable<string>
  active: boolean
}

export interface ErpClient {
  id: number
  name: string
  active: boolean
}

export interface ErpStatsRow {
  code: string
  label: string
  n: number
  /** Aralash valyutada `null` — summalar qo'shilmaydi */
  total: Nullable<number>
}

export interface ErpStatsBroker {
  id: number
  full_name: string
  n: number
  open_n: number
  won_n: number
  lost_n: number
  /** Aralash valyutada `null` */
  open_total: Nullable<number>
}

export interface ErpStatsClient {
  id: number
  name: string
  n: number
  won_n: number
  lost_n: number
  /** Aralash valyutada `null` */
  won_total: Nullable<number>
}

export interface ErpStatsUpcoming {
  id: number
  title: Nullable<string>
  deadline_at: Nullable<string>
  status: string
  status_label: Nullable<string>
  start_price: Nullable<number>
  currency: Nullable<string>
  broker_name: Nullable<string>
  client_name: Nullable<string>
}

export interface ErpStatsMonth {
  month: string
  won: number
  lost: number
  rejected: number
}

/** `/erp/stats` — hisob BAZADA qilinadi, bu yerda faqat ko'rsatiladi. */
export interface ErpStats {
  /** Kartalar bitta valyutada bo'lsa — o'sha valyuta; aralash bo'lsa `null` */
  currency: Nullable<string>
  currencies: string[]
  /** Aralash valyuta: pul yig'indilari `null` keladi — qo'shib bo'lmaydi */
  mixed_currency: boolean
  total: number
  open: number
  open_total: Nullable<number>
  submitted: number
  won: number
  lost: number
  won_total: Nullable<number>
  rejected: number
  /** yutilgan / (yutilgan + yutqazilgan); hal bo'lgani yo'q bo'lsa null */
  win_rate: Nullable<number>
  by_status: ErpStatsRow[]
  by_broker: ErpStatsBroker[]
  by_client: ErpStatsClient[]
  upcoming: ErpStatsUpcoming[]
  monthly: ErpStatsMonth[]
  upcoming_days: number
}

// ===========================================================================
// ERP 2-bosqich — mijoz korxonalar bazasi va korxona passporti
// ===========================================================================

/** Korxona passporti. Hamma maydon ixtiyoriy: karta INN'siz ham yaratiladi,
 *  passport keyin to'ldiriladi. `missing` — serverda hisoblangan "hali
 *  to'ldirilmagan muhim maydonlar" ro'yxati. */
export interface ClientPassport {
  id: number
  name: string
  inn: Nullable<string>
  oked: Nullable<string>
  legal_form: Nullable<string>
  tax_mode: Nullable<string>
  address_legal: Nullable<string>
  address_actual: Nullable<string>
  bank_name: Nullable<string>
  bank_mfo: Nullable<string>
  bank_account: Nullable<string>
  director_name: Nullable<string>
  phone: Nullable<string>
  email: Nullable<string>
  note: Nullable<string>
  active: boolean
  /** QQS to'lovchimi. `null` = HALI SO'RALMAGAN (false bilan bir xil
   *  emas): faktura stavkasi shu javobga qarab hal bo'ladi (5B-2). */
  vat_payer: Nullable<boolean>
  /** Sukut stavka (%). Faktura QATORIGA nusxa ko'chiriladi. */
  vat_rate: Nullable<number>
  created_at: Nullable<string>
  updated_at: Nullable<string>
  missing: string[]
}

/** Ro'yxat qatori — passport + shu mijoz bo'yicha natija. Hisob bazada. */
export interface ClientRow extends ClientPassport {
  opp_n: number
  won_n: number
  lost_n: number
  open_n: number
  doc_n: number
  win_rate: Nullable<number>
}

export interface ClientContact {
  id: number
  client_id: number
  full_name: string
  position: Nullable<string>
  phone: Nullable<string>
  email: Nullable<string>
  is_primary: boolean
  note: Nullable<string>
  created_at: Nullable<string>
}

/** Mijoz hujjati. Maydonlari `CompanyDocument` bilan bir xil — cheklist
 *  ikkala manbani ham bir xil o'qiydi. */
export interface ClientDocument {
  id: number
  client_id: number
  doc_type: string
  name: string
  number: Nullable<string>
  issued_at: Nullable<string>
  valid_until: Nullable<string>
  file_name: Nullable<string>
  file_ref: Nullable<string>
  note: Nullable<string>
  created_at: Nullable<string>
  updated_at: Nullable<string>
}

/** Mijoz bilan bog'liq karta — passport sahifasidagi qisqa ko'rinish */
export interface ClientOpportunity {
  id: number
  title: Nullable<string>
  tender_id: number
  tender_ref: Nullable<string>
  status: string
  /** Odam o'qiydigan nomi — SERVERDAN (`api/erp/opportunity.py`).
   *  Frontendда ikkinchi ro'yxat saqlanmaydi. */
  status_label: string
  start_price: Nullable<number>
  currency: Nullable<string>
  deadline_at: Nullable<string>
  closed_at: Nullable<string>
  broker_name: Nullable<string>
}

/** `GET /erp/clients/{id}` — passport + aloqalar + hujjatlar + kartalar */
export interface ClientFull extends ClientPassport {
  contacts: ClientContact[]
  documents: ClientDocument[]
  opportunities: ClientOpportunity[]
  summary: {
    opp_n: number
    won_n: number
    lost_n: number
    /** Rad etilganlar. `win_rate` MAXRAJIGA kirmaydi (biz qatnashmadik —
     *  yutqazmadik), lekin ekranda ko'rsatiladi: aks holda "1 ta karta,
     *  yutish 100%" degan qator qayerdan kelgani tushunarsiz qoladi. */
    rejected_n: number
    open_n: number
    /** Aralash valyutada `null` — summalar qo'shilmaydi */
    won_total: Nullable<number>
    /** Bitta valyuta bo'lsa o'shanisi, aralashda `null` */
    currency: Nullable<string>
    mixed_currency: boolean
    win_rate: Nullable<number>
  }
}

/** Passportni saqlash uchun tana. `name` majburiy, qolgani ixtiyoriy. */
export interface ClientInput {
  name: string
  inn?: Nullable<string>
  oked?: Nullable<string>
  legal_form?: Nullable<string>
  tax_mode?: Nullable<string>
  address_legal?: Nullable<string>
  address_actual?: Nullable<string>
  bank_name?: Nullable<string>
  bank_mfo?: Nullable<string>
  bank_account?: Nullable<string>
  director_name?: Nullable<string>
  phone?: Nullable<string>
  email?: Nullable<string>
  note?: Nullable<string>
  active?: boolean
  /** QQS to'lovchimi. `null` = hali so'ralmagan (5B-2) */
  vat_payer?: Nullable<boolean>
  vat_rate?: Nullable<number>
}

export interface ClientContactInput {
  full_name: string
  position?: Nullable<string>
  phone?: Nullable<string>
  email?: Nullable<string>
  is_primary?: boolean
  note?: Nullable<string>
}

export interface ClientDocumentInput {
  doc_type: string
  name: string
  number?: Nullable<string>
  issued_at?: Nullable<string>
  valid_until?: Nullable<string>
  file_name?: Nullable<string>
  file_ref?: Nullable<string>
  note?: Nullable<string>
}

// ===========================================================================
// Cheklist — qoidalar TENDER-AI da, bu yerda faqat natijaning shakli
// (api/tenderai.py orqali keladi). Turlar tender-ai'dagi bilan mos bo'lishi
// SHART: manba `api/compliance.py` -> build_checklist().
// ===========================================================================

export interface ComplianceDocument {
  id?: number
  name: Nullable<string>
  number: Nullable<string>
  issued_at: Nullable<string>
  valid_until: Nullable<string>
  file_name?: Nullable<string>
  file_ref?: Nullable<string>
}

export interface ComplianceItem {
  doc_type: string
  label: string
  hint: Nullable<string>
  /** 'tender' — tender matnida talab topilgan; 'bazaviy' — odatiy to'plam */
  required_by: string
  evidence: Nullable<string>
  in_base: boolean
  document: Nullable<ComplianceDocument>
  status: 'ok' | 'expiring_soon' | 'expired' | 'missing'
  days_left: Nullable<number>
}

export interface ComplianceResult {
  items: ComplianceItem[]
  summary: {
    ready: number
    expiring_soon: number
    expired: number
    missing: number
    blocking: number
    note: string
    disclaimer: string
  }
  /** 'client' — mijoz hujjatlari bo'yicha; 'company' — mijoz tanlanmagan */
  doc_source?: string
  client?: Nullable<{ id: number; name: Nullable<string> }>
}

/** Hujjat turlari — tender-ai dagi kanonik ro'yxat (`compliance.DOC_TYPES`) */
export interface DocumentType {
  code: string
  label: string
  hint: Nullable<string>
  base: boolean
}

/** `GET /health` — ERP tender-ai'siz ham ishlaydi, lekin buni ochiq aytadi */
export interface ErpHealth {
  ok: boolean
  schema_ready: boolean
  clients_ready: boolean
  tender_ai: string
  tender_ai_web: string
}

// ===========================================================================
// Shablon importi — mijoz hujjatlari
// ===========================================================================

export interface ImportRow {
  row: number
  doc_type: string
  label: Nullable<string>
  name: Nullable<string>
  number: Nullable<string>
  issued_at: Nullable<string>
  valid_until: Nullable<string>
  status: string
  file_ref: Nullable<string>
}

export interface ImportIssue {
  row: number
  column: string
  field: Nullable<string>
  value: Nullable<string>
  message: string
}

/** `POST /erp/clients/{id}/documents/import` javobi.
 *  Faylni TENDER-AI o'qiydi (qoidalar u yerda), yozishni ERP qiladi. */
export interface ImportResult {
  dry_run: boolean
  client_id: number
  filename: string
  format: string
  header_row: number
  rows_total: number
  rows_ok: number
  rows_error: number
  /** dry_run bo'lsa — bashorat; aks holda haqiqiy natija */
  inserted: number
  updated: number
  rows: ImportRow[]
  errors: ImportIssue[]
  warnings: ImportIssue[]
  columns: {
    detected: Record<string, Nullable<string>>
    unknown: string[]
    missing: string[]
  }
}

// ===========================================================================
// Snapshot va jonli tender farqi
// ===========================================================================

export interface TenderDiffItem {
  field: string
  label: string
  /** kartadagi (muzlatilgan) qiymat */
  was: string | number | null
  /** tenderdagi hozirgi qiymat */
  now: string | number | null
}

/** `GET /erp/opportunities/{id}/tender-diff`.
 *  Snapshot O'ZGARTIRILMAYDI — bu faqat xabar. */
export interface TenderDiff {
  opportunity_id: number
  tender_id: number
  /** false — tender manbadan o'chirilgan (ETL), karta esa qoladi */
  exists: boolean
  changed: TenderDiffItem[]
  /** manbadagi HOZIRGI status (snapshotda emas) */
  source?: Nullable<{
    status: Nullable<string>
    status_name: Nullable<string>
    closed: boolean
  }>
  /** tender manbada yopilgan, karta esa hali ochiq — yakunlash TAKLIFI.
   *  Tizim o'zi o'zgartirmaydi: manba g'olibni ochiq bermaydi. */
  suggest_close?: boolean
}

// ===========================================================================
// Vazifalar (3-bosqich)
// ===========================================================================

export interface TaskAssignee {
  id: number
  name: Nullable<string>
}

export interface OpportunityTask {
  id: number
  opportunity_id: number
  title: string
  assignee: Nullable<TaskAssignee>
  due_at: Nullable<string>
  done: boolean
  done_at: Nullable<string>
  note: Nullable<string>
  reminded_at: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
  /** kechikkanini SERVER hisoblaydi — brauzer soati noto'g'ri bo'lishi mumkin */
  overdue: boolean
}

export interface TaskInput {
  title: string
  assignee_broker_id?: Nullable<number>
  due_at?: Nullable<string>
  note?: Nullable<string>
  created_by?: Nullable<string>
}

/** "Mening ishlarim" — vazifa + karta konteksti */
export interface MyTask extends OpportunityTask {
  opportunity: {
    id: number
    title: Nullable<string>
    status: string
    tender_id: number
    client_name: Nullable<string>
    broker_name: Nullable<string>
    deadline_at: Nullable<string>
    start_price: Nullable<number>
    currency: Nullable<string>
  }
}

export interface MyTasks {
  broker_id: Nullable<number>
  /** Kirgan hodimning `broker_id` si (bo'lsa) — filtr sukut bo'yicha shu */
  self_broker_id: Nullable<number>
  days: number
  overdue: MyTask[]
  today: MyTask[]
  later: MyTask[]
  total: number
}

// ===========================================================================
// Taklif va topshirish (4-bosqich)
// ===========================================================================

/** Muzlatilgan cheklist nusxasi — to'liq javobning KERAKLI qismi */
export interface SubmissionCompliance {
  summary?: {
    ready: number
    missing: number
    expired: number
    expiring_soon: number
    blocking: number
  }
  doc_source?: string
  items?: {
    doc_type: string
    label: string
    status: string
    in_base: boolean
    valid_until: Nullable<string>
  }[]
}

/** Topshirilgan taklif — O'ZGARMAS yozuv. Xato bo'lsa yangi versiya. */
export interface Submission {
  id: number
  opportunity_id: number
  version: number
  submitted_at: Nullable<string>
  submitted_by: Nullable<string>
  price: Nullable<number>
  currency: Nullable<string>
  pricing: Nullable<Record<string, unknown>>
  compliance: Nullable<SubmissionCompliance>
  documents: Nullable<ClientDocument[]>
  blocking_count: number
  confirmed_note: Nullable<string>
  note: Nullable<string>
}

/** `GET /erp/opportunities/{id}/submission` — topshirishdan oldingi holat.
 *  Tender-AI javob bermasa qismlar null bo'ladi va sababi `warnings` da. */
export interface SubmissionPackage {
  opportunity: Opportunity
  pricing: Nullable<{
    manual_price: Nullable<number>
    currency: Nullable<string>
    result: Nullable<Record<string, unknown>>
    updated_at: Nullable<string>
  }>
  compliance: Nullable<ComplianceResult>
  blocking: number
  documents: ClientDocument[]
  source: Nullable<{ status: Nullable<string>; name: Nullable<string>; closed: boolean }>
  warnings: string[]
  submissions: Submission[]
  suggested_price: Nullable<number>
  currency: Nullable<string>
}

export interface SubmissionInput {
  price?: Nullable<number>
  currency?: Nullable<string>
  confirmed?: boolean
  confirmed_note?: Nullable<string>
  note?: Nullable<string>
  submitted_by?: Nullable<string>
}

// ===========================================================================
// Shartnoma va bizning rekvizitlar (5A-1)
// ===========================================================================

export interface ContractStatus {
  code: string
  label: string
}

/** Bizning kompaniya passporti. `company_profile` (tender-ai) qidiruv
 *  profili — bu esa YURIDIK passport: shartnoma va hisob-faktura uchun. */
export interface OwnCompany {
  name: string
  inn: Nullable<string>
  oked: Nullable<string>
  legal_form: Nullable<string>
  tax_mode: Nullable<string>
  address_legal: Nullable<string>
  address_actual: Nullable<string>
  bank_name: Nullable<string>
  bank_mfo: Nullable<string>
  bank_account: Nullable<string>
  director_name: Nullable<string>
  phone: Nullable<string>
  email: Nullable<string>
  note: Nullable<string>
  /** BIZ QQS to'lovchimizmi. `null` = HALI SO'RALMAGAN (`false` bilan
   *  bir xil emas): QQS ni sotuvchi hisoblaydi, shuning uchun bu javob
   *  faktura stavkasiga ta'sir qiladi. */
  vat_payer: Nullable<boolean>
  vat_rate: Nullable<number>
  updated_at: Nullable<string>
  /** shartnoma uchun yetishmayotgan maydonlar (serverda hisoblanadi) */
  missing: string[]
}

/** Saqlash uchun tana: `name` majburiy, qolgani ixtiyoriy —
 *  passport bosqichma-bosqich to'ldiriladi. */
export type OwnCompanyInput =
  { name: string } & Partial<Omit<OwnCompany, 'name' | 'updated_at' | 'missing'>>

export interface Contract {
  id: number
  opportunity_id: number
  submission_id: Nullable<number>
  submission: Nullable<{ id: number; version: number; price: Nullable<number> }>
  number: Nullable<string>
  signed_at: Nullable<string>
  starts_at: Nullable<string>
  ends_at: Nullable<string>
  amount: Nullable<number>
  currency: Nullable<string>
  status: string
  status_label: Nullable<string>
  is_final: boolean
  status_changed_at: Nullable<string>
  note: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
  updated_at: Nullable<string>
}

/** Ro'yxat qatori — shartnoma + karta konteksti */
export interface ContractRow extends Contract {
  opportunity: {
    id: number
    title: Nullable<string>
    tender_id: number
    tender_ref: Nullable<string>
    client_name: Nullable<string>
    broker_name: Nullable<string>
  }
}

export interface ContractInput {
  submission_id?: Nullable<number>
  number?: Nullable<string>
  signed_at?: Nullable<string>
  starts_at?: Nullable<string>
  ends_at?: Nullable<string>
  amount?: Nullable<number>
  currency?: Nullable<string>
  status?: Nullable<string>
  note?: Nullable<string>
  created_by?: Nullable<string>
}

export interface ContractStats {
  by_status: { code: string; label: string; n: number; total: number }[]
  total: number
  active: number
}

// ===========================================================================
// Rahbar tahlili (5A-2) — hammasi `opportunity_history` dan hisoblanadi
// ===========================================================================

export interface StageTime {
  code: string
  label: Nullable<string>
  /** shu bosqichda TUGAGAN turishlar soni (o'rtacha shulardan) */
  finished_n: number
  avg_days: Nullable<number>
  median_days: Nullable<number>
  max_days: Nullable<number>
  /** hozir shu bosqichda turgan ochiq kartalar (= faol_n + kechikkan_n) */
  ongoing_n: number
  /** shulardan HAQIQATAN ishlanayotgani: muddati hali o'tmagan */
  faol_n: number
  /** muddati O'TGAN, lekin yopilmagan — ular "ishlanmoqda" EMAS.
   *  Tizim kartani o'zi yopmaydi (qaror odamniki), shuning uchun ular
   *  yopilmaguncha shu yerda turadi va ko'rsatkichni shishiradi. */
  kechikkan_n: number
  oldest_days: Nullable<number>
  final: boolean
}

export interface FunnelStep {
  code: string
  label: Nullable<string>
  /** shu bosqichga YETIB BORGAN kartalar (hozirgi holati emas — tarixi) */
  reached: number
  /** ishga olinganlarning foizi */
  pct: Nullable<number>
}

export interface BrokerCycle {
  id: number
  full_name: string
  n: number
  submitted_n: number
  won_n: number
  avg_to_submit: Nullable<number>
  avg_to_win: Nullable<number>
}

export interface StuckCard {
  id: number
  title: Nullable<string>
  status: string
  status_label: Nullable<string>
  idle_days: number
  status_changed_at: Nullable<string>
  deadline_at: Nullable<string>
  start_price: Nullable<number>
  currency: Nullable<string>
  broker_name: Nullable<string>
  client_name: Nullable<string>
  open_tasks: number
}

export interface ErpAnalytics {
  stages: StageTime[]
  funnel: FunnelStep[]
  by_broker: BrokerCycle[]
  stuck: StuckCard[]
  lost_reasons: { code: string; n: number; total: number }[]
  stuck_days: number
}

// ===========================================================================
// Kimlik (auth) — foydalanuvchilar TENDER-AI da, ERP faqat tekshiradi
// ===========================================================================

/** Huquq darajasi (`api/erp/perm.py`): to'liq / faqat o'ziniki / faqat
 *  o'qish / yo'q. */
export type PermLevel = 'full' | 'own' | 'read' | null

export interface AuthUser {
  id: number
  username: string
  full_name: string
  role: 'admin' | 'rahbar' | 'menejer' | 'broker'
  role_label: Nullable<string>
  /** Serverdagi HUQUQLAR MATRITSASINING shu odam uchun kesimi
   *  (`GET /erp/auth/me`). Interfeys tugmani shundan hal qiladi —
   *  o'z ro'yxatini tutmaydi. */
  perms?: Record<string, PermLevel>
  /** erp.broker.id bilan bog'lanish (bo'lsa) */
  broker_id: Nullable<number>
  email: Nullable<string>
  active: boolean
  last_login_at: Nullable<string>
  /** Hodim ismi (hisob hodimga bog'langan bo'lsa) */
  broker_name?: Nullable<string>
  /** CSRF tokeni (auth-4). Sir EMAS: o'zgartiruvchi so'rovlarga
   *  `X-CSRF-Token` sarlavhasi sifatida qo'yiladi. */
  csrf?: string
}

/** `broker_name` — hisob hodimga bog'langan bo'lsa o'sha hodimning ismi.
 *  Kartalarda va tarixda AYNAN shu ism yoziladi (`actor()`). */
// ===========================================================================
// OMBOR (5B-1) — qoldiqning egasi ERP
// ===========================================================================
export interface StockMove {
  id: number
  product_id: number
  product_name: string
  unit: Nullable<string>
  kind: 'opening' | 'in' | 'out' | 'adjust'
  kind_label: Nullable<string>
  /** ISHORALI: kirim +, chiqim - (qoldiq = yig'indi) */
  qty: number
  opportunity_id: Nullable<number>
  opportunity_name: Nullable<string>
  doc_ref: Nullable<string>
  note: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
}

export interface StockBalance {
  product_id: number
  product_name: string
  unit: Nullable<string>
  /** JISMONIY qoldiq (harakatlar yig'indisi) */
  qty: number
  /** Kartalarga ajratilgani — qoldiqni kamaytirmaydi */
  reserved: number
  /** qty - reserved. "Yetadimi?" savoliga javob beradigan son */
  available: number
  reserve_count: number
  updated_at: Nullable<string>
  move_count: number
  /** Mahsulot tender-ai katalogida hali bormi (jurnal baribir qoladi) */
  in_catalog: boolean
  /** Tender-AI ga import qilingan ESKI qoldiq — solishtirish uchun */
  import_qty: Nullable<number>
  import_at: Nullable<string>
}

export interface StockList {
  items: StockBalance[]
  kinds: { code: string; label: string }[]
  reserve_states: { code: string; label: string }[]
  /** Qoldig'i manfiy bo'lib qolgan mahsulotlar */
  negative: number[]
  /** Jismonan bor, lekin hammasi band bo'lib qolganlar */
  over_reserved: number[]
}

/** "Shu karta uchun ajratildi". Kartaning statusiga bog'langan:
 *  yutilganda chiqimga aylanadi, yutqazilganda bo'shaydi. */
export interface StockReserve {
  id: number
  opportunity_id: number
  opportunity_name: Nullable<string>
  opportunity_status: Nullable<string>
  product_id: number
  product_name: string
  unit: Nullable<string>
  qty: number
  status: 'held' | 'consumed' | 'released'
  status_label: Nullable<string>
  /** Sarflanganda yozilgan chiqim harakati */
  move_id: Nullable<number>
  note: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
  closed_at: Nullable<string>
  closed_by: Nullable<string>
}

/** Tender pozitsiyasidan TAKLIF. Hech narsa avtomatik yozilmaydi —
 *  moslashuv nom bo'yicha ishlaydi va har doim ham to'g'ri emas. */
export interface ReserveSuggestion {
  product_id: number
  product_name: Nullable<string>
  unit: Nullable<string>
  /** Tenderdagi pozitsiya nomi — odam nimaga qarab tasdiqlashini bilsin */
  position: Nullable<string>
  position_amount: Nullable<string>
  /** Tenderga qancha kerak (tender-ai o'qigan) */
  required: Nullable<number>
  /** Shu kartaga allaqachon ajratilgani */
  held: number
  /** kerak - ajratilgan */
  suggest: Nullable<number>
  available: Nullable<number>
  qty: Nullable<number>
  status: Nullable<string>
  status_label: Nullable<string>
  reason: Nullable<string>
  can_reserve: boolean
}

export interface ReserveSuggestions {
  opportunity_id: number
  tender_id: number
  items: ReserveSuggestion[]
  /** Katalogda mos mahsulot topilmagan pozitsiyalar — bu ham ma'lumot */
  unmatched: { position: Nullable<string>; amount: Nullable<string>; reason: Nullable<string> }[]
  warning: Nullable<string>
  preliminary: Nullable<boolean>
}

export interface StockReserveInput {
  product_id: number
  qty: number
  note?: Nullable<string>
}

export interface StockProduct extends StockBalance {
  moves: StockMove[]
  reserves: StockReserve[]
}

export interface StockMoveInput {
  product_id: number
  kind: string
  /** MUSBAT son: ishorani server qo'yadi (`adjust` dan tashqari) */
  qty: number
  opportunity_id?: Nullable<number>
  doc_ref?: Nullable<string>
  note?: Nullable<string>
}

// ===========================================================================
// HISOB-FAKTURA (5B-2)
// ===========================================================================
/** Qator. QQS stavkasi HAR QATORDA — passport keyin o'zgarsa chiqarilgan
 *  hujjat buzilmasin. `net`/`vat`/`total` — SAQLANMAYDI, hisoblanadi. */
export interface InvoiceLine {
  id: number
  invoice_id: number
  pos: number
  product_id: Nullable<number>
  name: string
  unit: Nullable<string>
  qty: number
  price: number
  vat_rate: number
  note: Nullable<string>
  net: number
  vat: number
  total: number
}

export interface InvoicePayment {
  id: number
  invoice_id: number
  paid_at: Nullable<string>
  amount: number
  method: string
  method_label: Nullable<string>
  doc_ref: Nullable<string>
  note: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
}

/** Rekvizitlar SNAPSHOT: hujjat chiqarilgandan keyin passport o'zgarsa
 *  ham eski faktura o'zgarmaydi. */
export interface InvoiceParty {
  name: Nullable<string>
  inn: Nullable<string>
  address: Nullable<string>
  bank: Nullable<string>
  mfo: Nullable<string>
  account: Nullable<string>
  director: Nullable<string>
  vat_payer?: Nullable<boolean>
}

export interface Invoice {
  id: number
  opportunity_id: Nullable<number>
  opportunity_name: Nullable<string>
  contract_id: Nullable<number>
  contract_number: Nullable<string>
  client_id: number
  number: Nullable<string>
  issued_at: Nullable<string>
  due_at: Nullable<string>
  currency: string
  status: string
  status_label: Nullable<string>
  status_changed_at: Nullable<string>
  /** Faqat qoralama tahrirlanadi */
  editable: boolean
  client: InvoiceParty
  own: InvoiceParty
  note: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
  updated_at: Nullable<string>
  lines?: InvoiceLine[]
  payments?: InvoicePayment[]
  totals?: {
    net: number
    vat: number
    total: number
    /** Summa SO'Z bilan (bosma shakl uchun). Serverda yasaladi. */
    words?: string
  }
  paid?: number
  /** Jami - to'langan. "Qisman to'landi" STATUS emas, shu son */
  balance?: number
  fully_paid?: boolean
  /** Kartadan chiqarilganda: nima qayerdan to'ldirilgani */
  filled?: {
    lines: number
    /** Katalogda narxi topilmagan qatorlar soni */
    no_price: number
    from_contract: boolean
    contract_number: Nullable<string>
  }
}

export interface InvoiceInput {
  client_id?: number
  contract_id?: Nullable<number>
  opportunity_id?: Nullable<number>
  number?: Nullable<string>
  issued_at?: Nullable<string>
  due_at?: Nullable<string>
  currency?: Nullable<string>
  note?: Nullable<string>
}

export interface InvoiceLineInput {
  name: string
  qty: number
  price: number
  /** null = mijoz passportidan olinsin */
  vat_rate?: Nullable<number>
  unit?: Nullable<string>
  product_id?: Nullable<number>
  note?: Nullable<string>
}

export interface PaymentInput {
  paid_at: string
  amount: number
  method?: string
  doc_ref?: Nullable<string>
  note?: Nullable<string>
}

// --- DALOLATNOMA (akt) ---
// Faktura "qancha to'lash kerak" deydi, akt "bajarildi" deydi.
// Hisob-kitob fakturaniki bilan BIR XIL kod bilan bajariladi.
export interface ActParty {
  name: Nullable<string>
  inn: Nullable<string>
  address: Nullable<string>
  director: Nullable<string>
}

export interface Act {
  id: number
  invoice_id: Nullable<number>
  invoice_number: Nullable<string>
  contract_id: Nullable<number>
  contract_number: Nullable<string>
  opportunity_id: Nullable<number>
  opportunity_name: Nullable<string>
  client_id: number
  number: Nullable<string>
  act_date: Nullable<string>
  period_from: Nullable<string>
  period_to: Nullable<string>
  currency: string
  status: string
  status_label: Nullable<string>
  status_changed_at: Nullable<string>
  /** HUJJATDAGI imzo sanasi (tizim vaqtidan farqli) */
  signed_at: Nullable<string>
  editable: boolean
  client: ActParty
  own: ActParty
  note: Nullable<string>
  created_by: Nullable<string>
  created_at: Nullable<string>
  updated_at: Nullable<string>
  lines?: InvoiceLine[]
  totals?: { net: number; vat: number; total: number; words?: string }
  /** Fakturadan chiqarilganda: nechta qator ko'chirilgani */
  filled?: { lines: number; invoice_number: Nullable<string> }
}

/** Shartnoma ILOVASI (spetsifikatsiya). Shartnoma MATNI ERP da yo'q:
 *  huquqiy matn yurist ishi. Bu yerda faqat pozitsiyalar ro'yxati. */
export interface ContractSpecification {
  contract: Contract
  lines: InvoiceLine[]
  totals?: { net: number; vat: number; total: number; words?: string }
  client: InvoiceParty
  own: InvoiceParty
  /** 'invoice' — muzlatilgan, 'reserves' — hozirgi holat, 'none' — yo'q */
  source: 'invoice' | 'reserves' | 'none'
  /** Ma'lumot muzlatilganmi (faktura snapshotidanmi) */
  frozen: boolean
  invoice_number?: Nullable<string>
  /** Rezervdan olinganda: katalogda narxi topilmagan qatorlar soni */
  no_price?: number
}

export interface ActInput {
  client_id?: number
  invoice_id?: Nullable<number>
  number?: Nullable<string>
  act_date?: Nullable<string>
  period_from?: Nullable<string>
  period_to?: Nullable<string>
  note?: Nullable<string>
}

// --- FOYDA ---
// Daromad — fakturaning QQS SIZ summasi (QQS davlatniki, daromad emas).
// Tannarx — ombor harakatida MUZLATILGAN narx, joriy katalog narxi emas.
export interface ProfitRow {
  opportunity_id: number
  title: Nullable<string>
  status: string
  currency: string
  broker_name: Nullable<string>
  client_name: Nullable<string>
  /** QQS SIZ daromad */
  revenue: number
  /** QQS alohida: u daromad emas */
  vat: number
  invoices: number
  cost: number
  profit: number
  /** Daromad nol bo'lsa `null` — "0% foyda" degan yolg'on bo'lmasin */
  margin: Nullable<number>
  /** Tannarxi noma'lum chiqimlar soni */
  unknown_cost_moves: number
  cost_moves: number
  /** Hisob to'liqmi (noma'lum tannarx yo'qmi) */
  complete: boolean
}

/** Bitta valyuta kesimidagi yig'indi. Aralash valyuta QO'SHILMAYDI —
 *  kurs bo'yicha konvertatsiya yo'q va bo'lmaydi ham. */
export interface ProfitTotals {
  currency: string
  revenue: number
  cost: number
  profit: number
  margin: Nullable<number>
  cards: number
  unknown_cost_moves: number
  complete: boolean
}

export interface ProfitReport {
  items: ProfitRow[]
  /** Har valyuta uchun alohida qator, daromad bo'yicha kamayish tartibida */
  by_currency: ProfitTotals[]
  /** Umumiy yig'indi FAQAT hamma karta bitta valyutada bo'lganda; aks holda `null` */
  totals: Nullable<ProfitTotals>
  currencies: string[]
  mixed_currency: boolean
  unknown_cost_moves: number
  complete: boolean
}

// --- HUJJAT O'ZGARISHLARI (audit) ---
// Jurnalni BAZA yozadi (trigger), ERP kodi emas: qo'lda yozilgan SQL ham
// shu yerga tushadi. Shuning uchun bu ro'yxat "hujjat o'zgarmagan" degan
// gapning yagona mustaqil dalili.
export interface AuditRow {
  id: number
  doc_type: 'invoice' | 'act'
  doc_label: Nullable<string>
  doc_id: number
  entity: 'invoice' | 'act' | 'line' | 'payment'
  entity_label: Nullable<string>
  entity_id: Nullable<number>
  action: 'create' | 'update' | 'delete'
  action_label: Nullable<string>
  /** `update` da — ustun nomi; yaratish/o'chirishda `null` */
  field: Nullable<string>
  old_value: Nullable<string>
  new_value: Nullable<string>
  /** O'zgarish paytidagi hujjat holati */
  doc_status: Nullable<string>
  /** Hujjat MUZLATILGANDAN keyin o'zgarganmi */
  after_issue: boolean
  /** Kim; `null` = ERP dan tashqarida */
  actor: Nullable<string>
  outside_erp: boolean
  created_at: string
}

export interface AuditReport {
  items: AuditRow[]
  days: number
  summary: {
    n: number
    outside_erp: number
    after_issue: number
    last_at: Nullable<string>
  }
  /** Shubhali o'zgarish yo'qmi ("tekshirilmadi" bilan aralashmasin) */
  clean: boolean
}

// --- KIRISH URINISHLARI ---
// Bloklash shu JURNALDAN hisoblanadi (alohida hisoblagich ustuni yo'q),
// shuning uchun bu ro'yxat himoyaning haqiqiy holatini ko'rsatadi.
export interface LoginAttempt {
  id: number
  username: string
  /** Manzil noma'lum bo'lishi mumkin (masalan lokal chaqiruv) */
  ip: Nullable<string>
  ok: boolean
  user_agent: Nullable<string>
  created_at: string
  /** Bunday login BOR yoki YO'Q — yo'q login bilan urinish hujum izi */
  known_user: boolean
}

export interface StaffAccount {
  id: number
  username: string
  role: 'admin' | 'rahbar' | 'menejer' | 'broker'
  active: boolean
  last_login_at: Nullable<string>
}

/** TAHLIL bo'limi. Yiqilgan bo'lim YASHIRILMAYDI: `ok=false` va
 *  `xato` bilan keladi (Tender-AI `api/topshiriq.py`). */
export interface TahlilBolim<T = unknown> {
  ok: boolean
  data?: T
  xato?: string
}

/** TENDER-AI TAHLILI — qaror paytidagi SNAPSHOT
 *  (`erp.opportunity_analysis`). ERP uni qayta hisoblamaydi. */
export interface ErpTahlil {
  id: number
  topshiriq_id: Nullable<number>
  /** Qaror qanchalik ishonchli edi (Tender-AI lug'ati) */
  ishonch: Nullable<string>
  captured_at: Nullable<string>
  payload: Record<string, TahlilBolim | string | number>
}

/** BILDIRISHNOMA (`erp.notification`). Hodimga qaratilgan: Tender-AI
 *  dagi xabar KOMPANIYA darajasida va odamni bilmaydi. */
export interface ErpNotification {
  id: number
  kind: string
  /** Odam o'qiydigan tur nomi (serverdan) */
  kind_label: string
  matn: string
  opportunity_id: Nullable<number>
  opportunity_title: Nullable<string>
  /** `localhost` bo'lsa serverda YOZILMAYDI — buzuq havola bermaslik uchun */
  havola: Nullable<string>
  created_at: string
  read_at: Nullable<string>
}

/** TENDER-AI YO'NALTIRISH OQIMINING holati
 *  (`GET /erp/topshiriq/holat`). Sozlanmagan holat ham OCHIQ
 *  aytiladi: `sabab` — "nega hech narsa kelmayapti" degan savolga
 *  javob. */
export interface TopshiriqHolat {
  ready: boolean
  /** Biz qaysi Tender-AI ijarachisimiz. `null` — xarita yo'q */
  tai_company_id: Nullable<number>
  /** Fon tinglovchisi tirikmi (`LISTEN`) */
  tinglovchi: boolean
  oraliq: number
  oxirgi_xato: Nullable<string>
  sabab?: string
  kutayotgan?: number
  kartalar?: number
}

/** TIZIM SOZLAMASI (`erp.setting`). Ta'rifi va STANDART qiymati
 *  serverda (`api/erp/sozlama.py`) — ekran ro'yxatni o'zi tutmaydi. */
export interface Setting {
  key: string
  value: boolean
  /** Kod bergan standart qiymat (o'zgartirilmagan bo'lsa shu ishlaydi) */
  default: boolean
  label: string
  /** "Yoqsam nima o'zgaradi" — ekranda ko'rsatiladi */
  help: string
  /** Bazada yozuvi bormi (ya'ni standartdan o'zgartirilganmi) */
  changed: boolean
  updated_by: Nullable<string>
  updated_at: Nullable<string>
}

/** HODIM + unga bog'langan HISOB. Ikkisi alohida tushuncha: hodim
 *  tizimga kirmasligi ham mumkin, shuning uchun `user` — `null` bo'lishi
 *  mumkin. */
export interface StaffRow {
  id: number
  full_name: string
  email: Nullable<string>
  phone: Nullable<string>
  active: boolean
  /** Kartalar soni — hodimni faolsizlantirishdan oldin ko'rinsin */
  opp_count: number
  open_tasks: number
  user: Nullable<StaffAccount>
}

export interface StaffList {
  staff: StaffRow[]
  /** Hech qaysi hodimga bog'lanmagan hisoblar (masalan administrator) */
  unlinked_users: AuthUser[]
}

export interface UserInput {
  username?: string
  full_name?: string
  password?: string
  role?: string
  broker_id?: Nullable<number>
  email?: Nullable<string>
  active?: boolean
}

/** Sessiya tokeni bu yerda YO'Q — u `HttpOnly` cookie'da (auth-4). */
export interface LoginResult {
  expires_at: string
  csrf: string
  user: AuthUser
}

/** Kartaga biriktirilgan SABAB HUJJATI (24-patch).
 *
 *  Baytlar bu yerda YO'Q va bo'lmaydi ham: ro'yxat faqat metadata
 *  qaytaradi, fayl alohida so'rov bilan yuklab olinadi. */
export interface OpportunityFile {
  id: number
  opportunity_id: number
  fayl_nom: string
  mime: string
  hajm: number
  sha256: string
  izoh: string | null
  created_by: string | null
  created_at: string | null
}

/** "Yopilgan N kartadan M tasida sabab hujjati bor". */
export interface FaylQamrov {
  yopiq_n: number
  fayli_bor_n: number
  /** null = minimal namuna yig'ilmagan (10 dan kam) — foiz BERILMAYDI */
  foiz: number | null
  min_namuna: number
}
