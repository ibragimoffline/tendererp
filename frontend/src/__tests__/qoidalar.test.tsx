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

const api = {
  stats: vi.fn(), analytics: vi.fn(), myTasks: vi.fn(), invoiceStats: vi.fn(),
  profit: vi.fn(), audit: vi.fn(), opportunities: vi.fn(),
  cardProfit: vi.fn(), setUserPassword: vi.fn(), loginAttempts: vi.fn(),
}
vi.mock('@/api', () => ({ api, ApiError: class extends Error {} }))

const { default: Dashboard } = await import('../components/erp/Dashboard')
const { default: ProfitLine } = await import('../components/erp/ProfitLine')
const { default: ProfitPanel } = await import('../components/erp/ProfitPanel')
const { default: AuditPanel } = await import('../components/erp/AuditPanel')
const { default: MyPasswordPanel } =
  await import('../components/erp/MyPasswordPanel')

const MANAGER: AuthUser = {
  id: 1, username: 'a', full_name: 'A', role: 'admin',
  role_label: 'Administrator', broker_id: null, broker_name: null,
  email: null, active: true, last_login_at: null,
}
const BROKER: AuthUser = { ...MANAGER, role: 'broker', role_label: 'Broker' }

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
afterEach(cleanup)

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
