import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ErpNotification } from '@/types'

// BILDIRISHNOMA VA MULOQOT — EKRANDAGI QARORLAR sinovi.
//
// NEGA ALOHIDA FAYL: `qoidalar.test.tsx` pul va huquq qoidalarini
// qo'riqlaydi. Bu yerdagi qoidalar boshqa sinfdan va ular JIM
// buziladi — ekran xato bermaydi, shunchaki xabar ko'rinmay qoladi:
//
//   1. RO'YXAT OCHILGANI "O'QILDI" DEGANI EMAS (§10). Ilgari shunday
//      edi: qo'ng'iroqni bexosdan bosgan odam hisoblagichni nolga
//      tushirardi va o'qilmagan xabar ro'yxat ichida ko'milib qolardi.
//   2. KLIK ANIQ KONTEKSTGA OLIB BORADI (§15). Chat bildirishnomasi
//      chatni ochishi kerak, "umumiy panelni" emas.
//   3. KARTA CHATIDA KONTEKST KO'RINADI (§6) — odam qaysi tender
//      haqida yozayotganini bilishi kerak.
//   4. XATO YASHIRILMAYDI va QAYTA URINISH bor: jim yutilgan xato
//      "xabar yo'q" bo'lib ko'rinardi.
//
// NIMA TEKSHIRILMAYDI: ranglar, oraliqlar, joylashuv (mavjud sinov
// fayli bilan bir xil qoida).

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {}
}

const api = {
  notifications: vi.fn(), readNotifications: vi.fn(), unread: vi.fn(),
  chats: vi.fn(), chatMessages: vi.fn(), chatSend: vi.fn(),
  chatEdit: vi.fn(), chatDelete: vi.fn(), chatMembers: vi.fn(),
  chatMemberAdd: vi.fn(), chatMemberRemove: vi.fn(), chatRead: vi.fn(),
  chatMute: vi.fn(), oppChat: vi.fn(),
}
vi.mock('@/api', () => ({ api, ApiError: class extends Error {} }))

const { default: NotificationBell } =
  await import('../components/erp/NotificationBell')
const { default: Muloqot } = await import('../components/erp/Muloqot')
const { setPerms } = await import('../components/erp/erpShared')

function bildirishnoma(p: Partial<ErpNotification> = {}): ErpNotification {
  return {
    id: 1, kind: 'chat_yangi', kind_label: 'Yangi xabar',
    matn: 'Karimov: narx tayyor',
    opportunity_id: 7, opportunity_title: 'Server tenderi',
    chat_id: 3, task_id: null, chat_title: 'Server tenderi',
    nishon: { turi: 'chat', id: 3, opportunity_id: 7 },
    havola: null, created_at: '2026-09-06T10:00:00+05:00', read_at: null,
    ...p,
  }
}

function royxat(items: ErpNotification[], yana = false) {
  return { ready: true, items, unread: items.filter((n) => !n.read_at).length,
           yana }
}

function xabar(id: number, text: string) {
  return {
    id, chat_id: 3, author_id: 5, author_name: 'Karimov', tizim: false,
    text, ochirilgan: false, ochirdi: null, ochirish_izohi: null,
    reply_to_id: null, created_at: '2026-09-06T10:00:00+05:00',
    edited_at: null, tahrirlangan: false,
  }
}

const KONTEKST = {
  opportunity_id: 7, title: 'Server uskunalari yetkazib berish',
  status: 'preparing', status_label: 'Tayyorlanmoqda',
  masul: 'Karimov A.', customer_name: 'Sog‘liqni saqlash vazirligi',
  deadline_at: '2026-09-12T18:00:00+05:00',
}

function lenta(messages = [xabar(10, 'salom')], extra = {}) {
  return {
    chat: {
      id: 3, turi: 'opportunity', opportunity_id: 7,
      title: 'Server tenderi', arxiv: false, azoman: true,
      kontekst: KONTEKST,
    },
    messages, eng_eski_id: messages[0]?.id ?? null, yana: false, ...extra,
  }
}

afterEach(() => { cleanup(); setPerms(null) })

beforeEach(() => {
  vi.clearAllMocks()
  const never = new Promise(() => {})
  for (const f of Object.values(api)) f.mockReturnValue(never)
})

// ---------------------------------------------------------------------------
describe('Bildirishnoma markazi: o‘qilganlik', () => {
  it('ro‘yxat OCHILGANI o‘qilgan degani emas', async () => {
    api.notifications.mockResolvedValue(royxat([bildirishnoma()]))
    api.readNotifications.mockResolvedValue({ belgilandi: 0, unread: 1 })
    render(<NotificationBell />)

    await userEvent.click(await screen.findByTestId('bell-toggle'))
    await screen.findByTestId('bell-panel')
    // ENG MUHIM TEKSHIRUV: ochilish O'ZI hech narsani belgilamaydi.
    expect(api.readNotifications).not.toHaveBeenCalled()
    expect(screen.getByTestId('bell-count').textContent).toContain('1')
  })

  it('"hammasini o‘qildi" — AYNAN shu tugma bosilganda', async () => {
    api.notifications.mockResolvedValue(royxat([bildirishnoma()]))
    api.readNotifications.mockResolvedValue({ belgilandi: 1, unread: 0 })
    const onChange = vi.fn()
    render(<NotificationBell onChange={onChange} />)

    await userEvent.click(await screen.findByTestId('bell-toggle'))
    await userEvent.click(await screen.findByTestId('mark-all'))
    // `ids` YO'Q = hammasi.
    expect(api.readNotifications).toHaveBeenCalledWith(undefined)
    await waitFor(() => expect(onChange).toHaveBeenCalled())
    // Hisoblagich yo'qoladi.
    expect(screen.queryByTestId('bell-count')).toBeNull()
  })

  it('bittasini bosish uni o‘qilgan qiladi', async () => {
    api.notifications.mockResolvedValue(royxat([bildirishnoma({ id: 42 })]))
    api.readNotifications.mockResolvedValue({ belgilandi: 1, unread: 0 })
    render(<NotificationBell />)

    await userEvent.click(await screen.findByTestId('bell-toggle'))
    await userEvent.click(await screen.findByTestId('notif-42'))
    expect(api.readNotifications).toHaveBeenCalledWith([42])
  })
})

// ---------------------------------------------------------------------------
describe('Bildirishnoma markazi: klik ANIQ kontekstga olib boradi', () => {
  it('chat bildirishnomasi CHATni ochadi (kartani emas)', async () => {
    api.notifications.mockResolvedValue(royxat([bildirishnoma()]))
    api.readNotifications.mockResolvedValue({ belgilandi: 1, unread: 0 })
    const onOpenChat = vi.fn()
    const onOpenOpportunity = vi.fn()
    render(<NotificationBell onOpenChat={onOpenChat}
      onOpenOpportunity={onOpenOpportunity} />)

    await userEvent.click(await screen.findByTestId('bell-toggle'))
    await userEvent.click(await screen.findByTestId('notif-1'))
    expect(onOpenChat).toHaveBeenCalledWith(3, 7)
    // Karta OCHILMAYDI: chat aniqroq kontekst.
    expect(onOpenOpportunity).not.toHaveBeenCalled()
  })

  it('karta bildirishnomasi kartani ochadi', async () => {
    api.notifications.mockResolvedValue(royxat([bildirishnoma({
      id: 2, kind: 'status', kind_label: 'Karta holati o‘zgardi',
      chat_id: null, nishon: { turi: 'opportunity', id: 7, opportunity_id: 7 },
    })]))
    api.readNotifications.mockResolvedValue({ belgilandi: 1, unread: 0 })
    const onOpenOpportunity = vi.fn()
    render(<NotificationBell onOpenOpportunity={onOpenOpportunity} />)

    await userEvent.click(await screen.findByTestId('bell-toggle'))
    await userEvent.click(await screen.findByTestId('notif-2'))
    expect(onOpenOpportunity).toHaveBeenCalledWith(7)
  })

  it('nishonsiz bildirishnoma hech qayerga olib bormaydi', async () => {
    // "Umumiy panelga tashlash" ATAYLAB yo'q (§15): odam nima haqida
    // ekanini qaytadan qidirardi.
    api.notifications.mockResolvedValue(royxat([bildirishnoma({
      id: 3, kind: 'tizim', chat_id: null, opportunity_id: null,
      opportunity_title: null,
      nishon: { turi: null, id: null, opportunity_id: null },
    })]))
    api.readNotifications.mockResolvedValue({ belgilandi: 1, unread: 0 })
    const onOpenChat = vi.fn()
    const onOpenOpportunity = vi.fn()
    render(<NotificationBell onOpenChat={onOpenChat}
      onOpenOpportunity={onOpenOpportunity} />)

    await userEvent.click(await screen.findByTestId('bell-toggle'))
    await userEvent.click(await screen.findByTestId('notif-3'))
    expect(onOpenChat).not.toHaveBeenCalled()
    expect(onOpenOpportunity).not.toHaveBeenCalled()
    // Lekin O'QILGAN bo'ladi — odam uni ko'rdi.
    expect(api.readNotifications).toHaveBeenCalledWith([3])
  })
})

// ---------------------------------------------------------------------------
describe('Bildirishnoma markazi: xato va sahifalash', () => {
  it('xato KO‘RSATILADI va qayta urinish bor', async () => {
    api.notifications.mockRejectedValue(new Error('Tarmoq uzildi'))
    render(<NotificationBell />)

    await userEvent.click(await screen.findByTestId('bell-toggle'))
    const xato = await screen.findByTestId('bell-error')
    expect(xato.textContent).toContain('Tarmoq uzildi')

    api.notifications.mockResolvedValue(royxat([bildirishnoma()]))
    await userEvent.click(screen.getByText('Qayta urinish'))
    await waitFor(() => expect(screen.queryByTestId('bell-error')).toBeNull())
    expect(await screen.findByTestId('notif-1')).toBeTruthy()
  })

  it('"yana yuklash" ESKIROQLARINI so‘raydi', async () => {
    api.notifications.mockResolvedValueOnce(
      royxat([bildirishnoma({ id: 9 })], true))
    render(<NotificationBell />)
    await userEvent.click(await screen.findByTestId('bell-toggle'))

    api.notifications.mockResolvedValueOnce(
      royxat([bildirishnoma({ id: 5, read_at: '2026-09-05T10:00:00+05:00' })]))
    await userEvent.click(await screen.findByTestId('bell-more'))
    // `before_id` = ekrandagi ENG OXIRGI qatorning id si.
    await waitFor(() => expect(api.notifications)
      .toHaveBeenLastCalledWith(false, 9))
    expect(await screen.findByTestId('notif-5')).toBeTruthy()
  })

  it('tashqi hisoblagich ustun — ikki raqam ajralib ketmasin', async () => {
    api.notifications.mockResolvedValue(royxat([bildirishnoma()]))
    const { rerender } = render(<NotificationBell unread={4} />)
    expect((await screen.findByTestId('bell-count')).textContent)
      .toContain('4')
    rerender(<NotificationBell unread={0} />)
    await waitFor(() =>
      expect(screen.queryByTestId('bell-count')).toBeNull())
  })
})

// ---------------------------------------------------------------------------
describe('Muloqot: karta chatida KONTEKST ko‘rinadi', () => {
  it('holat, mas’ul, muddat va buyurtmachi yoziladi', async () => {
    setPerms({ 'chat.yozish': 'full', 'chat.korish': 'full' })
    api.chatMessages.mockResolvedValue(lenta())
    api.chatMembers.mockResolvedValue({
      chat_id: 3, turi: 'opportunity', virtual: false, members: [] })
    api.chatRead.mockResolvedValue({ last_read_id: 10 })
    render(<Muloqot chatId={3} royxatsiz compact />)

    const k = await screen.findByTestId('chat-kontekst')
    expect(k.textContent).toContain('Tayyorlanmoqda')
    expect(k.textContent).toContain('Karimov A.')
    expect(k.textContent).toContain('Sog‘liqni saqlash vazirligi')
  })

  it('umumiy chatda kontekst YO‘Q (bo‘sh maydon chalg‘itardi)', async () => {
    setPerms({ 'chat.yozish': 'full', 'chat.korish': 'full' })
    api.chatMessages.mockResolvedValue({
      chat: { id: 1, turi: 'umumiy', opportunity_id: null, title: 'Umumiy',
              arxiv: false, azoman: true, kontekst: null },
      messages: [xabar(1, 'hammaga salom')], eng_eski_id: 1, yana: false })
    api.chatMembers.mockResolvedValue({
      chat_id: 1, turi: 'umumiy', virtual: true, members: [] })
    api.chatRead.mockResolvedValue({ last_read_id: 1 })
    render(<Muloqot chatId={1} royxatsiz compact />)

    await screen.findByTestId('chat-header')
    expect(screen.queryByTestId('chat-kontekst')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
describe('Muloqot: tarix va o‘qilganlik', () => {
  it('chat ochilganda OXIRGI sahifa keladi va o‘qilgan deb belgilanadi',
    async () => {
      setPerms({ 'chat.yozish': 'full', 'chat.korish': 'full' })
      api.chatMessages.mockResolvedValue(lenta([xabar(50, 'oxirgi gap')]))
      api.chatMembers.mockResolvedValue({
        chat_id: 3, turi: 'opportunity', virtual: false, members: [] })
      api.chatRead.mockResolvedValue({ last_read_id: 50 })
      const onUnreadChange = vi.fn()
      render(<Muloqot chatId={3} royxatsiz compact
        onUnreadChange={onUnreadChange} />)

      expect(await screen.findByText('oxirgi gap')).toBeTruthy()
      // O'QILGAN CHEGARASI ekrандagi OXIRGI xabar bo'yicha suriladi.
      await waitFor(() => expect(api.chatRead).toHaveBeenCalledWith(3, 50))
      await waitFor(() => expect(onUnreadChange).toHaveBeenCalled())
    })

  it('"eskiroq xabarlar" before_id bilan so‘raladi va tepaga qo‘shiladi',
    async () => {
      setPerms({ 'chat.yozish': 'full', 'chat.korish': 'full' })
      api.chatMessages.mockResolvedValueOnce(
        lenta([xabar(50, 'yangi gap')], { yana: true, eng_eski_id: 50 }))
      api.chatMembers.mockResolvedValue({
        chat_id: 3, turi: 'opportunity', virtual: false, members: [] })
      api.chatRead.mockResolvedValue({ last_read_id: 50 })
      render(<Muloqot chatId={3} royxatsiz compact />)

      await screen.findByText('yangi gap')
      api.chatMessages.mockResolvedValueOnce(
        lenta([xabar(10, 'eski gap')], { yana: false, eng_eski_id: 10 }))
      await userEvent.click(await screen.findByTestId('eski-yukla'))

      await waitFor(() => expect(api.chatMessages)
        .toHaveBeenLastCalledWith(3, { before_id: 50 }))
      expect(await screen.findByText('eski gap')).toBeTruthy()
      // Ikkalasi ham ekranda — eskisi yangisini ALMASHTIRMAYDI.
      expect(screen.getByText('yangi gap')).toBeTruthy()
    })

  it('xato lentada KO‘RSATILADI', async () => {
    setPerms({ 'chat.yozish': 'full', 'chat.korish': 'full' })
    api.chatMessages.mockRejectedValue(new Error('Bu chatning a’zosi emassiz.'))
    api.chatMembers.mockRejectedValue(new Error('yo‘q'))
    render(<Muloqot chatId={3} royxatsiz compact />)
    expect(await screen.findByText(/a’zosi emassiz/)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
describe('Muloqot: jimlash', () => {
  it('jimlash tugmasi holatni almashtiradi', async () => {
    setPerms({ 'chat.yozish': 'full', 'chat.korish': 'full' })
    api.chatMessages.mockResolvedValue(lenta())
    api.chatMembers.mockResolvedValue({
      chat_id: 3, turi: 'opportunity', virtual: false, members: [] })
    api.chatRead.mockResolvedValue({ last_read_id: 10 })
    api.chatMute.mockResolvedValue({ chat_id: 3, jim: true })
    render(<Muloqot chatId={3} royxatsiz compact />)

    const tugma = await screen.findByTestId('jimla')
    expect(tugma.textContent).toContain('🔔')
    await userEvent.click(tugma)
    expect(api.chatMute).toHaveBeenCalledWith(3, true)
    await waitFor(() =>
      expect(screen.getByTestId('jimla').textContent).toContain('🔕'))
  })
})

// ---------------------------------------------------------------------------
describe('Muloqot: yozish huquqi', () => {
  it('a’zo bo‘lmagan odamga sabab OCHIQ aytiladi', async () => {
    setPerms({ 'chat.yozish': 'full', 'chat.korish': 'full' })
    api.chatMessages.mockResolvedValue(
      lenta([xabar(10, 'gap')], {
        chat: { id: 3, turi: 'opportunity', opportunity_id: 7,
                title: 'Server tenderi', arxiv: false, azoman: false,
                kontekst: KONTEKST } }))
    api.chatMembers.mockResolvedValue({
      chat_id: 3, turi: 'opportunity', virtual: false, members: [] })
    api.chatRead.mockResolvedValue({ last_read_id: 10 })
    render(<Muloqot chatId={3} royxatsiz compact />)
    // "Jimgina kuzatib turib yozish" YO'Q: rahbar ham qo'shilishi kerak.
    expect(await screen.findByText(/avval chatga qo'shiling/)).toBeTruthy()
  })

  it('huquqi yo‘q bo‘lsa yozish maydoni ko‘rsatilmaydi', async () => {
    setPerms({ 'chat.korish': 'full' })
    api.chatMessages.mockResolvedValue(lenta())
    api.chatMembers.mockResolvedValue({
      chat_id: 3, turi: 'opportunity', virtual: false, members: [] })
    api.chatRead.mockResolvedValue({ last_read_id: 10 })
    render(<Muloqot chatId={3} royxatsiz compact />)
    expect(await screen.findByText(/ruxsatingiz yo'q/)).toBeTruthy()
  })
})
