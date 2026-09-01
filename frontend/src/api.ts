// ERP backend qatlami — barcha so'rovlar shu yerdan o'tadi.
// Bazaviy manzil .env dagi VITE_API_BASE dan (default: /api -> Vite proksisi).
//
// TENDER-AI GA TO'G'RIDAN-TO'G'RI MUROJAAT YO'Q. Cheklist va hujjat turlari
// ham ERP backendidan keladi — u tender-ai bilan server tomonda gaplashadi
// (api/tenderai.py). Shu tufayli brauzerda ikkinchi manzil, ikkinchi CORS
// sozlamasi va "qaysi biri yiqildi?" degan savol yo'q.
import type {
  ClientContactInput, ClientDocument, ClientDocumentInput, ClientFull,
  ClientInput, ClientRow, ComplianceResult, DocumentType, ErpBroker, ErpHealth,
  ErpMeta, ErpStats, ImportResult, Nullable, Opportunity, OpportunityInput,
  Contract, ContractInput, ContractRow, ContractStats, ErpAnalytics, MyTasks,
  OpportunityTask, OwnCompany, OwnCompanyInput, Submission, SubmissionInput,
  SubmissionPackage, TaskInput, TenderDiff, AuthUser, LoginResult,
  StaffList, UserInput, StockList, StockMove, StockMoveInput, StockProduct,
  StockReserve, StockReserveInput, Invoice, InvoiceInput, InvoiceLineInput,
  PaymentInput, ReserveSuggestions, Act, ActInput, ContractSpecification,
  AuditReport, AuditRow,
  LoginAttempt,
  ProfitReport, ProfitRow,
  Setting, ErpNotification, ErpTahlil, TopshiriqHolat,
} from './types'

const BASE = import.meta.env.VITE_API_BASE || '/api'

// --- KIMLIK (auth-4) ---------------------------------------------------------
// Sessiya tokeni `HttpOnly` COOKIE'da va bu fayl uni KO'RMAYDI. XSS bo'lsa
// ham JavaScript tokenni o'qiy olmaydi — `localStorage` da esa o'qirdi.
//
// Auth-3 gacha tokenni shu yerda saqlardik, chunki tender-ai interfeysi ERP
// API'siga to'g'ridan-to'g'ri murojaat qilardi (cookie cross-site bo'lardi).
// Endi u ERP ga umuman bormaydi — o'z backendidan o'qiydi — va to'siq
// yo'qoldi.
//
// COOKIE'NING NARXI — CSRF: brauzer cookie'ni HAR so'rovga o'zi qo'shadi.
// Shuning uchun o'zgartiruvchi so'rovlarga `X-CSRF-Token` sarlavhasi
// qo'yiladi; qiymati `HttpOnly BO'LMAGAN` cookie'dan (yoki `/auth/me`
// javobidan) olinadi va serverdagi SESSIYA qiymati bilan solishtiriladi.
const CSRF_COOKIE = 'erp_csrf'

/** CSRF tokeni. Cookie o'qilmasa (masalan cookie'lar bloklangan) — login
 *  yoki `/auth/me` javobidan saqlab qolingan nusxa ishlatiladi. */
let csrfFallback: string | null = null

export function setCsrf(token: string | null): void {
  csrfFallback = token
}

function readCsrf(): string | null {
  try {
    const hit = document.cookie.split('; ')
      .find((c) => c.startsWith(CSRF_COOKIE + '='))
    if (hit) return decodeURIComponent(hit.slice(CSRF_COOKIE.length + 1))
  } catch { /* document yo'q (SSR) — pastdagi nusxa ishlatiladi */ }
  return csrfFallback
}

/** Sessiya BOR-YO'QLIGI. Token o'qib bo'lmaydi (HttpOnly), shuning uchun
 *  "kirilganmi" degan savolga faqat server javob beradi — bu yerda esa
 *  oldingi urinish natijasi saqlanadi: sahifa ochilganda kirish ekrani
 *  behuda chaqnab ketmasin. */
const SEEN_KEY = 'tender-erp:seen'

export function getToken(): string | null {
  // Nomi eski chaqiruvchilar uchun saqlandi: endi u TOKEN emas, faqat
  // "avval kirgan edik" belgisi.
  try { return localStorage.getItem(SEEN_KEY) } catch { return null }
}

export function setToken(v: string | null): void {
  try {
    if (v) localStorage.setItem(SEEN_KEY, '1')
    else localStorage.removeItem(SEEN_KEY)
  } catch { /* localStorage yopiq — zarari yo'q, faqat chaqnash bo'ladi */ }
}

/** 401 kelganda chaqiriladi: ilova kirish ekraniga qaytadi. */
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn
}

/** Xato + STRUKTURALI `detail`: 409 da mavjud yozuvning id si keladi
 *  ({message, opportunity_id} yoki {message, client_id}) va interfeys unga
 *  havola quradi. Oddiy `Error` da bu ma'lumot yo'qolardi. */
export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** FastAPI xato tanasini o'qiladigan matnga aylantiradi.
 *  400/404/503 -> detail satr yoki {message}; 422 -> [{loc, msg}, ...]. */
function errMatn(detail: unknown): string {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((e: { loc?: (string | number)[]; msg?: string }) => {
      const maydon = (e.loc || []).filter((x) => x !== 'body').join('.')
      const msg = String(e.msg || '').replace(/^Value error,\s*/, '')
      return maydon ? `${maydon}: ${msg}` : msg
    }).join('; ')
  }
  const m = (detail as { message?: string }).message
  return m || String(detail)
}

type Params = Record<string, string | number | boolean | null | undefined>

async function request<T>(
  method: string, path: string,
  { params, body }: { params?: Params; body?: unknown } = {},
): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue
      url.searchParams.set(k, String(v))
    }
  }
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  // CSRF faqat O'ZGARTIRUVCHI so'rovlarda: GET da server ham tekshirmaydi.
  if (method !== 'GET' && method !== 'HEAD') {
    const csrf = readCsrf()
    if (csrf) headers['X-CSRF-Token'] = csrf
  }

  // `credentials: 'include'` — sessiya cookie'si yuborilishi uchun SHART.
  const opts: RequestInit = { method, headers, credentials: 'include' }
  if (body !== undefined) opts.body = JSON.stringify(body)

  const res = await fetch(url, opts)
  if (!res.ok) {
    let detail: unknown = null
    let text = res.statusText
    try {
      const b = await res.json()
      detail = b.detail
      text = errMatn(b.detail) || text
    } catch { /* JSON emas */ }
    // 401 — sessiya tugagan yoki bekor qilingan: ilova kirish ekraniga
    // qaytadi. Har komponent buni alohida ushlashi shart emas.
    if (res.status === 401) { setToken(null); onUnauthorized?.() }
    throw new ApiError(`${res.status}: ${text}`, res.status, detail)
  }
  if (res.status === 204) return null as T
  const text = await res.text()
  return (text ? JSON.parse(text) : null) as T
}

export const api = {
  // --- kimlik ---
  login: async (username: string, password: string) => {
    // Javobda TOKEN YO'Q — u `HttpOnly` cookie'da. Faqat foydalanuvchi
    // va CSRF tokeni qaytadi.
    const r = await request<LoginResult>('POST', '/erp/auth/login',
      { body: { username, password } })
    setCsrf(r.csrf)
    setToken('1')
    return r.user
  },
  logout: async () => {
    try { await request<{ ok: boolean }>('POST', '/erp/auth/logout') } finally {
      setToken(null); setCsrf(null)
    }
  },
  me: async () => {
    // Sahifa yangilanganda CSRF tokeni shu yerdan tiklanadi.
    const u = await request<AuthUser>('GET', '/erp/auth/me')
    if (u.csrf) setCsrf(u.csrf)
    return u
  },

  health: () => request<ErpHealth>('GET', '/health'),
  meta: () => request<ErpMeta>('GET', '/erp/meta'),

  // --- opportunity pipeline ---
  opportunities: (params?: Params) =>
    request<Opportunity[]>('GET', '/erp/opportunities', { params }),
  opportunity: (id: number) => request<Opportunity>('GET', `/erp/opportunities/${id}`),
  updateOpportunity: (id: number, body: OpportunityInput) =>
    request<Opportunity>('PUT', `/erp/opportunities/${id}`, { body }),
  setStatus: (id: number, body: {
    status: string; changed_by?: Nullable<string>; note?: Nullable<string>
    lost_reason?: Nullable<string>
  }) => request<Opportunity>('PATCH', `/erp/opportunities/${id}/status`, { body }),

  // --- shartnoma va bizning rekvizitlar (5A-1) ---
  ownCompany: () => request<OwnCompany>('GET', '/erp/own-company'),
  saveOwnCompany: (body: OwnCompanyInput) =>
    request<OwnCompany>('PUT', '/erp/own-company', { body }),
  contractList: (params?: Params) =>
    request<ContractRow[]>('GET', '/erp/contracts', { params }),
  contractStats: () => request<ContractStats>('GET', '/erp/contracts/stats'),
  contracts: (oppId: number) =>
    request<Contract[]>('GET', `/erp/opportunities/${oppId}/contracts`),
  addContract: (oppId: number, body: ContractInput) =>
    request<Contract[]>('POST', `/erp/opportunities/${oppId}/contracts`, { body }),
  updateContract: (contractId: number, body: ContractInput) =>
    request<Contract[]>('PUT', `/erp/contracts/${contractId}`, { body }),
  setContractStatus: (contractId: number, status: string) =>
    request<Contract[]>('PATCH', `/erp/contracts/${contractId}/status`,
      { params: { status } }),

  // --- taklif va topshirish (4-bosqich) ---
  submissionPackage: (oppId: number) =>
    request<SubmissionPackage>('GET', `/erp/opportunities/${oppId}/submission`),
  submit: (oppId: number, body: SubmissionInput) =>
    request<{ submission: Submission; opportunity: Opportunity }>(
      'POST', `/erp/opportunities/${oppId}/submission`, { body }),
  submissions: (oppId: number) =>
    request<Submission[]>('GET', `/erp/opportunities/${oppId}/submissions`),

  // --- vazifalar (3-bosqich). Javob har doim BUTUN ro'yxat. ---
  tasks: (oppId: number) =>
    request<OpportunityTask[]>('GET', `/erp/opportunities/${oppId}/tasks`),
  addTask: (oppId: number, body: TaskInput) =>
    request<OpportunityTask[]>('POST', `/erp/opportunities/${oppId}/tasks`, { body }),
  updateTask: (taskId: number, body: TaskInput) =>
    request<OpportunityTask[]>('PUT', `/erp/tasks/${taskId}`, { body }),
  setTaskDone: (taskId: number, done: boolean) =>
    request<OpportunityTask[]>('PATCH', `/erp/tasks/${taskId}/done`, { params: { done } }),
  deleteTask: (taskId: number) =>
    request<OpportunityTask[]>('DELETE', `/erp/tasks/${taskId}`),
  myTasks: (params?: Params) => request<MyTasks>('GET', '/erp/my-tasks', { params }),
  /** Snapshot jonli tenderdan farq qiladimi (snapshot o'zgarmaydi). */
  tenderDiff: (oppId: number) =>
    request<TenderDiff>('GET', `/erp/opportunities/${oppId}/tender-diff`),
  tenderOpportunities: (tenderId: number) =>
    request<Opportunity[]>('GET', `/erp/tenders/${tenderId}/opportunities`),
  takeTender: (tenderId: number, body: OpportunityInput) =>
    request<Opportunity>('POST', `/erp/tenders/${tenderId}/take`, { body }),

  // --- lug'atlar ---
  brokers: () => request<ErpBroker[]>('GET', '/erp/brokers'),
  addBroker: (body: { full_name: string; email?: Nullable<string>; phone?: Nullable<string> }) =>
    request<ErpBroker>('POST', '/erp/brokers', { body }),

  // --- ombor (5B-1): qoldiqning egasi ERP ---
  // Qoldiq alohida ustunda saqlanmaydi — u harakatlar yig'indisi.
  stock: (params?: Params) => request<StockList>('GET', '/erp/stock', { params }),
  stockProduct: (id: number) => request<StockProduct>('GET', `/erp/stock/${id}`),
  stockMoves: (params?: Params) =>
    request<StockMove[]>('GET', '/erp/stock/moves', { params }),
  addStockMove: (body: StockMoveInput) =>
    request<StockMove & { balance: number; warning: Nullable<string> }>(
      'POST', '/erp/stock/moves', { body }),
  seedOpening: () =>
    request<{ created: number[]; skipped: number[] }>(
      'POST', '/erp/stock/seed-opening'),

  // --- rezerv: "shu karta uchun ajratildi" ---
  // Qoldiqni kamaytirmaydi, MAVJUD miqdorni kamaytiradi. Yopilishi
  // kartaning statusiga bog'langan — qo'lda faqat bo'shatish mumkin.
  reserves: (params?: Params) =>
    request<StockReserve[]>('GET', '/erp/reserves', { params }),
  addReserve: (oppId: number, body: StockReserveInput) =>
    request<StockReserve & { balance: number; available: number; warning: Nullable<string> }>(
      'POST', `/erp/opportunities/${oppId}/reserves`, { body }),
  releaseReserve: (reserveId: number) =>
    request<StockReserve>('DELETE', `/erp/reserves/${reserveId}`),
  /** Tender pozitsiyalaridan taklif. FAQAT ro'yxat — yozmaydi. */
  reserveSuggestions: (oppId: number) =>
    request<ReserveSuggestions>('GET', `/erp/opportunities/${oppId}/reserve-suggestions`),
  /** Tasdiqlangan takliflarni rezervga aylantirish (bir necha qator) */
  addReserves: (oppId: number, rows: StockReserveInput[]) =>
    request<{ count: number; failed: number; errors: { product_id: number; error: string }[] }>(
      'POST', `/erp/opportunities/${oppId}/reserves/bulk`, { body: rows }),

  // --- hisob-faktura (5B-2) ---
  // Summalar SAQLANMAYDI: `totals` har javobda qatorlardan hisoblanadi.
  // Eksport endpointi bor, lekin format sozlanmagan (501) — shuning
  // uchun interfeys tugmani ko'rsatmaydi.
  invoices: (params?: Params) => request<Invoice[]>('GET', '/erp/invoices', { params }),
  invoice: (id: number) => request<Invoice>('GET', `/erp/invoices/${id}`),
  invoiceStats: () => request<{
    by_status: { code: string; label: string; count: number; total: number }[]
    count: number
    debt: number
  }>('GET', '/erp/invoices/stats'),
  createInvoice: (body: InvoiceInput) =>
    request<Invoice>('POST', '/erp/invoices', { body }),
  /** Kartadan: qatorlar ajratilgan tovardan to'ldiriladi (`filled`) */
  invoiceFromOpportunity: (oppId: number, body: InvoiceInput) =>
    request<Invoice>('POST', `/erp/opportunities/${oppId}/invoice`, { body }),
  updateInvoice: (id: number, body: InvoiceInput) =>
    request<Invoice>('PUT', `/erp/invoices/${id}`, { body }),
  setInvoiceStatus: (id: number, status: string) =>
    request<Invoice>('PUT', `/erp/invoices/${id}/status`, { body: { status } }),
  addInvoiceLine: (id: number, body: InvoiceLineInput) =>
    request<Invoice>('POST', `/erp/invoices/${id}/lines`, { body }),
  deleteInvoiceLine: (id: number, lineId: number) =>
    request<Invoice>('DELETE', `/erp/invoices/${id}/lines/${lineId}`),
  addPayment: (id: number, body: PaymentInput) =>
    request<Invoice>('POST', `/erp/invoices/${id}/payments`, { body }),
  deletePayment: (paymentId: number) =>
    request<Invoice>('DELETE', `/erp/payments/${paymentId}`),

  /** Shartnoma ilovasi (spetsifikatsiya). Shartnoma MATNI ERP da yo'q. */
  contractSpecification: (contractId: number) =>
    request<ContractSpecification>(
      'GET', `/erp/contracts/${contractId}/specification`),

  // --- foyda ---
  // Umumiy hisobot RAHBAR huquqini talab qiladi; bitta kartaniki esa
  // ustida ishlayotgan odamga ham ochiq.
  profit: (params?: Params) => request<ProfitReport>('GET', '/erp/profit', { params }),
  loginAttempts: (params?: Params) =>
    request<LoginAttempt[]>('GET', '/erp/auth/attempts', { params }),
  /** Pul hujjatlari o'zgarishlari jurnali (rahbar) */
  audit: (params?: Params) =>
    request<AuditReport>('GET', '/erp/audit', { params }),
  /** Bitta hujjatning butun tarixi */
  docAudit: (docType: 'invoice' | 'act', docId: number) =>
    request<AuditRow[]>('GET', `/erp/audit/${docType}/${docId}`),
  cardProfit: (oppId: number) =>
    request<ProfitRow>('GET', `/erp/opportunities/${oppId}/profit`),

  // --- dalolatnoma (akt) ---
  // Qatorlar fakturadan KO'CHIRILADI (bog'lanmaydi): faktura keyin
  // bekor qilinishi mumkin, akt esa bajarilgan ishning dalili.
  acts: (params?: Params) => request<Act[]>('GET', '/erp/acts', { params }),
  actFromInvoice: (invoiceId: number, body: ActInput) =>
    request<Act>('POST', `/erp/invoices/${invoiceId}/act`, { body }),
  setActStatus: (id: number, status: string, signedAt?: string | null) =>
    request<Act>('PUT', `/erp/acts/${id}/status`,
      { body: { status, signed_at: signedAt ?? null } }),

  // --- hodimlar va hisoblar (admin) ---
  // Hodim (`erp.broker`) va hisob (`erp.app_user`) ALOHIDA tushuncha,
  // lekin ekran bitta: "kimga hisob ochilgan?" degan savol bir qarashda
  // ko'rinsin.
  staff: () => request<StaffList>('GET', '/erp/staff'),
  updateBroker: (id: number, body: { full_name: string; email?: Nullable<string>; phone?: Nullable<string>; active?: boolean }) =>
    request<ErpBroker>('PUT', `/erp/brokers/${id}`, { body }),
  createUser: (body: UserInput) => request<AuthUser>('POST', '/erp/users', { body }),
  updateUser: (id: number, body: UserInput) =>
    request<AuthUser>('PUT', `/erp/users/${id}`, { body }),
  /** Parolni almashtirish (auth-6).
   *  `currentPassword` — O'ZINIKINI almashtirayotganda MAJBURIY; admin
   *  boshqaning parolini tiklayotganda berilmaydi. Javobda yopilgan
   *  boshqa sessiyalar soni qaytadi. */
  setUserPassword: (id: number, password: string, currentPassword?: string) =>
    request<{ ok: boolean; closed_sessions: number }>(
      'PUT', `/erp/users/${id}/password`,
      { body: { password, current_password: currentPassword } }),
  roles: () => request<{ roles: { code: string; label: string }[] }>('GET', '/erp/auth/roles'),

  /** "Bu ish menga to'g'ri kelmadi" — MENEJERGA so'rov. Broker
   *  kartani o'zi o'tkaza olmaydi (huquqlar matritsasi), lekin
   *  so'rovi tarixda qoladi. */
  requestReassign: (oppId: number, izoh: string) =>
    request<{ ok: boolean; xabar_ketdi: number }>(
      'POST', `/erp/opportunities/${oppId}/taqsimlash-sorovi`,
      { body: { izoh } }),

  /** Tender-AI tahlili — SNAPSHOT (eng yangisi birinchi). ERP uni
   *  qayta hisoblamaydi: qoidalar Tender-AI da. */
  tahlil: (oppId: number) =>
    request<{ items: ErpTahlil[] }>(
      'GET', `/erp/opportunities/${oppId}/tahlil`),

  // --- bildirishnomalar (o'ziniki) ---
  // HUQUQ yo'q: har kim faqat o'zinikini ko'radi va `app_user_id`
  // sessiyadan olinadi (so'rovdan emas).
  notifications: (onlyUnread = false) =>
    request<{ ready: boolean; items: ErpNotification[]; unread: number }>(
      'GET', '/erp/notifications', { params: { only_unread: onlyUnread } }),
  readNotifications: (ids?: number[]) =>
    request<{ belgilandi: number; unread: number }>(
      'POST', '/erp/notifications/read', { body: { ids: ids ?? null } }),

  // --- Tender-AI yo'naltirish oqimi (admin) ---
  // Xarita OPERATOR qarori: qaysi Tender-AI ijarachisi ekanimiz
  // taxmin qilinmaydi (`api/erp/topshiriq.py`).
  topshiriqHolat: () =>
    request<TopshiriqHolat>('GET', '/erp/topshiriq/holat'),
  setTaiXarita: (taiCompanyId: number | null) =>
    request<TopshiriqHolat>('PUT', '/erp/topshiriq/xarita',
      { body: { tai_company_id: taiCompanyId } }),
  topshiriqSync: () =>
    request<{ holat: string; yaratildi?: number; bekor?: number
              xato?: number }>('POST', '/erp/topshiriq/sync'),

  // --- tizim sozlamalari (admin) ---
  // Ro'yxat SERVERDAN keladi: kalitlar, standart qiymatlar va izohlar
  // `api/erp/sozlama.py` da. Ekran ikkinchi nusxa tutmaydi.
  settings: () => request<{ ready: boolean; settings: Setting[] }>(
    'GET', '/erp/settings'),
  setSetting: (key: string, value: boolean) =>
    request<Setting>('PUT', `/erp/settings/${key}`, { body: { value } }),

  // --- mijoz korxonalar ---
  clients: (params?: Params) => request<ClientRow[]>('GET', '/erp/clients', { params }),
  client: (id: number) => request<ClientFull>('GET', `/erp/clients/${id}`),
  createClient: (body: ClientInput) => request<ClientFull>('POST', '/erp/clients', { body }),
  updateClient: (id: number, body: ClientInput) =>
    request<ClientFull>('PUT', `/erp/clients/${id}`, { body }),
  addContact: (clientId: number, body: ClientContactInput) =>
    request<ClientFull>('POST', `/erp/clients/${clientId}/contacts`, { body }),
  updateContact: (contactId: number, body: ClientContactInput) =>
    request<ClientFull>('PUT', `/erp/client-contacts/${contactId}`, { body }),
  deleteContact: (contactId: number) =>
    request<ClientFull>('DELETE', `/erp/client-contacts/${contactId}`),
  clientDocuments: (clientId: number) =>
    request<ClientDocument[]>('GET', `/erp/clients/${clientId}/documents`),
  addClientDocument: (clientId: number, body: ClientDocumentInput) =>
    request<ClientDocument>('POST', `/erp/clients/${clientId}/documents`, { body }),
  updateClientDocument: (docId: number, body: ClientDocumentInput) =>
    request<ClientDocument>('PUT', `/erp/client-documents/${docId}`, { body }),
  deleteClientDocument: (docId: number) =>
    request<null>('DELETE', `/erp/client-documents/${docId}`),

  /** Shablonni yuklab olish. `<a href>` ISHLAMAYDI: endpoint himoyalangan
   *  va oddiy havola `Authorization` sarlavhasini yubormaydi. Shuning uchun
   *  fayl `fetch` bilan olinadi va brauzerga blob sifatida beriladi. */
  downloadClientTemplate: async (clientId: number, fmt: 'xlsx' | 'csv' = 'xlsx') => {
    const url = new URL(
      `${BASE}/erp/clients/${clientId}/documents/template?fmt=${fmt}`,
      window.location.origin)
    // GET — CSRF kerak emas, lekin cookie SHART.
    const res = await fetch(url, { credentials: 'include' })
    if (!res.ok) throw new ApiError(`${res.status}: shablon olinmadi`, res.status, null)
    const blob = await res.blob()
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = `mijoz_hujjatlari_shablon.${fmt}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(href)
  },

  /** To'ldirilgan shablonni yuklash. YAGONA `FormData` chaqiruvi: `request()`
   *  JSON bilan ishlaydi, fayl uchun `Content-Type` ni BRAUZER o'zi qo'yishi
   *  kerak (boundary bilan) — qo'lda qo'yilsa yuklash buziladi. */
  importClientDocuments: async (clientId: number, file: File, dryRun: boolean) => {
    const fd = new FormData()
    fd.append('file', file)
    const url = new URL(
      `${BASE}/erp/clients/${clientId}/documents/import?dry_run=${dryRun}`,
      window.location.origin)
    // FormData: `Content-Type` ni brauzer o'zi qo'yadi, biz faqat
    // CSRF sarlavhasini qo'shamiz.
    const csrf = readCsrf()
    const res = await fetch(url, {
      method: 'POST', body: fd, credentials: 'include',
      headers: csrf ? { 'X-CSRF-Token': csrf } : undefined,
    })
    const text = await res.text()
    const data = text ? JSON.parse(text) : null
    if (!res.ok) {
      throw new ApiError(`${res.status}: ${errMatn(data?.detail) || res.statusText}`,
        res.status, data?.detail)
    }
    return data as ImportResult
  },

  // --- tender-ai bilan integratsiya (server orqali) ---
  documentTypes: () => request<DocumentType[]>('GET', '/erp/document-types'),
  compliance: (oppId: number) =>
    request<ComplianceResult>('GET', `/erp/opportunities/${oppId}/compliance`),

  // --- hisobot ---
  stats: (params?: Params) => request<ErpStats>('GET', '/erp/stats', { params }),
  // Tahlil: bosqich vaqtlari, voronka, qotib qolganlar. Yangi jadval
  // YO'Q — hammasi `opportunity_history` dan.
  analytics: (params?: Params) =>
    request<ErpAnalytics>('GET', '/erp/analytics', { params }),
}
