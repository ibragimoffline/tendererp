import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { cn } from '@/lib/utils'
import Icon from '../Icon'
import type { ErpNishon, ErpNotification } from '@/types'

// BILDIRISHNOMA MARKAZI — "menga nima keldi va u qayerga olib boradi".
//
// NEGA KERAK: yo'naltirish oqimi (`api/erp/topshiriq.py`) kartani
// O'ZI ochadi. Xabar bo'lmasa hodim buni faqat kartalar ekranini
// ochib, ro'yxatni ko'zdan kechirganda bilardi — ya'ni "sizga ish
// berildi" degan gap hech qayerda aytilmasdi.
//
// SO'ROV ORALIG'I: 60 soniya. Bu ERP — soniyalar muhim emas, lekin
// "ertalab keldim va 3 ta yangi karta bor" degan holat ko'rinishi
// kerak. WebSocket qo'shish bitta hisoblagich uchun ortiqcha
// qurilma bo'lardi (`docs/erp_chat.md` §5 bilan bir xil qaror).
//
// O'QILGAN DEB BELGILASH — QAYSI HODISADA (§10)
// ═════════════════════════════════════════════
// Ro'yxat OCHILGANI o'qilgan degani EMAS. Ilgari shunday edi va
// natijada odam qo'ng'iroqni bexosdan bosib yopsa, hisoblagich
// nolga tushardi — o'qilmagan xabar esa ro'yxat ichida qolib
// ketardi va hech qachon ko'zga tashlanmasdi.
//
// Endi ikki aniq hodisa:
//   * BITTASI — o'sha qatorni bosganda (u kontekstga o'tadi, ya'ni
//     haqiqatan ko'rgan bo'ladi);
//   * HAMMASI — faqat "hammasini o'qildi" tugmasi bosilganda.
//
// KLIK MANZILINI SERVER AYTADI (`nishon`): ekran o'z qoidasini
// tutmasin. Aks holda yangi hodisa turi qo'shilganda u jimgina
// "hech qayerga olib bormaydigan" bildirishnoma bo'lib qolardi.

/** So'rov oralig'i (ms). */
const ORALIQ_MS = 60_000

/** Bir sahifada nechta. "Yana yuklash" shundan keyin chiqadi. */
const SAHIFA = 15

const NISHON: Record<string, string> = {
  topshiriq: 'plus',
  taqsimlanmagan: 'alert',
  bekor: 'close',
  otkazildi: 'right',
  biriktirish_olib_tashlandi: 'right',
  muddat: 'clock',
  hujjat_muddat: 'clip',
  status: 'refresh',
  vazifa: 'check',
  qaror: 'alert',
  tizim: 'alert',
  chat_yangi: 'user',
  chat_mention: 'user',
  chat_qoshildi: 'user',
  chat_ochirildi: 'close',
}

export interface NotificationBellProps {
  onOpenOpportunity?: (id: number) => void
  /** Chat bildirishnomasi — AYNAN o'sha chatni ochadi (§15). */
  onOpenChat?: (chatId: number, oppId: number | null) => void
  /** Tashqaridan berilgan hisoblagich (yon paneldagi yagona manba). */
  unread?: number
  /** O'qilganlik o'zgardi — tashqaridagi hisoblagich yangilansin. */
  onChange?: () => void
}

export default function NotificationBell(
  { onOpenOpportunity, onOpenChat, unread: tashqiUnread, onChange }:
  NotificationBellProps,
) {
  const f = useFormat()
  const [ochiq, setOchiq] = useState(false)
  const [items, setItems] = useState<ErpNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [yana, setYana] = useState(false)
  const [ready, setReady] = useState(true)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const timer = useRef<number | null>(null)
  // TASHQI HISOBLAGICH BERILGANMI. Ref, chunki `yukla` uni
  // o'qiydi va u so'rov oralig'ida o'zgarishi mumkin.
  const tashqiRef = useRef(tashqiUnread)
  tashqiRef.current = tashqiUnread

  const yukla = useCallback(async (jim = false) => {
    try {
      const r = await api.notifications(false, undefined)
      setItems(r.items.slice(0, SAHIFA))
      // TASHQI RAQAM USTUN: yon panel `GET /erp/unread` dan yagona
      // manba sifatida oladi. Bu yerda ham yozib qo'yilsa, ikkita
      // so'rov ikki xil paytda tugab, ekranda ikki xil son
      // ko'rinardi — odam "3 ta xabar" deb ochib, hech narsa
      // topmasdi.
      if (typeof tashqiRef.current !== 'number') setUnread(r.unread)
      setYana(r.yana || r.items.length > SAHIFA)
      setReady(r.ready)
      setErr('')
    } catch (e) {
      // XATO KO'RSATILADI, lekin faqat ro'yxat OCHIQ bo'lsa: yopiq
      // qo'ng'iroq ostida qizil yozuv turishi ma'nosiz. Fon so'rovi
      // (`jim`) esa umuman jim o'tadi — tarmoq bir soniyaga uzilsa
      // ekranga xato chiqmasin.
      if (!jim) setErr(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void yukla(true)
    timer.current = window.setInterval(() => void yukla(true), ORALIQ_MS)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [yukla])

  // Tashqi hisoblagich (yon panel) ustun: ikki raqam ajralib
  // ketmasin.
  useEffect(() => {
    if (typeof tashqiUnread === 'number') setUnread(tashqiUnread)
  }, [tashqiUnread])

  async function och() {
    const yangi = !ochiq
    setOchiq(yangi)
    // OCHILGANDA belgilanMAYDI — yuqoridagi izohga qarang.
    if (yangi) await yukla()
  }

  async function yanaYukla() {
    const oxirgi = items.at(-1)?.id
    if (!oxirgi) return
    setBusy(true)
    try {
      const r = await api.notifications(false, oxirgi)
      setItems((p) => [...p, ...r.items])
      setYana(r.yana)
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function belgila(ids?: number[]) {
    setBusy(true)
    try {
      const r = await api.readNotifications(ids)
      setUnread(r.unread)
      setItems((p) => p.map((n) => (
        !ids || ids.includes(n.id)
          ? { ...n, read_at: n.read_at ?? new Date().toISOString() }
          : n)))
      setErr('')
      onChange?.()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  /** KLIK: aniq kontekstga o'tish + o'qilgan deb belgilash.
   *  Nishonsiz bildirishnoma ham o'qilgan bo'ladi — shunchaki
   *  hech qayerga o'tmaydi (umumiy panelga OLIB BORMAYDI). */
  function bos(n: ErpNotification) {
    const t: ErpNishon = n.nishon
    setOchiq(false)
    void belgila([n.id])
    if (t?.turi === 'chat' && t.id) onOpenChat?.(t.id, t.opportunity_id)
    else if (t?.opportunity_id) onOpenOpportunity?.(t.opportunity_id)
  }

  if (!ready) return null

  return (
    <div className="relative" data-testid="notification-bell">
      <button onClick={() => void och()} data-testid="bell-toggle"
        aria-expanded={ochiq}
        className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-caption text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
        <Icon name="bell" size={14} />
        Bildirishnomalar
        {unread > 0 && (
          <span data-testid="bell-count"
            className="ml-auto rounded-full bg-urgent px-1.5 py-px text-micro font-semibold text-urgent-foreground">
            {unread}
          </span>
        )}
      </button>

      {ochiq && (
        <div data-testid="bell-panel"
          className="absolute bottom-full left-0 z-40 mb-1 flex max-h-[70vh] w-80 max-w-[calc(100vw-2rem)] flex-col rounded-lg border bg-popover shadow-lg">
          <div className="flex items-center gap-2 border-b px-2 py-1.5">
            <span className="text-micro font-semibold text-muted-foreground">
              {unread > 0 ? `${unread} ta o'qilmagan` : 'Hammasi o‘qilgan'}
            </span>
            {unread > 0 && (
              <button data-testid="mark-all" disabled={busy}
                onClick={() => void belgila()}
                className="ml-auto text-micro text-primary hover:underline disabled:opacity-50">
                Hammasini o‘qildi
              </button>
            )}
          </div>

          {err && (
            // XATO HOLATI + QAYTA URINISH. Jim yutilsa odam "xabar
            // yo'q" deb o'ylardi, aslida esa so'rov yiqilgan bo'lardi.
            <div data-testid="bell-error"
              className="flex items-center gap-2 border-b bg-urgent/10 px-2 py-1.5 text-micro text-urgent">
              <span className="min-w-0 flex-1 truncate">{err}</span>
              <button onClick={() => void yukla()} className="underline">
                Qayta urinish
              </button>
            </div>
          )}

          <ul className="min-h-0 flex-1 divide-y overflow-y-auto">
            {items.length === 0 && !err && (
              <li className="px-2 py-3 text-caption text-muted-foreground">
                Xabar yo'q.
              </li>
            )}
            {items.map((n) => (
              <li key={n.id} className={cn('py-2', !n.read_at && 'bg-secondary/40')}>
                <button data-testid={`notif-${n.id}`}
                  className="w-full px-2 text-left"
                  onClick={() => bos(n)}>
                  <div className="flex items-baseline gap-1.5">
                    <Icon name={NISHON[n.kind] || 'plus'} size={12}
                      className="text-muted-foreground" />
                    <span className="text-micro font-semibold text-muted-foreground">
                      {n.kind_label}
                    </span>
                    <span className="ml-auto shrink-0 text-micro text-muted-foreground">
                      {f.dateFmt(n.created_at)}
                    </span>
                  </div>
                  <div className="mt-0.5 text-caption">{n.matn}</div>
                  {n.opportunity_title && (
                    <div className="mt-0.5 truncate text-micro text-muted-foreground">
                      {n.opportunity_title}
                    </div>
                  )}
                </button>
              </li>
            ))}
          </ul>

          {yana && (
            <button data-testid="bell-more" disabled={busy}
              onClick={() => void yanaYukla()}
              className="border-t px-2 py-1.5 text-micro text-primary hover:bg-accent disabled:opacity-50">
              Yana yuklash
            </button>
          )}
        </div>
      )}
    </div>
  )
}
