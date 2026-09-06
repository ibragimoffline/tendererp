import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ErpBroker, Jamoa, MyTask } from '@/types'

// JAMOA va VAZIFALAR — EKRANDAGI QARORLAR sinovi (28-patch).
//
// Bu yerdagi qoidalar JIM buziladi — ekran xato bermaydi, shunchaki
// noto'g'ri narsani ko'rsatadi yoki ko'rsatmaydi:
//
//   1. UMUMIY VAZIFA KARTAGA OLIB BORMAYDI. `t.opportunity` endi
//      `null` bo'lishi mumkin; ilgari u har doim bor deb
//      hisoblanardi va bunday qatorni bosish ekranni yiqitardi.
//   2. ASOSIY MAS'UL AJRALIB TURADI. Jamoa ro'yxatida u boshqalar
//      bilan aralashib ketsa, "kim javobgar" degan savol yo'qolardi.
//   3. HUQUQ EKRANDA HAM KO'RINADI. Chiqarish va asosiy qilish
//      brokerda yo'q — tugmani ko'rsatib, keyin 403 berish eng yomon
//      variant: odam nima qilolmasligini FAQAT urinib ko'rgach
//      bilardi.
//   4. YUKLAMA BAHO EMAS. Raqamlar yonida buni ochiq aytadigan
//      yozuv turishi kerak.

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {}
}
if (!('ResizeObserver' in globalThis)) {
  ;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver =
    class { observe() {} unobserve() {} disconnect() {} }
}

// POINTER CAPTURE — jsdom da YO'Q, Radix Select esa uni chaqiradi.
//
// Usiz sinov "88 ta o'tdi" deb ko'rinadi, lekin vitest oxirida
// `Errors 1 error` yozadi va NOLINCHI BO'LMAGAN kod qaytaradi:
// ushlanmagan istisno sinov tugagandan KEYIN otiladi, ya'ni
// hech bir `it()` ni yiqitmaydi.
//
// Buni deploy skripti topdi — men esa `npx vitest run | grep "Tests"`
// qilib tekshirayotgan edim va o'sha qator "88 passed" deb turardi.
// Ya'ni SINOV EMAS, MENING TEKSHIRISH USULIM aldagan. Chiqish kodi
// yagona ishonchli belgi.
for (const nom of ['hasPointerCapture', 'setPointerCapture',
                   'releasePointerCapture'] as const) {
  if (!(nom in Element.prototype)) {
    ;(Element.prototype as unknown as Record<string, unknown>)[nom] =
      function stub() { return false }
  }
}

const api = {
  jamoa: vi.fn(), jamoaAdd: vi.fn(), jamoaRemove: vi.fn(),
  jamoaRole: vi.fn(), jamoaPrimary: vi.fn(),
  myTasks: vi.fn(), taskList: vi.fn(), taskCreate: vi.fn(),
  taskStatus: vi.fn(), taskAssign: vi.fn(), workload: vi.fn(),
  setTaskDone: vi.fn(),
}
vi.mock('@/api', () => ({ api, ApiError: class extends Error {} }))

const { default: JamoaPanel } = await import('../components/erp/JamoaPanel')
const { default: MyTasksPage } = await import('../components/erp/MyTasksPage')
const { setPerms } = await import('../components/erp/erpShared')

const BROKERS: ErpBroker[] = [
  { id: 1, full_name: 'Karimov A.', email: null, phone: null, active: true },
  { id: 2, full_name: 'Aliyev B.', email: null, phone: null, active: true },
  { id: 3, full_name: 'Rasulov D.', email: null, phone: null, active: true },
  { id: 4, full_name: 'Eski X.', email: null, phone: null, active: false },
]

function jamoa(over: Partial<Jamoa> = {}): Jamoa {
  return {
    opportunity_id: 7,
    asosiy_broker_id: 1,
    azolar: [
      { broker_id: 1, full_name: 'Karimov A.', active: true, app_user_id: 10,
        rol: 'masul', rol_label: "Mas'ul", asosiy: true, izoh: null,
        added_at: null, added_by_name: null, removed_at: null },
      { broker_id: 2, full_name: 'Aliyev B.', active: true, app_user_id: 11,
        rol: 'narx', rol_label: 'Narx va hisob-kitob', asosiy: false,
        izoh: null, added_at: '2026-09-01T10:00:00+05:00',
        added_by_name: 'Menejer', removed_at: null },
    ],
    soni: 2,
    rollar: [
      { kod: 'narx', label: 'Narx va hisob-kitob' },
      { kod: 'hujjat', label: 'Hujjatlar' },
      { kod: 'kuzatuvchi', label: 'Kuzatuvchi' },
    ],
    ...over,
  }
}

function vazifa(over: Partial<MyTask> = {}): MyTask {
  return {
    id: 1, opportunity_id: 7, title: 'Marjani hisoblash',
    assignee: { id: 2, name: 'Aliyev B.' },
    due_at: '2026-09-10', done: false, done_at: null, cancelled_at: null,
    note: null, reminded_at: null, created_by: 'Menejer',
    created_at: '2026-09-01T10:00:00+05:00', updated_at: null,
    status: 'yangi', status_label: 'Yangi', priority: 'medium',
    priority_label: "O'rta", kontekst: 'karta', ochiq: true, overdue: false,
    opportunity: {
      id: 7, title: 'Server tenderi', status: 'preparing', tender_id: 100,
      client_name: 'Mijoz MCHJ', broker_name: 'Karimov A.',
      deadline_at: '2026-09-12T18:00:00+05:00', start_price: 1000,
      currency: 'UZS',
    },
    ...over,
  }
}

const UMUMIY = vazifa({
  id: 2, opportunity_id: null, title: 'Sertifikatni yangilash',
  kontekst: 'umumiy', opportunity: null, priority: 'high',
  priority_label: 'Yuqori',
})

function myTasks(items: MyTask[]) {
  return {
    broker_id: 1, days: 7, total: items.length,
    overdue: items.filter((t) => t.overdue),
    today: [], later: items.filter((t) => !t.overdue),
    self_broker_id: 1,
  }
}

afterEach(() => { cleanup(); setPerms(null) })

beforeEach(() => {
  vi.clearAllMocks()
  const never = new Promise(() => {})
  for (const f of Object.values(api)) f.mockReturnValue(never)
})

// ---------------------------------------------------------------------------
describe('Jamoa: asosiy mas’ul ajralib turadi', () => {
  it('mas’ul va jamoadoshlar ro‘yxatda, rollari bilan', async () => {
    setPerms({ 'karta.jamoa': 'full', 'karta.jamoa_qosh': 'full' })
    api.jamoa.mockResolvedValue(jamoa())
    render(<JamoaPanel oppId={7} brokers={BROKERS} />)

    const masul = await screen.findByTestId('jamoa-azo-1')
    expect(masul.textContent).toContain('Karimov A.')
    expect(masul.textContent).toContain("Mas'ul")
    const narx = screen.getByTestId('jamoa-azo-2')
    expect(narx.textContent).toContain('Aliyev B.')
    expect(narx.textContent).toContain('Narx')
  })

  it('jamoa bo‘sh bo‘lsa sabab yoziladi', async () => {
    setPerms({ 'karta.jamoa': 'full' })
    api.jamoa.mockResolvedValue(jamoa({
      asosiy_broker_id: null, azolar: [], soni: 0 }))
    render(<JamoaPanel oppId={7} brokers={BROKERS} />)
    expect(await screen.findByText(/mas'ul biriktirilmagan/)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
describe('Jamoa: qo‘shish', () => {
  it('qidiruv bilan tanlanadi va allaqachon a’zolar ko‘rsatilmaydi',
    async () => {
      setPerms({ 'karta.jamoa': 'full', 'karta.jamoa_qosh': 'full' })
      api.jamoa.mockResolvedValue(jamoa())
      render(<JamoaPanel oppId={7} brokers={BROKERS} />)

      await userEvent.click(await screen.findByTestId('jamoa-och'))
      // Karimov (mas'ul) va Aliyev (a'zo) ro'yxatda YO'Q.
      expect(screen.queryByTestId('jamoa-qosh-1')).toBeNull()
      expect(screen.queryByTestId('jamoa-qosh-2')).toBeNull()
      // Rasulov bor, FAOLSIZ Eski X. esa yo'q.
      expect(screen.getByTestId('jamoa-qosh-3')).toBeTruthy()
      expect(screen.queryByTestId('jamoa-qosh-4')).toBeNull()

      await userEvent.type(screen.getByTestId('jamoa-qidiruv'), 'rasul')
      expect(screen.getByTestId('jamoa-qosh-3')).toBeTruthy()
    })

  it('qo‘shilgach ro‘yxat yangilanadi', async () => {
    setPerms({ 'karta.jamoa': 'full', 'karta.jamoa_qosh': 'full' })
    api.jamoa.mockResolvedValue(jamoa())
    const yangi = jamoa()
    yangi.azolar.push({
      broker_id: 3, full_name: 'Rasulov D.', active: true, app_user_id: 12,
      rol: 'kuzatuvchi', rol_label: 'Kuzatuvchi', asosiy: false, izoh: null,
      added_at: null, added_by_name: null, removed_at: null })
    yangi.soni = 3
    api.jamoaAdd.mockResolvedValue(yangi)
    const onChanged = vi.fn()
    render(<JamoaPanel oppId={7} brokers={BROKERS} onChanged={onChanged} />)

    await userEvent.click(await screen.findByTestId('jamoa-och'))
    await userEvent.click(screen.getByTestId('jamoa-qosh-3'))
    expect(api.jamoaAdd).toHaveBeenCalledWith(7, 3, 'kuzatuvchi')
    expect(await screen.findByTestId('jamoa-azo-3')).toBeTruthy()
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('xato KO‘RSATILADI (ichki tafsilotsiz)', async () => {
    setPerms({ 'karta.jamoa': 'full', 'karta.jamoa_qosh': 'full' })
    api.jamoa.mockResolvedValue(jamoa())
    api.jamoaAdd.mockRejectedValue(
      new Error('Aliyev B. allaqachon jamoada.'))
    render(<JamoaPanel oppId={7} brokers={BROKERS} />)

    await userEvent.click(await screen.findByTestId('jamoa-och'))
    await userEvent.click(screen.getByTestId('jamoa-qosh-3'))
    expect(await screen.findByText(/allaqachon jamoada/)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
describe('Jamoa: huquq ekranda ham ko‘rinadi', () => {
  it('brokerga chiqarish va asosiy qilish KO‘RSATILMAYDI', async () => {
    // Broker jamoaga qo'sha oladi, lekin chiqara olmaydi.
    setPerms({ 'karta.jamoa': 'own', 'karta.jamoa_qosh': 'own' })
    api.jamoa.mockResolvedValue(jamoa())
    render(<JamoaPanel oppId={7} brokers={BROKERS} />)

    await screen.findByTestId('jamoa-azo-2')
    expect(screen.queryByTestId('jamoa-menu-2')).toBeNull()
    // Qo'shish esa ochiq.
    expect(screen.getByTestId('jamoa-och')).toBeTruthy()
  })

  it('menejerga amallar menyusi ochiladi', async () => {
    setPerms({ 'karta.jamoa': 'full', 'karta.jamoa_qosh': 'full',
               'karta.jamoa_chiqar': 'full', 'karta.biriktirish': 'full' })
    api.jamoa.mockResolvedValue(jamoa())
    api.jamoaPrimary.mockResolvedValue(jamoa({ asosiy_broker_id: 2 }))
    render(<JamoaPanel oppId={7} brokers={BROKERS} />)

    await userEvent.click(await screen.findByTestId('jamoa-menu-2'))
    expect(screen.getByTestId('jamoa-chiqar-2')).toBeTruthy()
    await userEvent.click(screen.getByTestId('jamoa-asosiy-2'))
    expect(api.jamoaPrimary).toHaveBeenCalledWith(7, 2)
  })

  it('ASOSIY mas’ulda "asosiy qilish" tugmasi yo‘q', async () => {
    setPerms({ 'karta.jamoa': 'full', 'karta.jamoa_chiqar': 'full',
               'karta.biriktirish': 'full' })
    api.jamoa.mockResolvedValue(jamoa())
    render(<JamoaPanel oppId={7} brokers={BROKERS} />)
    // Mas'ulni chiqarib ham, qayta "asosiy" qilib ham bo'lmaydi.
    await screen.findByTestId('jamoa-azo-1')
    expect(screen.queryByTestId('jamoa-menu-1')).toBeNull()
  })

  it('chiqarilganlar tarixi ko‘rinadi (qator yo‘qolmaydi)', async () => {
    setPerms({ 'karta.jamoa': 'full' })
    const bilanTarix = jamoa()
    bilanTarix.azolar.push({
      broker_id: 3, full_name: 'Rasulov D.', active: true, app_user_id: 12,
      rol: 'hujjat', rol_label: 'Hujjatlar', asosiy: false, izoh: null,
      added_at: null, added_by_name: null,
      removed_at: '2026-09-05T10:00:00+05:00' })
    api.jamoa.mockResolvedValue(bilanTarix)
    render(<JamoaPanel oppId={7} brokers={BROKERS} />)

    await userEvent.click(await screen.findByTestId('jamoa-tarix'))
    expect(await screen.findByText(/Rasulov D\. — Hujjatlar · chiqarildi/))
      .toBeTruthy()
    // Faol a'zolar orasida esa YO'Q.
    expect(screen.queryByTestId('jamoa-azo-3')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
describe('Vazifalar: umumiy va tender vazifasi ajratiladi', () => {
  it('umumiy vazifa "umumiy" deb belgilanadi va kartaga olib bormaydi',
    async () => {
      setPerms({ 'hisobot.deadline': 'full' })
      api.myTasks.mockResolvedValue(myTasks([UMUMIY]))
      const onOpen = vi.fn()
      render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={onOpen} />)

      expect(await screen.findByText('Sertifikatni yangilash')).toBeTruthy()
      expect(screen.getByText('umumiy')).toBeTruthy()
      // Kartaga o'tish tugmasi UMUMAN yo'q.
      expect(screen.queryByTestId('task-opp-2')).toBeNull()
    })

  it('tender vazifasi kartaga olib boradi', async () => {
    setPerms({ 'hisobot.deadline': 'full' })
    api.myTasks.mockResolvedValue(myTasks([vazifa()]))
    const onOpen = vi.fn()
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={onOpen} />)

    await userEvent.click(await screen.findByTestId('task-opp-1'))
    expect(onOpen).toHaveBeenCalledWith(7)
  })

  it('yuqori ustuvorlik ko‘rinadi, o‘rtasi ko‘rinmaydi', async () => {
    setPerms({ 'hisobot.deadline': 'full' })
    api.myTasks.mockResolvedValue(myTasks([vazifa(), UMUMIY]))
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)

    expect(await screen.findByText('Yuqori')).toBeTruthy()
    expect(screen.queryByText("O'rta")).toBeNull()
  })
})

// ---------------------------------------------------------------------------
describe('Vazifalar: holat va yaratish', () => {
  it('belgilash bajarildi qiladi, yechish QAYTA OCHADI', async () => {
    setPerms({ 'hisobot.deadline': 'full' })
    api.myTasks.mockResolvedValue(myTasks([vazifa()]))
    api.taskStatus.mockResolvedValue([])
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)

    await userEvent.click(await screen.findByTestId('task-done-1'))
    expect(api.taskStatus).toHaveBeenCalledWith(1, 'bajarildi')

    cleanup()
    api.myTasks.mockResolvedValue(myTasks([
      vazifa({ status: 'bajarildi', ochiq: false, done: true })]))
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)
    await userEvent.click(await screen.findByTestId('task-done-1'))
    expect(api.taskStatus).toHaveBeenLastCalledWith(1, 'yangi')
  })

  it('umumiy vazifa yaratiladi', async () => {
    setPerms({ 'hisobot.deadline': 'full', 'vazifa.yaratish': 'full',
               'vazifa.biriktirish': 'full' })
    api.myTasks.mockResolvedValue(myTasks([]))
    api.taskCreate.mockResolvedValue([UMUMIY])
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)

    await userEvent.click(await screen.findByTestId('vazifa-yangi'))
    await userEvent.type(screen.getByTestId('vazifa-nom'),
                         'Sertifikatni yangilash')
    await userEvent.click(screen.getByTestId('vazifa-saqla'))
    await waitFor(() => expect(api.taskCreate).toHaveBeenCalled())
    const arg = api.taskCreate.mock.calls[0][0]
    expect(arg.title).toBe('Sertifikatni yangilash')
    // KARTAGA BOG'LANMAGAN.
    expect(arg.opportunity_id).toBeNull()
  })

  it('yaratish huquqi yo‘q bo‘lsa tugma ko‘rinmaydi', async () => {
    setPerms({ 'hisobot.deadline': 'full' })
    api.myTasks.mockResolvedValue(myTasks([]))
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)
    await screen.findByText(/Vazifa yo'q/)
    expect(screen.queryByTestId('vazifa-yangi')).toBeNull()
  })

  it('biriktirish huquqi BOR bo‘lsa hodimlar ro‘yxati chiqadi', async () => {
    // IJOBIY JUFT. Usiz quyidagi "yo'q" tekshiruvi select UMUMAN
    // ochilmasa ham o'tardi — ya'ni hech narsani isbotlamasdi.
    setPerms({ 'hisobot.deadline': 'full', 'vazifa.yaratish': 'full',
               'vazifa.biriktirish': 'full' })
    api.myTasks.mockResolvedValue(myTasks([]))
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)

    await userEvent.click(await screen.findByTestId('vazifa-yangi'))
    fireEvent.keyDown(screen.getByTestId('vazifa-masul'), { key: 'ArrowDown' })
    expect(await screen.findByText('Aliyev B.')).toBeTruthy()
    // FAOLSIZ hodim esa ro'yxatda yo'q.
    expect(screen.queryByText('Eski X.')).toBeNull()
  })

  it('biriktirish huquqi yo‘q bo‘lsa faqat "o‘zimga" tanlanadi', async () => {
    setPerms({ 'hisobot.deadline': 'own', 'vazifa.yaratish': 'own' })
    api.myTasks.mockResolvedValue(myTasks([]))
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)

    await userEvent.click(await screen.findByTestId('vazifa-yangi'))
    // RADIX SELECT KLAVIATURA bilan ochiladi: jsdom da `click`
    // pointer capture zanjiriga tayanadi va ro'yxat ochilmaydi —
    // sinov esa "topilmadi" deb emas, JIMGINA o'tib ketardi.
    fireEvent.keyDown(screen.getByTestId('vazifa-masul'),
                      { key: 'ArrowDown' })
    // `findAll`: Radix tanlangan qiymatni TUGMADA ham ko'rsatadi,
    // ya'ni matn ikki joyda uchraydi.
    expect((await screen.findAllByText('O‘zimga')).length).toBeGreaterThan(0)
    // ASOSIY TEKSHIRUV: boshqa hodimlar ro'yxatda YO'Q — server
    // baribir rad etardi va tanlov "buzuq" bo'lib ko'rinardi.
    expect(screen.queryByText('Aliyev B.')).toBeNull()
    expect(screen.queryByText('Rasulov D.')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
describe('Vazifalar: filtrlar va yuklama', () => {
  it('filtr yoqilganda tekis ro‘yxat so‘raladi', async () => {
    setPerms({ 'hisobot.deadline': 'full' })
    api.myTasks.mockResolvedValue(myTasks([vazifa()]))
    api.taskList.mockResolvedValue([UMUMIY])
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)

    await screen.findByText('Marjani hisoblash')
    await userEvent.click(screen.getByTestId('filtr-kechikkan'))
    await waitFor(() => expect(api.taskList).toHaveBeenCalled())
    expect(api.taskList.mock.calls.at(-1)?.[0]).toMatchObject({ overdue: true })
    expect(await screen.findByTestId('filtrlangan-royxat')).toBeTruthy()
  })

  it('yuklama ochiladi va BAHO emasligi yoziladi', async () => {
    setPerms({ 'hisobot.deadline': 'full', 'vazifa.yuklama': 'full' })
    api.myTasks.mockResolvedValue(myTasks([]))
    api.workload.mockResolvedValue([
      { broker_id: 1, full_name: 'Karimov A.', active: true,
        ochiq_vazifa: 8, kechikkan: 2, bajarilgan: 14, ochiq_karta: 4 },
    ])
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)

    await userEvent.click(await screen.findByTestId('yuklama-och'))
    const qator = await screen.findByTestId('yuklama-1')
    expect(qator.textContent).toContain('Karimov A.')
    expect(qator.textContent).toContain('8')
    expect(qator.textContent).toContain('2')
    expect(screen.getByText(/baho emas/)).toBeTruthy()
  })

  it('yuklama huquqi yo‘q bo‘lsa bo‘lim ko‘rinmaydi', async () => {
    setPerms({ 'hisobot.deadline': 'own' })
    api.myTasks.mockResolvedValue(myTasks([]))
    render(<MyTasksPage brokers={BROKERS} onOpenOpportunity={vi.fn()} />)
    await screen.findByText(/Vazifa yo'q/)
    expect(screen.queryByTestId('yuklama-och')).toBeNull()
  })
})
