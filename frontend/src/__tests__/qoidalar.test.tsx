import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AuthUser } from '@/types'

// INTERFEYS SINOVI — komponentlarni emas, QARORLARNI tekshiradi.
//
// NEGA BU FAYL BOR: backendda 875 tekshiruv bor, frontendda esa
// bittasi ham yo'q edi. Ya'ni "aralash valyutada summa ko'rsatilmaydi",
// "hisob to'liq emas deb aytiladi", "brokerga pul bloklari
// ko'rinmaydi" degan qoidalar SERVERDA tekshirilardi, EKRANDA esa
// hech kim tekshirmasdi. Bir noto'g'ri `&&` va qoida jimgina yo'qoladi.
//
// NIMA TEKSHIRILMAYDI: ranglar, oraliqlar, joylashuv. Ular ko'z bilan
// ko'riladi va sinov ularni ushlashga urinsa, har dizayn tuzatishida
// yiqilib, foydadan ko'ra ko'proq to'sqinlik qilardi.
//
// `api` MODULI ALMASHTIRILADI: sinov tarmoqqa ham, bazaga ham
// chiqmaydi — u faqat "shu ma'lumot kelganda ekranda nima yozilishi
// kerak" degan savolga javob beradi.

// jsdom da `ResizeObserver` yo'q, Radix Slider esa uni talab qiladi
// (karta oynasidagi "yutish ehtimoli"). Stub bo'lmasa sinov komponentni
// emas, brauzer API'sining yo'qligini tekshirgan bo'lardi.
// jsdom da `scrollIntoView` yo'q. Muloqot lentasi yangi xabar
// kelganda pastga suriladi — usiz sinov komponentni emas, brauzer
// API'sining yo'qligini tekshirgan bo'lardi (ResizeObserver bilan
// bir xil sabab).
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {}
}

if (!('ResizeObserver' in globalThis)) {
  ;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver =
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
}

const api = {
  stats: vi.fn(), analytics: vi.fn(), myTasks: vi.fn(), invoiceStats: vi.fn(),
  profit: vi.fn(), audit: vi.fn(), opportunities: vi.fn(),
  cardProfit: vi.fn(), setUserPassword: vi.fn(), loginAttempts: vi.fn(),
  stock: vi.fn(), stockProduct: vi.fn(), seedOpening: vi.fn(),
  tahlil: vi.fn(),
  // Karta va mijoz oynalari (ular ichidagi bloklar ham chaqiradi).
  opportunity: vi.fn(), tenderDiff: vi.fn(), tasks: vi.fn(),
  reserves: vi.fn(), invoices: vi.fn(), client: vi.fn(),
  acts: vi.fn(), actFromInvoice: vi.fn(), setActStatus: vi.fn(),
  // Sabab hujjati (24-patch)
  oppFiles: vi.fn(), addOppFile: vi.fn(), deleteOppFile: vi.fn(),
  downloadOppFile: vi.fn(),
  // Muloqot (25-patch)
  chats: vi.fn(), chatMessages: vi.fn(), chatSend: vi.fn(),
  chatEdit: vi.fn(), chatDelete: vi.fn(), chatMembers: vi.fn(),
  chatMemberAdd: vi.fn(), chatMemberRemove: vi.fn(),
  chatRead: vi.fn(), oppChat: vi.fn(),
}
vi.mock('@/api', () => ({ api, ApiError: class extends Error {} }))

const { default: Dashboard } = await import('../components/erp/Dashboard')
const { default: ProfitLine } = await import('../components/erp/ProfitLine')
const { default: ProfitPanel } = await import('../components/erp/ProfitPanel')
const { default: AuditPanel } = await import('../components/erp/AuditPanel')
const { default: MyPasswordPanel } =
  await import('../components/erp/MyPasswordPanel')
const { default: StockPage } = await import('../components/erp/StockPage')
const { default: MyTasksPage } = await import('../components/erp/MyTasksPage')
const { default: TahlilPanel } = await import('../components/erp/TahlilPanel')
const { default: OpportunityCard } =
  await import('../components/erp/OpportunityCard')
const { default: ClientCard } = await import('../components/erp/ClientCard')
const { default: SababFayl } = await import('../components/erp/SababFayl')
const { default: Muloqot } = await import('../components/erp/Muloqot')
const { default: ActPanel } = await import('../components/erp/ActPanel')
const { setPerms } = await import('../components/erp/erpShared')

const MANAGER: AuthUser = {
  id: 1, username: 'a', full_name: 'A', role: 'admin',
  role_label: 'Administrator', broker_id: null, broker_name: null,
  email: null, active: true, last_login_at: null,
}
const BROKER: AuthUser = { ...MANAGER, role: 'broker', role_label: 'Broker' }
const MENEJER: AuthUser = { ...MANAGER, role: 'menejer', role_label: 'Menejer' }

const EMPTY_STATS = {
  currency: 'UZS', currencies: ['UZS'], mixed_currency: false,
  total: 4, open: 2, open_total: 1000000, submitted: 1, won: 1,
  won_total: 5000000, lost: 0, rejected: 0, win_rate: 100,
  by_status: [{ code: 'new', label: 'Yangi', n: 2, total: 1000000 }],
  by_broker: [], by_client: [], upcoming: [], monthly: [], upcoming_days: 7,
}

// TOZALASH QO'LDA: `globals: false` bo'lgani uchun Testing Library o'z
// `afterEach` ini avtomatik ulay olmaydi. Usiz oldingi sinovning
// ekrani DOM da qolib, "bir nechta bir xil tugma topildi" degan
// aldamchi xato chiqadi.
afterEach(() => { cleanup(); setPerms(null) })

beforeEach(() => {
  vi.clearAllMocks()
  const never = new Promise(() => {})
  for (const f of Object.values(api)) f.mockReturnValue(never)
})

// ---------------------------------------------------------------------------
describe('Foyda: hisob to‘liq bo‘lmasa OCHIQ aytiladi', () => {
  it('noma’lum tannarx bo‘lsa ogohlantirish chiqadi', async () => {
    api.cardProfit.mockResolvedValue({
      opportunity_id: 1, title: 'X', status: 'won', currency: 'UZS',
      broker_name: null, client_name: null,
      revenue: 2000000, vat: 240000, invoices: 1,
      cost: 0, profit: 2000000, margin: 100,
      unknown_cost_moves: 3, cost_moves: 3, complete: false,
    })
    render(<ProfitLine oppId={1} />)
    // Raqamning o'zi emas, SABABI ham yozilishi kerak.
    expect(await screen.findByText(/hisob to'liq emas/i)).toBeTruthy()
    expect(screen.getByText(/haqiqiy foyda bundan kam/i)).toBeTruthy()
  })

  it('QQS daromaddan ALOHIDA ko‘rsatiladi', async () => {
    api.cardProfit.mockResolvedValue({
      opportunity_id: 1, title: 'X', status: 'won', currency: 'UZS',
      broker_name: null, client_name: null,
      revenue: 2000000, vat: 240000, invoices: 1,
      cost: 1200000, profit: 800000, margin: 40,
      unknown_cost_moves: 0, cost_moves: 1, complete: true,
    })
    render(<ProfitLine oppId={1} />)
    expect(await screen.findByText(/QQS siz/i)).toBeTruthy()
    // QQS daromadga QO'SHILMAY, yonida alohida turadi.
    expect(screen.getAllByText(/\+ QQS/i).length).toBeGreaterThan(0)
  })

  it('pul harakati bo‘lmasa blok UMUMAN ko‘rsatilmaydi', async () => {
    api.cardProfit.mockResolvedValue({
      opportunity_id: 1, title: 'X', status: 'new', currency: 'UZS',
      broker_name: null, client_name: null,
      revenue: 0, vat: 0, invoices: 0, cost: 0, profit: 0, margin: null,
      unknown_cost_moves: 0, cost_moves: 0, complete: true,
    })
    const { container } = render(<ProfitLine oppId={1} />)
    // Nol-nol-nol qator hech narsa aytmaydi.
    await new Promise((r) => setTimeout(r, 0))
    expect(container.textContent).toBe('')
  })
})

// ---------------------------------------------------------------------------
describe('Aralash valyuta QO‘SHILMAYDI', () => {
  it('umumiy yig‘indi berilmaydi va SABABI yoziladi', async () => {
    api.profit.mockResolvedValue({
      items: [{ opportunity_id: 1, title: 'A', status: 'won', currency: 'UZS',
        broker_name: null, client_name: null, revenue: 1e7, vat: 0,
        invoices: 1, cost: 0, profit: 1e7, margin: 100,
        unknown_cost_moves: 0, cost_moves: 0, complete: true }],
      by_currency: [
        { currency: 'UZS', revenue: 1e7, cost: 0, profit: 1e7, margin: 100,
          cards: 1, unknown_cost_moves: 0, complete: true },
        { currency: 'USD', revenue: 1200, cost: 0, profit: 1200, margin: 100,
          cards: 1, unknown_cost_moves: 0, complete: true },
      ],
      totals: null, currencies: ['UZS', 'USD'], mixed_currency: true,
      unknown_cost_moves: 0, complete: true,
    })
    render(<ProfitPanel onOpen={() => {}} />)
    expect(await screen.findByText(/valyutalar aralash/i)).toBeTruthy()
    // Har valyuta ALOHIDA qator bo'lib chiqadi.
    expect(screen.getByText('UZS')).toBeTruthy()
    expect(screen.getByText('USD')).toBeTruthy()
  })

  it('rahbar panelida aralashda pul yig‘indilari YASHIRILADI', async () => {
    api.stats.mockResolvedValue({
      ...EMPTY_STATS, currency: null, currencies: ['UZS', 'USD'],
      mixed_currency: true, open_total: null, won_total: null,
      by_status: [{ code: 'new', label: 'Yangi', n: 2, total: null }],
    })
    render(<Dashboard user={MANAGER} onOpenOpportunity={() => {}}
      onGo={() => {}} />)
    expect(await screen.findByText(/valyutalarida/i)).toBeTruthy()
    expect(screen.getByText(/sanoq esa to'g'ri qoladi/i)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
describe('Rol: broker kompaniya ko‘rsatkichlarini KO‘RMAYDI', () => {
  it('brokerga o‘z ishlari chiqadi, xato emas', async () => {
    api.myTasks.mockResolvedValue({
      broker_id: null, self_broker_id: null, days: 7,
      overdue: [], today: [], later: [], total: 0,
    })
    api.opportunities.mockResolvedValue([])
    render(<Dashboard user={BROKER} onOpenOpportunity={() => {}}
      onGo={() => {}} />)
    expect(await screen.findByText(/Ochiq kartalarim/i)).toBeTruthy()
    // Pul va audit so'rovlari UMUMAN yuborilmasligi kerak.
    expect(api.profit).not.toHaveBeenCalled()
    expect(api.audit).not.toHaveBeenCalled()
    expect(api.stats).not.toHaveBeenCalled()
  })

  // MENEJER — 17-patchda ajratilgan yangi rol. U kundalik ishning
  // egasi, ya'ni kompaniya ko'rsatkichini KO'RADI. Bu tekshiruv
  // aynan shuning uchun bor: rol qo'shilganda ekrandagi shart
  // (`roleAtLeast`) unutilsa, menejer brokerning ekranini olardi va
  // buni hech kim sezmasdi.
  it('menejerga ham kompaniya ko‘rsatkichlari so‘raladi', async () => {
    api.stats.mockResolvedValue(EMPTY_STATS)
    api.myTasks.mockResolvedValue({
      broker_id: null, self_broker_id: null, days: 7,
      overdue: [], today: [], later: [], total: 0,
    })
    render(<Dashboard user={MENEJER} onOpenOpportunity={() => {}}
      onGo={() => {}} />)
    await screen.findByText(/Yutish foizi/i)
    expect(api.profit).toHaveBeenCalled()
  })

  it('rahbarga kompaniya ko‘rsatkichlari so‘raladi', async () => {
    api.stats.mockResolvedValue(EMPTY_STATS)
    api.myTasks.mockResolvedValue({
      broker_id: null, self_broker_id: null, days: 7,
      overdue: [], today: [], later: [], total: 0,
    })
    render(<Dashboard user={MANAGER} onOpenOpportunity={() => {}}
      onGo={() => {}} />)
    await screen.findByText(/Yutish foizi/i)
    expect(api.profit).toHaveBeenCalled()
    expect(api.audit).toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
describe('Audit: "hammasi joyida" ham AYTILADI', () => {
  it('toza bo‘lsa buni ochiq yozadi', async () => {
    api.audit.mockResolvedValue({
      items: [], days: 30,
      summary: { n: 12, outside_erp: 0, after_issue: 0, last_at: null },
      clean: true,
    })
    render(<AuditPanel />)
    // Bo'sh ro'yxat "tekshirilmadi" degani emas.
    expect(await screen.findByText(/shubhali o'zgarish yo'q/i)).toBeTruthy()
  })

  it('ERP dan tashqaridagi o‘zgarish ajratib ko‘rsatiladi', async () => {
    api.audit.mockResolvedValue({
      items: [{ id: 1, doc_type: 'invoice', doc_label: 'Hisob-faktura',
        doc_id: 7, entity: 'invoice', entity_label: 'Faktura', entity_id: 7,
        action: 'update', action_label: "o'zgartirildi", field: 'number',
        old_value: 'F-1', new_value: 'F-SOXTA', doc_status: 'issued',
        after_issue: true, actor: null, outside_erp: true,
        created_at: '2026-08-22T10:00:00+05:00' }],
      days: 30,
      summary: { n: 1, outside_erp: 1, after_issue: 1, last_at: null },
      clean: false,
    })
    render(<AuditPanel />)
    // Matn ikki joyda: filtr yorlig'ida va qatordagi belgida. Ikkalasi
    // ham bo'lishi KERAK, shuning uchun sonini tekshiramiz.
    expect((await screen.findAllByText(/ERP dan tashqarida/i)).length)
      .toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/chiqarilgandan keyin/i)).toBeTruthy()
    // Eski va yangi qiymat KO'RINADI.
    expect(screen.getByText(/F-SOXTA/)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
describe('Parol almashtirish (auth-6)', () => {
  it('joriy parolsiz yoki nusxalar mos kelmasa tugma o‘chiq', async () => {
    render(<MyPasswordPanel userId={1} onClose={() => {}} />)
    const btn = screen.getByRole('button', { name: /almashtirish/i })
    expect((btn as HTMLButtonElement).disabled).toBe(true)

    const u = userEvent.setup()
    await u.type(screen.getByLabelText(/joriy parol/i), 'eski-parol-123')
    await u.type(screen.getByLabelText(/^yangi parol$/i), 'yangi-parol-123')
    await u.type(screen.getByLabelText(/takror/i), 'boshqacha')
    expect(screen.getByText(/bir xil emas/i)).toBeTruthy()
    expect((btn as HTMLButtonElement).disabled).toBe(true)
  })

  it('yopilgan sessiyalar soni AYTILADI', async () => {
    api.setUserPassword.mockResolvedValue({ ok: true, closed_sessions: 2 })
    const u = userEvent.setup()
    render(<MyPasswordPanel userId={1} onClose={() => {}} />)
    await u.type(screen.getByLabelText(/joriy parol/i), 'eski-parol-123')
    await u.type(screen.getByLabelText(/^yangi parol$/i), 'yangi-parol-123')
    await u.type(screen.getByLabelText(/takror/i), 'yangi-parol-123')
    await u.click(screen.getByRole('button', { name: /almashtirish/i }))
    expect(await screen.findByText(/Boshqa 2 ta sessiya yopildi/i)).toBeTruthy()
  })

  it('parol uzunligi sharti MIJOZDA takrorlanmaydi', async () => {
    // Server xatosi qanday kelsa shunday ko'rsatiladi — mijoz o'z
    // raqamini o'ylab topmaydi (`erp_auth.md` 11.7).
    api.setUserPassword.mockRejectedValue(
      new Error("400: Parol kamida 10 belgi bo'lsin."))
    const u = userEvent.setup()
    render(<MyPasswordPanel userId={1} onClose={() => {}} />)
    await u.type(screen.getByLabelText(/joriy parol/i), 'eski')
    await u.type(screen.getByLabelText(/^yangi parol$/i), 'qisqa')
    await u.type(screen.getByLabelText(/takror/i), 'qisqa')
    await u.click(screen.getByRole('button', { name: /almashtirish/i }))
    expect(await screen.findByText(/kamida 10 belgi/i)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// HUQUQ: tugma KO'RSATILMAYDI (bosilganda 403 beradigan tugma — yolg'on
// va'da). Matritsa serverda (`api/erp/perm.py`), ekran uni `/erp/auth/me`
// javobidan oladi; bu yerda aynan shu bog'lanish tekshiriladi.
const STOCK = {
  items: [{
    product_id: 1, product_name: 'Nasos', unit: 'dona', qty: 0, reserved: 0,
    available: 0, reserve_count: 0, updated_at: null, move_count: 0,
    in_catalog: true, import_qty: 7, import_at: null,
  }],
  kinds: [{ code: 'in', label: 'Kirim' }],
  reserve_states: [], negative: [], over_reserved: [],
}

describe('Huquq: ruxsat yo‘q amal EKRANDA ham yo‘q', () => {
  it('ombor harakati yo‘q bo‘lsa — ko‘chirish tugmasi ko‘rsatilmaydi', async () => {
    setPerms({ 'ombor.korish': 'read' })
    api.stock.mockResolvedValue(STOCK)
    render(<StockPage />)
    await screen.findByText(/Qoldiqlar/i)
    expect(screen.queryByText(/Import qoldiqlarini/i)).toBeNull()
  })

  it('ruxsat bo‘lsa — o‘sha tugma chiqadi', async () => {
    setPerms({ 'ombor.korish': 'full', 'ombor.harakat': 'full' })
    api.stock.mockResolvedValue(STOCK)
    render(<StockPage />)
    expect(await screen.findByText(/Import qoldiqlarini/i)).toBeTruthy()
  })
})

// EGALIK (`api/erp/egalik.py`): broker faqat o'z ishlarini ko'radi, ya'ni
// "boshqa hodim" filtri unga ISHLAMAYDI. Uni ekranda qoldirsak, tanlov
// natijani o'zgartirmasdi va filtr buzuq bo'lib ko'rinardi.
describe('Egalik: "o‘z ishlarim" filtri', () => {
  const TASKS = {
    broker_id: 5, self_broker_id: 5, days: 7,
    overdue: [], today: [], later: [], total: 0,
  }

  it('brokerga hodim tanlovi ko‘rsatilmaydi', async () => {
    setPerms({ 'hisobot.deadline': 'own' })
    api.myTasks.mockResolvedValue(TASKS)
    render(<MyTasksPage brokers={[]} onOpenOpportunity={() => {}} />)
    await screen.findByText(/kun/i)
    expect(screen.queryByText(/Barcha mas'ullar/i)).toBeNull()
  })

  it('menejerga ko‘rsatiladi', async () => {
    setPerms({ 'hisobot.deadline': 'full' })
    api.myTasks.mockResolvedValue(TASKS)
    render(<MyTasksPage brokers={[]} onOpenOpportunity={() => {}} />)
    expect(await screen.findByText(/Barcha mas'ullar/i)).toBeTruthy()
  })
})

// TAHLIL — Tender-AI qaroridagi SNAPSHOT. Ikki qoida ekranda ham
// amal qilishi kerak, chunki ikkalasi ham YOLG'ON ISHONCHNI to'sadi.
describe('Tahlil: yolg‘on ishonch to‘siladi', () => {
  const TAHLIL = (payload: Record<string, unknown>) => ({
    items: [{
      id: 1, topshiriq_id: 7, ishonch: 'aktor_elon',
      captured_at: '2026-09-01T10:00:00+05:00', payload,
    }],
  })

  it('yiqilgan bo‘lim YASHIRILMAYDI — sababi ko‘rinadi', async () => {
    api.tahlil.mockResolvedValue(TAHLIL({
      ombor: { ok: false, xato: 'DBUnavailable: katalog yo‘q' },
    }))
    render(<TahlilPanel oppId={1} />)
    expect(await screen.findByText(/olinmadi/i)).toBeTruthy()
    expect(screen.getByText(/katalog yo‘q/i)).toBeTruthy()
  })

  it('tasdiqlanmagan talab "ko‘rilmagan" deb belgilanadi', async () => {
    api.tahlil.mockResolvedValue(TAHLIL({
      talablar: { ok: true, data: { royxat: [
        { matn: 'Litsenziya talab qilinadi', holat: 'pending_review' },
      ] } },
    }))
    render(<TahlilPanel oppId={1} />)
    expect(await screen.findByText(/ko'rilmagan/i)).toBeTruthy()
  })

  it('ishonch darajasi DALILDAN oshmaydi', async () => {
    api.tahlil.mockResolvedValue(TAHLIL({ ai: { ok: true, data: { qaror: 'go' } } }))
    render(<TahlilPanel oppId={1} />)
    expect(await screen.findByText(/e‘lon qilingan/i)).toBeTruthy()
    expect(screen.queryByText(/tasdiqlangan/i)).toBeNull()
  })

  it('tahlil yo‘q bo‘lsa blok UMUMAN ko‘rsatilmaydi', async () => {
    api.tahlil.mockResolvedValue({ items: [] })
    const { container } = render(<TahlilPanel oppId={1} />)
    await new Promise((r) => setTimeout(r, 0))
    expect(container.textContent).toBe('')
  })
})

// ---------------------------------------------------------------------------
// QO'LDA SINOVDA TOPILGAN KAMCHILIKLAR.
//
// Uchtasi ham bir ildizdan: EKRAN huquqni yoki hujjatning holatini
// hisobga olmasdi. Natijada odam formani to'ldirib bo'lgach saqlay
// olmasdi, tugmani bosib 403 olardi yoki yopilgan kartani jimgina
// o'zgartirib yuborardi.
// ---------------------------------------------------------------------------
const OPP = (patch: Record<string, unknown> = {}) => ({
  id: 1,
  tender_id: 7,
  tender: {
    source_platform: 'xt-xarid', tender_ref: '7', customer_name: 'AGROBANK',
    title: 'Server', start_price: 100, currency: 'UZS',
    deadline_at: null, region_name: null, source_url: null,
  },
  broker: null, client: null, priority: 'medium', priority_label: "O'rta",
  win_probability: null, note: null, next_task: null, next_task_at: null,
  status: 'new', status_label: 'Yangi', is_final: false,
  status_changed_at: null, closed_at: null, lost_reason: null,
  created_by: null, created_at: null, updated_at: null, history: [],
  ...patch,
})

const CARD_PROPS = {
  id: 1,
  statuses: [
    { code: 'new', label: 'Yangi', final: false },
    { code: 'won', label: 'Yutildi', final: true },
  ],
  brokers: [],
  clients: [],
  priorities: [{ code: 'medium', label: "O'rta" }],
  onClose: () => {},
  onChanged: () => {},
}

describe('Yopilgan karta TAHRIRLANMAYDI', () => {
  beforeEach(() => {
    api.tenderDiff.mockResolvedValue({
      opportunity_id: 1, tender_id: 7, exists: true, changed: [],
    })
  })

  it('yakuniy statusda "Saqlash" yo‘q va sababi yoziladi', async () => {
    setPerms({ 'karta.korish': 'full', 'karta.tahrirlash': 'full' })
    api.opportunity.mockResolvedValue(
      OPP({ status: 'won', status_label: 'Yutildi', is_final: true }))
    render(<OpportunityCard {...CARD_PROPS} />)
    expect(await screen.findByText(/Karta yakunlangan/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Saqlash/i })).toBeNull()
  })

  it('ochiq kartada "Saqlash" bor', async () => {
    setPerms({ 'karta.korish': 'full', 'karta.tahrirlash': 'full' })
    api.opportunity.mockResolvedValue(OPP())
    render(<OpportunityCard {...CARD_PROPS} />)
    expect(await screen.findByRole('button', { name: /Saqlash/i })).toBeTruthy()
  })

  it('tahrirlash huquqi yo‘q bo‘lsa sabab AYTILADI', async () => {
    setPerms({ 'karta.korish': 'own' })
    api.opportunity.mockResolvedValue(OPP())
    render(<OpportunityCard {...CARD_PROPS} />)
    expect(await screen.findByText(/rahbar yoki menejer huquqi/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Saqlash/i })).toBeNull()
  })
})

// Passport: "to'ldirdim, saqlay olmadim" — eng qimmat kamchilik, chunki
// kiritilgan ma'lumot butunlay yo'qoladi.
describe('Mijoz passporti: yozib bo‘lmasa OLDINDAN aytiladi', () => {
  const CLIENT = {
    id: 3, name: 'ZZ MCHJ', inn: null, oked: null, legal_form: null,
    tax_mode: null, address_legal: null, address_actual: null,
    bank_name: null, bank_mfo: null, bank_account: null,
    director_name: null, phone: null, email: null, note: null,
    active: true, vat_payer: null, vat_rate: null,
    created_at: null, updated_at: null, missing: [],
    contacts: [], documents: [], opportunities: [],
    summary: {
      opp_n: 0, won_n: 0, lost_n: 0, rejected_n: 0, open_n: 0,
      won_total: null, currency: null, mixed_currency: false, win_rate: null,
    },
  }

  it('huquq yo‘q — sabab ko‘rinadi, Saqlash yo‘q', async () => {
    setPerms({ 'mijoz.korish': 'own' })
    api.client.mockResolvedValue(CLIENT)
    render(<ClientCard id={3} onClose={() => {}} onSaved={() => {}} />)
    expect(await screen.findByText(/rahbar yoki menejer huquqi/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /^Saqlash$/i })).toBeNull()
  })

  it('huquq bor — Saqlash tugmasi turadi', async () => {
    setPerms({ 'mijoz.korish': 'full', 'mijoz.tahrirlash': 'full' })
    api.client.mockResolvedValue(CLIENT)
    render(<ClientCard id={3} onClose={() => {}} onSaved={() => {}} />)
    expect(await screen.findByRole('button', { name: /^Saqlash$/i })).toBeTruthy()
  })
})

// Dalolatnoma: bosilib 403 beradigan tugmadan ko'ra ko'rsatilmagani
// yaxshi — fakturada allaqachon shunday, akt orqada qolgan edi.
describe('Dalolatnoma: ruxsatsiz tugma KO‘RSATILMAYDI', () => {
  const INV = {
    id: 9, status: 'issued', status_label: 'Chiqarildi', currency: 'UZS',
  } as never
  const ACT = {
    id: 4, status: 'draft', status_label: 'Qoralama', number: 'A-1',
    act_date: '2026-09-01', signed_at: null, currency: 'UZS',
    totals: { net: 0, vat: 0, total: 100, words: '' },
  }

  it('brokerda "Chiqarish" ham, "Dalolatnoma chiqarish" ham yo‘q', async () => {
    setPerms({ 'hujjat.korish': 'own' })
    api.acts.mockResolvedValue([ACT])
    render(<ActPanel inv={INV} />)
    await screen.findByText(/faktura bilan juft/i)
    expect(screen.queryByRole('button', { name: /^Chiqarish$/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /Dalolatnoma chiqarish/i }))
      .toBeNull()
  })

  it('menejerda ikkalasi ham bor', async () => {
    setPerms({
      'hujjat.korish': 'full', 'hujjat.qoralama': 'full',
      'hujjat.chiqarish': 'full', 'hujjat.bekor': 'full',
    })
    api.acts.mockResolvedValue([ACT])
    render(<ActPanel inv={INV} />)
    expect(await screen.findByRole('button', { name: /^Chiqarish$/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Dalolatnoma chiqarish/i }))
      .toBeTruthy()
  })
})

// Qidiruv yoqilganda sarlavhadagi son ro'yxat bilan mos kelishi kerak:
// "Qoldiqlar (1800)" deb turgan sarlavha 3 ta qator ustida yolg'on gapiradi.
describe('Ombor: sarlavhadagi son FILTRGA moslashadi', () => {
  it('qidiruvda "topilgan / jami" ko‘rinadi', async () => {
    setPerms({ 'ombor.korish': 'full' })
    api.stock.mockResolvedValue({
      ...STOCK,
      items: [
        { ...STOCK.items[0], product_id: 1, product_name: 'Nasos' },
        { ...STOCK.items[0], product_id: 2, product_name: 'Server' },
      ],
    })
    render(<StockPage />)
    expect(await screen.findByText('Qoldiqlar (2)')).toBeTruthy()
    await userEvent.type(screen.getByPlaceholderText(/Mahsulot nomi/i), 'nasos')
    expect(await screen.findByText('Qoldiqlar (1 / 2)')).toBeTruthy()
  })
})


// ---------------------------------------------------------------------------
// SABAB HUJJATI (24-patch)
// ---------------------------------------------------------------------------
// Funksiya IXTIYORIY, va aynan shuning uchun ekranda tekshiriladi:
// ixtiyoriy narsa jimgina yo'qolsa hech kim sezmaydi. Uchta qoida
// serverda emas, FAQAT shu yerda ushlanadi.
const FAYL_META = {
  schema_ready: true,
  statuses: [], priorities: [],
  fayl_ready: true,
  fayl_holatlar: ['lost', 'rejected', 'ulgurmadik'],
  fayl_turlar: ['.pdf', '.docx'],
  fayl_max_hajm: 10485760,
}

describe('Sabab hujjati: YO‘QLIGI ham aytiladi', () => {
  it('fayl bo‘lmasa "yo‘q" deb YOZILADI, bo‘sh joy qoldirilmaydi', async () => {
    setPerms({ 'karta.fayl': 'full' })
    api.oppFiles.mockResolvedValue([])
    render(<SababFayl oppId={1} oppStatus="lost" meta={FAYL_META as never} />)
    expect(await screen.findByText(/yo‘q — biriktirilmagan|yo'q — biriktirilmagan/))
      .toBeTruthy()
  })

  it('fayl bor bo‘lsa nomi va hajmi ko‘rinadi', async () => {
    setPerms({ 'karta.fayl': 'full' })
    api.oppFiles.mockResolvedValue([{
      id: 5, opportunity_id: 1, fayl_nom: 'Sabab.pdf',
      mime: 'application/pdf', hajm: 2048, sha256: 'x', izoh: null,
      created_by: 'A. Karimov', created_at: null,
    }])
    render(<SababFayl oppId={1} oppStatus="lost" meta={FAYL_META as never} />)
    expect(await screen.findByRole('button', { name: 'Sabab.pdf' })).toBeTruthy()
    expect(screen.getByText('2 KB')).toBeTruthy()
  })

  it('OCHIQ kartada yuklash yo‘q va SABABI yoziladi', async () => {
    setPerms({ 'karta.fayl': 'full' })
    api.oppFiles.mockResolvedValue([])
    render(<SababFayl oppId={1} oppStatus="preparing" meta={FAYL_META as never} />)
    expect(await screen.findByText(/faqat yakunlanmagan kartaga/i)).toBeTruthy()
    expect(screen.queryByLabelText(/Sabab hujjatini tanlash/i)).toBeNull()
  })

  it('yakunlangan kartada yuklash MAYDONI bor', async () => {
    setPerms({ 'karta.fayl': 'full' })
    api.oppFiles.mockResolvedValue([])
    render(<SababFayl oppId={1} oppStatus="ulgurmadik" meta={FAYL_META as never} />)
    expect(await screen.findByLabelText(/Sabab hujjatini tanlash/i)).toBeTruthy()
  })

  it('huquq yo‘q — yuklash ham, o‘chirish ham KO‘RSATILMAYDI', async () => {
    setPerms({ 'karta.korish': 'own' })
    api.oppFiles.mockResolvedValue([{
      id: 5, opportunity_id: 1, fayl_nom: 'Sabab.pdf',
      mime: 'application/pdf', hajm: 2048, sha256: 'x', izoh: null,
      created_by: null, created_at: null,
    }])
    render(<SababFayl oppId={1} oppStatus="lost" meta={FAYL_META as never} />)
    expect(await screen.findByText(/ruxsatingiz yo‘q|ruxsatingiz yo'q/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /O‘chirish|O'chirish/ })).toBeNull()
  })

  it('patch qo‘llanmagan bo‘lsa blok UMUMAN ko‘rsatilmaydi', async () => {
    setPerms({ 'karta.fayl': 'full' })
    api.oppFiles.mockResolvedValue([])
    const { container } = render(
      <SababFayl oppId={1} oppStatus="lost"
        meta={{ ...FAYL_META, fayl_ready: false } as never} />)
    expect(container.querySelector('[data-testid="sabab-fayl"]')).toBeNull()
  })
})


// ---------------------------------------------------------------------------
// VORONKA: "ishlanmoqda" va "muddati o'tgan" ARALASHMAYDI
// ---------------------------------------------------------------------------
// Tizim kartani o'zi yopmaydi (qaror odamniki), shuning uchun muddati
// o'tgan karta bosqichda turaveradi. Bitta songa yig'ilsa jadval
// "9 ta ishlanmoqda" deb YOLG'ON gapirardi.
describe('Tahlil: muddati o‘tgan karta "ishlanmoqda" deb sanalmaydi', () => {
  const AN = {
    stages: [{
      code: 'preparing', label: 'Taklif tayyorlanmoqda', finished_n: 3,
      avg_days: 2, median_days: 2, max_days: 5,
      ongoing_n: 9, faol_n: 2, kechikkan_n: 7, oldest_days: 4, final: false,
    }],
    funnel: [], stuck: [], lost_reasons: [], by_broker: [],
    stuck_days: 14, mixed_currency: false, currency: 'UZS',
  }

  it('faol va muddati o‘tgan AJRATIB ko‘rsatiladi', async () => {
    setPerms({ 'hisobot.kompaniya': 'full' })
    api.stats.mockResolvedValue(EMPTY_STATS)
    api.analytics.mockResolvedValue(AN)
    const { default: OpportunityStats } =
      await import('../components/erp/OpportunityStats')
    render(<OpportunityStats onOpen={() => {}} />)
    // Ustun sarlavhasi bor — ya'ni raqam ATALGAN, shunchaki son emas.
    expect(await screen.findByText(/Muddati o.tgan/)).toBeTruthy()

    // QATOR ichida: faol 2, kechikkan 7 — ALOHIDA kataklarda.
    // Butun ekran bo'ylab qidirilsa "2" bir nechta joyda uchraydi,
    // shuning uchun aynan shu bosqich qatoriga qaraymiz.
    const qator = (await screen.findByText('Taklif tayyorlanmoqda'))
      .closest('tr') as HTMLTableRowElement
    const katak = [...qator.querySelectorAll('td')].map((td) => td.textContent)
    expect(katak).toContain('2')
    expect(katak).toContain('7')
    // Yig'ma son (9) KO'RSATILMAYDI — u aynan chalg'ituvchi raqam edi.
    expect(katak).not.toContain('9')
  })
})

// ---------------------------------------------------------------------------
// SABAB: yakunlanmagan uchta holatda MAJBURIY
// ---------------------------------------------------------------------------
describe('Status dialogi: sabab MAJBURIY', () => {
  const TO = (code: string, label: string) => ({ code, label, final: true })
  const REASONS = [{ code: 'price', label: 'Narx yuqori' }]
  const OPP_MIN = { id: 1, title: 'ZZ', status: 'preparing', is_final: false }

  async function ochish(code: string, label: string) {
    const { default: Dlg } = await import('../components/erp/StatusChangeDialog')
    render(<Dlg o={OPP_MIN as never} to={TO(code, label)}
      lostReasons={REASONS} onCancel={() => {}} onConfirm={() => {}} />)
  }

  for (const [code, label] of [['lost', 'Yutqazildi'],
                               ['rejected', 'Rad etildi'],
                               ['ulgurmadik', 'Ulgurmadik']]) {
    it(`'${code}': sabab tanlanmaguncha tasdiq tugmasi O'CHIQ`, async () => {
      await ochish(code, label)
      const tugma = await screen.findByRole('button', { name: /Tasdiqlash/i })
      expect((tugma as HTMLButtonElement).disabled).toBe(true)
    })
  }

  it("'won': sabab so‘ralmaydi, tugma OCHIQ", async () => {
    await ochish('won', 'Yutildi')
    const tugma = await screen.findByRole('button', { name: /Tasdiqlash/i })
    expect((tugma as HTMLButtonElement).disabled).toBe(false)
  })
})


// ---------------------------------------------------------------------------
// MULOQOT (25-patch)
// ---------------------------------------------------------------------------
// Uchta qoida faqat EKRANDA ushlanadi. Ular server javobida bor, lekin
// bir noto'g'ri `&&` va ular jimgina yo'qoladi — chatda esa yo'qolgan
// narsa "hech qachon bo'lmagan" bo'lib ko'rinadi.
const MSG = (p: Record<string, unknown> = {}) => ({
  id: 1, chat_id: 7, author_id: 2, author_name: 'B. To‘xtayev',
  tizim: false, text: 'Salom', ochirilgan: false, ochirdi: null,
  ochirish_izohi: null, reply_to_id: null, created_at: null,
  edited_at: null, tahrirlangan: false, ...p,
})

const LENTA = (chat: Record<string, unknown>, messages: unknown[]) => ({
  chat: {
    id: 7, turi: 'opportunity', opportunity_id: 3, title: 'ZZ tender',
    arxiv: false, azoman: true, ...chat,
  },
  messages, yana: false,
})

function muloqot(lenta: unknown, members: unknown = { chat_id: 7, turi: 'opportunity', virtual: false, members: [] }) {
  api.oppChat.mockResolvedValue({ chat_id: 7 })
  api.chatMessages.mockResolvedValue(lenta)
  api.chatMembers.mockResolvedValue(members)
  api.chatRead.mockResolvedValue({ last_read_id: 1 })
  return render(<Muloqot oppId={3} compact />)
}

describe('Muloqot: o‘chirilgan xabar YO‘QOLMAYDI', () => {
  it('"Xabar o‘chirildi" va KIM o‘chirgani yoziladi', async () => {
    setPerms({ 'chat.korish': 'full', 'chat.yozish': 'full' })
    muloqot(LENTA({}, [MSG({
      ochirilgan: true, text: null, ochirdi: 'A. Karimov',
      ochirish_izohi: 'ish bilan bog‘liq emas',
    })]))
    expect(await screen.findByText(/Xabar o.chirildi/)).toBeTruthy()
    expect(screen.getByText(/A\. Karimov/)).toBeTruthy()
    // Sabab ham ko'rinadi — "nega yo'qoldi" savoli qolmasin.
    expect(screen.getByText(/ish bilan bog/)).toBeTruthy()
  })

  it('o‘chirilgan xabarga JAVOB ham ko‘rinadi', async () => {
    setPerms({ 'chat.korish': 'full', 'chat.yozish': 'full' })
    muloqot(LENTA({}, [MSG({
      id: 2, text: 'javobim', reply_to_id: 1,
      reply: { id: 1, author_name: 'X', text: null, ochirilgan: true },
    })]))
    expect(await screen.findByText(/o.chirilgan xabar/)).toBeTruthy()
    expect(screen.getByText('javobim')).toBeTruthy()
  })
})

describe('Muloqot: yozish TAQIQLANSA sababi aytiladi', () => {
  it('arxiv chatda yozish maydoni YO‘Q va sababi yoziladi', async () => {
    setPerms({ 'chat.korish': 'full', 'chat.yozish': 'full' })
    muloqot(LENTA({ arxiv: true }, [MSG()]))
    expect(await screen.findByText(/Chat arxivlangan/)).toBeTruthy()
    expect(screen.queryByLabelText(/Xabar matni/)).toBeNull()
  })

  it('a‘zo bo‘lmasa — "avval qo‘shiling" deb aytiladi', async () => {
    setPerms({ 'chat.korish': 'full', 'chat.yozish': 'full' })
    muloqot(LENTA({ azoman: false }, [MSG()]))
    expect(await screen.findByText(/avval chatga qo.shiling/)).toBeTruthy()
    expect(screen.queryByLabelText(/Xabar matni/)).toBeNull()
  })

  it('huquq yo‘q — maydon ham, sabab ham', async () => {
    setPerms({ 'chat.korish': 'own' })
    muloqot(LENTA({}, [MSG()]))
    expect(await screen.findByText(/ruxsatingiz yo/)).toBeTruthy()
    expect(screen.queryByLabelText(/Xabar matni/)).toBeNull()
  })

  it('hammasi joyida — maydon BOR', async () => {
    setPerms({ 'chat.korish': 'full', 'chat.yozish': 'full' })
    muloqot(LENTA({}, [MSG()]))
    expect(await screen.findByLabelText(/Xabar matni/)).toBeTruthy()
  })
})

describe('Muloqot: tizim xabari MULOQOT emas', () => {
  it('tizim xabarida javob/tahrir/o‘chirish tugmalari YO‘Q', async () => {
    setPerms({ 'chat.korish': 'full', 'chat.yozish': 'full' })
    muloqot(LENTA({}, [MSG({
      author_id: null, author_name: 'Tizim', tizim: true,
      text: 'Holat: Yangi -> Yutqazildi',
    })]))
    expect(await screen.findByText(/Holat: Yangi/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Javob/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Tahrir/ })).toBeNull()
  })
})
