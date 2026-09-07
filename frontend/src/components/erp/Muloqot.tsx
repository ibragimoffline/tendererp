import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Icon from '../Icon'
import { cn } from '@/lib/utils'
import type {
  ErpChat, ErpChatLenta, ErpChatMember, ErpChatMembers, ErpChatMessage,
} from '@/types'
import { ErpError, can } from './erpShared'

// MULOQOT — hodim bilan hodim yozishmasi (`docs/erp_chat.md`).
//
// BU TENDER-AI DAGI "AI chat" EMAS. U yerda odam AI bilan gaplashadi;
// bu yerda odam odam bilan. Nomlash ham ataylab boshqa, aks holda
// ikkala ilovada ikkita "Chat" bo'lib, qaysi biri nima ekani
// tushunarsiz bo'lardi.
//
// YANGILANISH SO'ROV BILAN, 5 soniyada. WebSocket ataylab yo'q
// (§5): 5-15 hodimlik kompaniyada 5 s kechikish muammo emas, WebSocket
// esa joylashtirishga (Caddy, systemd) alohida talab qo'yadi. So'rov
// arzon: `after_id` bilan yuboriladi va javob odatda bo'sh.
//
// EKRAN IKKI JOYDA ISHLATILADI: yon paneldagi "Muloqot" bo'limi va
// karta oynasidagi "Muloqot" tabi. Ikkinchisida chat ro'yxati
// KO'RSATILMAYDI (`chatId` beriladi) — karta oynasida boshqa
// kartaning chatiga o'tish chalg'itardi.

/** So'rov oralig'i (ms). */
const POLL_MS = 5000

/** Taklif ro'yxatida ko'rsatiladigan eng ko'p hodim. */
const TAKLIF_MAX = 6

// `@` dan KURSORGACHA bo'lgan qism. Ikkinchi `@` va qator uzilishi uni
// tugatadi, ya'ni "@Ali va @Vali" da faqat OXIRGISI qidiriladi.
//
// BO'SH JOY ATAYLAB tugatmaydi: ism ikki so'zdan iborat ("Ism
// Familiya") va probelda to'xtasak, familiyani yozayotgan odamda
// taklif ro'yxati yo'qolib qolardi.
const AT_RE = /@([^@\n]{0,40})$/

interface Props {
  /** Berilsa — SHU chat ochiladi.
   *
   *  IKKI MA'NO, BITTA XOSSA:
   *    karta oynasida — ro'yxat KO'RSATILMAYDI (`oppId` bilan birga);
   *    bildirishnomadan — ro'yxat ko'rinadi, lekin shu chat tanlanadi.
   *  Farqni `royxatsiz` ajratadi. */
  chatId?: number
  /** Karta oynasidan: chat id sini kartadan olish. */
  oppId?: number
  /** Ekran balandligi: yon panelda to'liq, kartada past. */
  compact?: boolean
  /** Chat ro'yxatini yashirish (karta oynasi). */
  royxatsiz?: boolean
  /** O'qilganlik o'zgardi — tashqi hisoblagich yangilansin. */
  onUnreadChange?: () => void
}

export default function Muloqot(
  { chatId, oppId, compact, royxatsiz, onUnreadChange }: Props,
) {
  const { dateTimeFmt } = useFormat()
  const [chats, setChats] = useState<ErpChat[] | null>(null)
  const [aktiv, setAktiv] = useState<number | null>(chatId ?? null)
  const [lenta, setLenta] = useState<ErpChatLenta | null>(null)
  const [azolar, setAzolar] = useState<ErpChatMembers | null>(null)
  const [matn, setMatn] = useState('')
  const [javob, setJavob] = useState<ErpChatMessage | null>(null)
  const [tahrir, setTahrir] = useState<ErpChatMessage | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  // ESLATISH. Kalit — hisob id si, qiymat — TANLANGAN paytdagi ism.
  //
  // Ism saqlanadi, chunki yuborishdan oldin "bu ism matnda hali ham
  // turibdimi" deb tekshiriladi: foydalanuvchi `@Ism` ni o'chirsa id
  // ham ketishi kerak, aks holda ko'rinmaydigan eslatish yuborilardi.
  const [eslatilgan, setEslatilgan] = useState<Record<number, string>>({})
  const [taklif, setTaklif] = useState<ErpChatMember[]>([])
  const [kursor, setKursor] = useState(0)
  // ESKI TARIX: `lenta` OXIRGI sahifani beradi, bu esa undan
  // oldingilarini. Ikkalasi alohida saqlanadi, chunki so'rov
  // (polling) faqat oxirgisini yangilaydi va eski sahifalarni
  // qaytadan yuklab o'tirmasligi kerak.
  const [eski, setEski] = useState<ErpChatMessage[]>([])
  const [jim, setJim] = useState(false)
  const [yanaBor, setYanaBor] = useState(false)
  const oxiri = useRef<HTMLDivElement>(null)
  //: Eski tarix ochilganmi (yuqoridagi izohga qarang).
  const eskiRef = useRef(false)
  //: Tashqi hisoblagich chaqirig'i — o'zgaruvchan, lekin qayta
  //: yuklashga sabab bo'lmasin.
  const unreadRef = useRef(onUnreadChange)
  unreadRef.current = onUnreadChange
  const yolg = useRef(false)          // birinchi yuklashdan keyin pastga surish

  const yozaOladi = can('chat.yozish')
  const chiqara = can('chat.azo_chiqar')
  const qosha = can('chat.azo_qosh')

  // --- chat ro'yxati (faqat yon panelda) --------------------------------
  const chatlarniYukla = useCallback(async () => {
    try {
      const r = await api.chats()
      setChats(r)
      setAktiv((cur) => cur ?? (r.length ? r[0].id : null))
      // Jimlash holati ro'yxatdan emas, ochilgan chatdan olinadi —
      // shuning uchun bu yerda tegilmaydi.
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setChats([])
    }
  }, [])

  useEffect(() => {
    // BILDIRISHNOMADAN kelganda ham ro'yxat yuklanadi: odam bitta
    // chatga tushib, boshqasiga o'ta olishi kerak. Faqat karta
    // oynasida (`royxatsiz`) ro'yxat ko'rsatilmaydi.
    if (chatId) {
      setAktiv(chatId)
      if (!royxatsiz && !oppId) void chatlarniYukla()
      return
    }
    if (oppId) {
      api.oppChat(oppId)
        .then((r) => setAktiv(r.chat_id))
        .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      return
    }
    void chatlarniYukla()
  }, [chatId, oppId, royxatsiz, chatlarniYukla])

  // --- lenta -------------------------------------------------------------
  const lentaniYukla = useCallback(async (id: number, sokin = false) => {
    try {
      const r = await api.chatMessages(id)
      setLenta(r)
      // Faqat BIRINCHI yuklashda: keyin `eskiniYukla` o'zi qo'yadi,
      // aks holda so'rov (polling) "yana bor" ni qayta yoqib,
      // tugma allaqachon oxirigacha yuklangan chatda ham turardi.
      //
      // REF, HOLAT EMAS: agar bu qiymat `useCallback` bog'liqligiga
      // tushsa, "eskiroq xabarlar" bosilishi funksiya identikligini
      // o'zgartirardi -> effekt qayta ishga tushardi -> lenta
      // QAYTADAN yuklanardi. Ya'ni tarixni ochish har safar oxirgi
      // sahifani qayta so'rardi.
      if (!eskiRef.current) setYanaBor(r.yana)
      if (!sokin) setErr('')
      // O'QILGAN deb belgilaymiz — hisoblagich lentani ochgan zahoti
      // nolga tushsin, keyingi so'rovni kutmasin.
      //
      // BU YERDA "ro'yxat ko'rindi" EMAS, "chat OCHILDI va oxirgi
      // xabar ekranda" degani (§10): lenta aynan shu chat uchun
      // so'ralgan va uning oxirgi id si ma'lum.
      const oxirgi = r.messages.at(-1)?.id
      if (oxirgi) {
        await api.chatRead(id, oxirgi)
        // REF orqali: chaqiruvchi bu funksiyani odatda ichma-ich
        // (`() => ...`) beradi va u har render'da YANGI bo'ladi.
        // Bog'liqlikka qo'yilsa effekt cheksiz qayta ishga tushardi.
        unreadRef.current?.()
      }
    } catch (e) {
      if (!sokin) setErr(e instanceof Error ? e.message : String(e))
      setLenta(null)
    }
  }, [])

  /** ESKI TARIXNI yuklash. Serverdagi `before_id` bo'yicha —
   *  vaqt bo'yicha emas, aks holda bir vaqtda yozilgan ikki xabar
   *  chegarada takrorlanardi yoki tushib qolardi. */
  async function eskiniYukla() {
    const chegara = eski[0]?.id ?? lenta?.eng_eski_id
    if (!aktiv || !chegara) return
    setBusy(true)
    eskiRef.current = true
    try {
      const r = await api.chatMessages(aktiv, { before_id: chegara })
      setEski((p) => [...r.messages, ...p])
      setYanaBor(r.yana)
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!aktiv) return
    yolg.current = false
    // CHAT ALMASHDI — eski sahifalar TOZALANADI. Aks holda boshqa
    // chatning tarixi yangisining tepasida qolib ketardi.
    setEski([])
    setYanaBor(false)
    eskiRef.current = false
    void lentaniYukla(aktiv)
    api.chatMembers(aktiv).then(setAzolar).catch(() => setAzolar(null))
  }, [aktiv, lentaniYukla])

  // SO'ROV: ochiq chat va ro'yxat birga yangilanadi. Xato JIM
  // o'tkaziladi — tarmoq bir soniyaga uzilsa ekranga qizil chiqmasin.
  useEffect(() => {
    if (!aktiv) return
    const t = setInterval(() => {
      void lentaniYukla(aktiv, true)
      if (!royxatsiz && !oppId) void api.chats().then(setChats).catch(() => {})
    }, POLL_MS)
    return () => clearInterval(t)
  }, [aktiv, royxatsiz, oppId, lentaniYukla])

  // Yangi xabar kelganda pastga suriladi.
  useEffect(() => {
    if (!lenta) return
    oxiri.current?.scrollIntoView({ behavior: yolg.current ? 'smooth' : 'auto' })
    yolg.current = true
  }, [lenta?.messages.length])

  // --- eslatish (@ism) ---------------------------------------------------
  // RO'YXAT FAQAT SHU CHATNING FAOL A'ZOLARIDAN. A'zo bo'lmagan
  // hodimni eslatib bo'lmaydi: "eslatdim, lekin u chatni ko'rmaydi"
  // degan holat chiqardi. Kerak bo'lsa avval chatga qo'shiladi.
  function matnOzgardi(v: string, caret: number) {
    setMatn(v)
    setKursor(caret)
    const m = AT_RE.exec(v.slice(0, caret))
    if (!m || !azolar) { setTaklif([]); return }
    const q = m[1].toLowerCase()
    setTaklif(azolar.members
      .filter((a) => a.active && a.full_name.toLowerCase().includes(q))
      .slice(0, TAKLIF_MAX))
  }

  function tanla(a: ErpChatMember) {
    const oldi = matn.slice(0, kursor).replace(AT_RE, `@${a.full_name} `)
    setMatn(oldi + matn.slice(kursor))
    setKursor(oldi.length)
    setEslatilgan((p) => ({ ...p, [a.app_user_id]: a.full_name }))
    setTaklif([])
  }

  /** MATNDA hali ham turgan eslatishlar. Foydalanuvchi ismni
   *  o'chirgan bo'lsa id ham ketadi — server ham tekshiradi, lekin
   *  ko'rinmaydigan eslatishni umuman yubormaslik to'g'riroq. */
  function joriyEslatishlar(): number[] {
    return Object.entries(eslatilgan)
      .filter(([, nom]) => matn.includes(`@${nom}`))
      .map(([id]) => Number(id))
  }

  async function yubor() {
    if (!aktiv || !matn.trim()) return
    setBusy(true)
    try {
      const mentions = joriyEslatishlar()
      if (tahrir) {
        await api.chatEdit(aktiv, tahrir.id, matn.trim(),
                           mentions.length ? mentions : undefined)
        setTahrir(null)
      } else {
        await api.chatSend(aktiv, {
          text: matn.trim(), reply_to_id: javob?.id ?? null,
          mentions: mentions.length ? mentions : undefined,
        })
        setJavob(null)
      }
      setMatn('')
      setEslatilgan({})
      setTaklif([])
      await lentaniYukla(aktiv)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function ochir(m: ErpChatMessage, oziniki: boolean) {
    if (!aktiv) return
    // BOSHQANING xabarini o'chirishda sabab MAJBURIY — u muallifga
    // bildirishnoma bo'lib boradi. Buni oldindan aytamiz.
    let izoh: string | null = null
    if (!oziniki) {
      izoh = window.prompt(
        "Sabab (majburiy) — muallifga yuboriladi:")
      if (!izoh || !izoh.trim()) return
    } else if (!window.confirm(
      "Xabar o'chirilsinmi? Matn lentadan yo'qoladi, "
      + 'lekin tarixda saqlanadi.')) {
      return
    }
    setBusy(true)
    try {
      await api.chatDelete(aktiv, m.id, izoh?.trim())
      await lentaniYukla(aktiv)
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function azoOzgart(fn: () => Promise<ErpChatMembers>) {
    setBusy(true)
    try {
      setAzolar(await fn())
      if (aktiv) await lentaniYukla(aktiv)
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function jimlaTugma() {
    if (!aktiv) return
    setBusy(true)
    try {
      const r = await api.chatMute(aktiv, !jim)
      setJim(r.jim)
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const arxiv = !!lenta?.chat.arxiv
  const azoman = !!lenta?.chat.azoman
  const kontekst = lenta?.chat.kontekst ?? null
  // ESKI + OXIRGI sahifa birga. Takrorlanish bo'lmasligi serverda
  // ta'minlangan (`before_id` qat'iy `<`), lekin bu yerda ham
  // qo'riqlanadi: bir marta yuklangan xabar ikki marta chizilsa
  // React kalit takrorlanishidan ogohlantiradi va tartib buziladi.
  const barcha = (() => {
    const kor = new Set(lenta?.messages.map((m) => m.id) ?? [])
    return [...eski.filter((m) => !kor.has(m.id)), ...(lenta?.messages ?? [])]
  })()

  return (
    <div className={cn('flex gap-4', compact ? 'h-[26rem]' : 'h-[calc(100vh-11rem)]')}
      data-testid="muloqot">
      {/* --- CHAT RO'YXATI (karta oynasida ko'rsatilmaydi) --- */}
      {!royxatsiz && !oppId && (
        <aside className="w-64 shrink-0 overflow-y-auto rounded-lg border bg-surface-2 p-1.5"
          data-testid="chat-royxat">
          {chats === null && (
            <p className="p-2 text-body text-muted-foreground">Yuklanmoqda…</p>
          )}
          {chats?.length === 0 && (
            <p className="p-2 text-body text-muted-foreground">Chat yo'q.</p>
          )}
          {chats?.map((c) => (
            <button key={c.id} type="button" onClick={() => setAktiv(c.id)}
              className={cn('flex w-full items-center gap-2 rounded-md px-2.5 py-2',
                'text-left text-body transition-colors',
                c.id === aktiv ? 'bg-secondary font-semibold text-primary'
                  : 'hover:bg-accent')}>
              <Icon name={c.turi === 'umumiy' ? 'user' : 'briefcase'}
                className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">
                {c.title || `#${c.opportunity_id}`}
              </span>
              {c.arxiv && (
                <span className="text-micro text-muted-foreground">arxiv</span>
              )}
              {c.oqilmagan > 0 && (
                <span className="rounded-full bg-primary px-1.5 text-micro
                                 font-semibold text-on-primary">
                  {c.oqilmagan}
                </span>
              )}
            </button>
          ))}
        </aside>
      )}

      {/* --- LENTA --- */}
      <section className="flex min-w-0 flex-1 flex-col rounded-lg border bg-card">
        <header className="border-b px-3 py-2" data-testid="chat-header">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 truncate text-lead font-semibold">
              {lenta?.chat.title || 'Muloqot'}
            </h3>
            {arxiv && (
              <span className="rounded-md bg-muted px-1.5 py-0.5 text-micro
                               text-muted-foreground">
                arxiv — faqat o'qish
              </span>
            )}
            <div className="ml-auto flex items-center gap-2">
              {azolar && !azolar.virtual && (
                <span className="text-caption text-muted-foreground">
                  {azolar.members.length} a'zo
                </span>
              )}
              {azolar?.virtual && (
                <span className="text-caption text-muted-foreground">
                  barcha hodimlar
                </span>
              )}
              {aktiv && (
                // JIMLASH — bildirishnoma kelmasin, lekin O'QILMAGAN
                // hisoblagichi ISHLAYVERADI (serverdagi qoida). Ikkisini
                // bitta tugmaga bog'lash odam yozishmani butunlay
                // yo'qotib qo'yishiga olib kelardi.
                <button type="button" disabled={busy} data-testid="jimla"
                  onClick={() => void jimlaTugma()}
                  title={jim ? 'Bildirishnoma o‘chirilgan' : 'Jimlash'}
                  className="text-caption text-muted-foreground hover:text-foreground">
                  {jim ? '🔕' : '🔔'}
                </button>
              )}
            </div>
          </div>

          {/* KONTEKST (§6) — "qaysi tender haqida yozyapman" degan
              savol EKRANDA javobsiz qolmasin. Karta chatida har doim
              ko'rinadi; umumiy chatda karta yo'q va sarlavha ham yo'q
              (bo'sh maydonlar chalg'itardi). */}
          {kontekst && (
            <dl data-testid="chat-kontekst"
              className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-micro">
              <div className="flex gap-1">
                <dt className="text-muted-foreground">Holat:</dt>
                <dd className="font-medium">{kontekst.status_label}</dd>
              </div>
              <div className="flex gap-1">
                <dt className="text-muted-foreground">Mas'ul:</dt>
                <dd className="font-medium">{kontekst.masul || '—'}</dd>
              </div>
              <div className="flex gap-1">
                <dt className="text-muted-foreground">Muddat:</dt>
                <dd className="font-medium">
                  {kontekst.deadline_at ? dateTimeFmt(kontekst.deadline_at) : '—'}
                </dd>
              </div>
              {kontekst.customer_name && (
                <div className="flex min-w-0 gap-1">
                  <dt className="text-muted-foreground">Buyurtmachi:</dt>
                  <dd className="truncate font-medium">{kontekst.customer_name}</dd>
                </div>
              )}
            </dl>
          )}
        </header>

        {err && <div className="px-3 pt-2"><ErpError msg={err} /></div>}

        <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3"
          data-testid="lenta">
          {yanaBor && (
            <button type="button" disabled={busy} data-testid="eski-yukla"
              onClick={() => void eskiniYukla()}
              className="mx-auto block rounded-md border px-3 py-1
                         text-caption text-muted-foreground hover:bg-accent
                         disabled:opacity-50">
              Eskiroq xabarlar
            </button>
          )}
          {barcha.length === 0 && (
            <p className="text-body text-muted-foreground">
              Hali xabar yo'q — birinchi bo'lib yozing.
            </p>
          )}
          {barcha.map((m) => (
            <Xabar key={m.id} m={m} arxiv={arxiv}
              vaqt={m.created_at ? dateTimeFmt(m.created_at) : ''}
              onJavob={() => setJavob(m)}
              onTahrir={() => { setTahrir(m); setMatn(m.text || '') }}
              onOchir={(oz) => void ochir(m, oz)} />
          ))}
          <div ref={oxiri} />
        </div>

        {/* --- A'ZOLAR (ro'yxatli chatda) --- */}
        {azolar && !azolar.virtual && (
          <div className="flex flex-wrap items-center gap-1.5 border-t px-3 py-2">
            {azolar.members.map((a) => (
              <span key={a.app_user_id}
                className="flex items-center gap-1 rounded-md bg-surface-2 px-2
                           py-0.5 text-caption">
                {a.full_name}
                {chiqara && !arxiv && (
                  <button type="button" disabled={busy}
                    aria-label={`${a.full_name} — chiqarish`}
                    className="text-muted-foreground hover:text-urgent-strong"
                    onClick={() => void azoOzgart(
                      () => api.chatMemberRemove(azolar.chat_id, a.app_user_id))}>
                    ×
                  </button>
                )}
              </span>
            ))}
            {qosha && !arxiv && !azoman && aktiv && (
              // "O'ZIMNI QO'SHISH" — rahbar chatni a'zosiz o'qiydi,
              // lekin yozish uchun qo'shilishi kerak va bu qo'shilish
              // lentada KO'RINADI.
              <Button variant="outline" size="sm" disabled={busy}
                onClick={() => void azoOzgart(
                  () => api.chatMemberAdd(aktiv))}>
                Chatga qo'shilish
              </Button>
            )}
          </div>
        )}

        {/* --- YOZISH --- */}
        <footer className="border-t px-3 py-2">
          {javob && (
            <div className="mb-1.5 flex items-center gap-2 text-caption
                            text-muted-foreground">
              <span className="truncate">
                Javob: {javob.author_name} — {(javob.text || '').slice(0, 60)}
              </span>
              <button type="button" onClick={() => setJavob(null)}>×</button>
            </div>
          )}
          {tahrir && (
            <div className="mb-1.5 flex items-center gap-2 text-caption
                            text-muted-foreground">
              <span>Tahrirlanmoqda</span>
              <button type="button"
                onClick={() => { setTahrir(null); setMatn('') }}>×</button>
            </div>
          )}
          {arxiv ? (
            <p className="text-body text-muted-foreground">
              Chat arxivlangan — karta yakunlangan. Kartani qayta ochsangiz
              muloqot ham ochiladi.
            </p>
          ) : !yozaOladi ? (
            <p className="text-body text-muted-foreground">
              Yozish uchun ruxsatingiz yo'q.
            </p>
          ) : !azoman ? (
            <p className="text-body text-muted-foreground">
              Yozish uchun avval chatga qo'shiling — qo'shilganingiz
              lentada ko'rinadi.
            </p>
          ) : (
            <div className="relative flex items-end gap-2">
              {/* @ISM TAKLIFI — faqat shu chatning faol a'zolari. */}
              {taklif.length > 0 && (
                <ul role="listbox" aria-label="Eslatish uchun hodimlar"
                  className="absolute bottom-full left-0 z-10 mb-1 w-64
                             overflow-hidden rounded-md border bg-popover shadow-lg">
                  {taklif.map((a) => (
                    <li key={a.app_user_id}>
                      <button type="button"
                        className="w-full px-3 py-1.5 text-left text-body hover:bg-accent"
                        onClick={() => tanla(a)}>
                        {a.full_name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <Input
                value={matn} disabled={busy}
                aria-label="Xabar matni"
                placeholder="Xabar… (@ bilan hodimni eslatish)"
                onChange={(e) => matnOzgardi(
                  e.target.value, e.target.selectionStart ?? e.target.value.length)}
                onKeyDown={(e) => {
                  // Taklif ochiq bo'lsa Escape uni yopadi, Enter esa
                  // xabarni YUBORMAYDI: odam ismni tanlamoqchi edi.
                  if (e.key === 'Escape' && taklif.length) {
                    e.preventDefault(); setTaklif([]); return
                  }
                  if (e.key === 'Enter' && taklif.length) {
                    e.preventDefault(); tanla(taklif[0]); return
                  }
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void yubor()
                  }
                }} />
              <Button size="sm" disabled={busy || !matn.trim()}
                onClick={() => void yubor()}>
                {tahrir ? 'Saqlash' : 'Yuborish'}
              </Button>
            </div>
          )}
        </footer>
      </section>
    </div>
  )
}

/** Bitta xabar. Tizim xabari boshqacha ko'rinadi: u muloqot emas, jurnal. */
function Xabar({ m, arxiv, vaqt, onJavob, onTahrir, onOchir }: {
  m: ErpChatMessage
  arxiv: boolean
  vaqt: string
  onJavob: () => void
  onTahrir: () => void
  onOchir: (oziniki: boolean) => void
}) {
  if (m.tizim) {
    return (
      <p className="text-center text-caption text-muted-foreground">
        {m.text} <span className="text-micro">· {vaqt}</span>
      </p>
    )
  }
  // O'CHIRILGAN xabar YO'QOLMAYDI: kim va nega o'chirgani yoziladi.
  // Bo'sh joy "hech narsa bo'lmagan" degan ma'no berardi.
  if (m.ochirilgan) {
    return (
      <p className="text-body italic text-muted-foreground">
        Xabar o'chirildi{m.ochirdi ? ` — ${m.ochirdi}` : ''}
        {m.ochirish_izohi ? ` (${m.ochirish_izohi})` : ''}
        <span className="ml-1 text-micro">· {vaqt}</span>
      </p>
    )
  }
  return (
    <div className="rounded-md border bg-surface-2 px-3 py-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-body font-semibold">{m.author_name}</span>
        <span className="text-micro text-muted-foreground">{vaqt}</span>
        {m.tahrirlangan && (
          <span className="text-micro text-muted-foreground">tahrirlangan</span>
        )}
        {!arxiv && (
          <span className="ml-auto flex gap-1">
            <Button variant="ghost" size="sm" onClick={onJavob}>Javob</Button>
            <Button variant="ghost" size="sm" onClick={onTahrir}>Tahrir</Button>
            <Button variant="ghost" size="sm"
              onClick={() => onOchir(true)}>O'chirish</Button>
          </span>
        )}
      </div>
      {m.reply && (
        <p className="mt-1 border-l-2 pl-2 text-caption text-muted-foreground">
          {m.reply.author_name}: {m.reply.ochirilgan
            ? "(o'chirilgan xabar)" : m.reply.text}
        </p>
      )}
      <p className="mt-1 whitespace-pre-wrap text-body">{m.text}</p>
    </div>
  )
}
