import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { cn } from '@/lib/utils'
import Icon from '../Icon'
import type { ErpNotification } from '@/types'

// BILDIRISHNOMA QO'NG'IROG'I — "menga nima keldi".
//
// NEGA KERAK: yo'naltirish oqimi (`api/erp/topshiriq.py`) kartani
// O'ZI ochadi. Xabar bo'lmasa hodim buni faqat kartalar ekranini
// ochib, ro'yxatni ko'zdan kechirganda bilardi — ya'ni "sizga ish
// berildi" degan gap hech qayerda aytilmasdi.
//
// SO'ROV ORALIG'I: 60 soniya. Bu ERP — soniyalar muhim emas, lekin
// "ertalab keldim va 3 ta yangi karta bor" degan holat ko'rinishi
// kerak. WebSocket qo'shish bitta hisoblagich uchun ortiqcha
// qurilma bo'lardi.
//
// O'QILGAN DEB BELGILASH — RO'YXAT OCHILGANDA, avtomatik emas:
// o'qimasdan yopilgan xabar hisoblagichdan tushib qolmasin.

const ORALIQ_MS = 60_000

const NISHON: Record<string, string> = {
  topshiriq: 'plus',
  taqsimlanmagan: 'alert',
  bekor: 'close',
  otkazildi: 'right',
  muddat: 'clock',
}

export default function NotificationBell(
  { onOpenOpportunity }: { onOpenOpportunity?: (id: number) => void },
) {
  const f = useFormat()
  const [ochiq, setOchiq] = useState(false)
  const [items, setItems] = useState<ErpNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [ready, setReady] = useState(true)
  const timer = useRef<number | null>(null)

  const yukla = useCallback(() => {
    api.notifications()
      .then((r) => { setItems(r.items); setUnread(r.unread); setReady(r.ready) })
      // Xato JIM yutiladi: qo'ng'iroq — yordamchi qism va u
      // yiqilgani uchun butun ekranga xato chiqarish noto'g'ri
      // bo'lardi (ish ma'lumoti baribir joyida).
      .catch(() => { /* qo'ng'iroq ishlamasa ish to'xtamaydi */ })
  }, [])

  useEffect(() => {
    yukla()
    timer.current = window.setInterval(yukla, ORALIQ_MS)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [yukla])

  async function och() {
    const yangi = !ochiq
    setOchiq(yangi)
    if (yangi) {
      yukla()
      // Ro'yxat OCHILGANDA belgilanadi — ya'ni odam ko'rgan bo'ladi.
      if (unread > 0) {
        await api.readNotifications().catch(() => null)
        setUnread(0)
      }
    }
  }

  if (!ready) return null

  return (
    <div className="relative">
      <button onClick={() => void och()}
        className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-caption text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
        <Icon name="bell" size={14} />
        Bildirishnomalar
        {unread > 0 && (
          <span className="ml-auto rounded-full bg-urgent px-1.5 py-px text-micro font-semibold text-urgent-foreground">
            {unread}
          </span>
        )}
      </button>

      {ochiq && (
        <div className="absolute bottom-full left-0 z-40 mb-1 max-h-96 w-80 overflow-y-auto rounded-lg border bg-popover p-2 shadow-lg">
          {items.length === 0 ? (
            <div className="px-2 py-3 text-caption text-muted-foreground">
              Xabar yo'q.
            </div>
          ) : (
            <ul className="divide-y">
              {items.map((n) => (
                <li key={n.id} className={cn('py-2', !n.read_at && 'bg-secondary/40')}>
                  <button
                    className="w-full px-2 text-left"
                    onClick={() => {
                      setOchiq(false)
                      if (n.opportunity_id) onOpenOpportunity?.(n.opportunity_id)
                    }}>
                    <div className="flex items-baseline gap-1.5">
                      <Icon name={NISHON[n.kind] || 'plus'} size={12}
                        className="text-muted-foreground" />
                      <span className="text-micro font-semibold text-muted-foreground">
                        {n.kind_label}
                      </span>
                      <span className="ml-auto text-micro text-muted-foreground">
                        {f.dateFmt(n.created_at)}
                      </span>
                    </div>
                    <div className="mt-0.5 text-caption">{n.matn}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
