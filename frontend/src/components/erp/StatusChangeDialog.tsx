import { useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Button } from '@/components/ui/button'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { ErpStatus, Opportunity } from '@/types'

// Status o'zgarishini TASDIQLASH oynasi. Ikki holatda ochiladi:
//   1) yakuniy statusga o'tish (Yutildi / Yutqazildi / Rad etildi) — bu
//      kartani yopadi, tasodifiy sudrab tashlash qimmatga tushadi;
//   2) yakuniydan qaytish — server izohsiz 400 beradi (sabab tarixda qolishi
//      kerak), shuning uchun izoh maydoni MAJBURIY.
// Qolgan ochiq->ochiq o'tishlar tasdiqsiz o'tadi: kundalik ish sekinlashmasin.

interface StatusChangeDialogProps {
  o: Opportunity
  to: ErpStatus
  /** yutqazish sabablari (`/erp/meta`); 'lost' ga o'tishda so'raladi */
  lostReasons?: { code: string; label: string }[]
  onCancel: () => void
  onConfirm: (note: string | null, lostReason: string | null) => void
}

export default function StatusChangeDialog(
  { o, to, lostReasons, onCancel, onConfirm }: StatusChangeDialogProps,
) {
  const [note, setNote] = useState('')
  const [reason, setReason] = useState<string | null>(null)
  const reopening = o.is_final && !to.final
  // Yutqazish sababi MAJBURIY: "nega yutqazdik?" degan savolga javob bo'lmasa
  // keyingi tahlil ham bo'lmaydi. Sabab — ro'yxatdan, erkin matn emas.
  const needReason = to.code === 'lost' && !!lostReasons?.length
  const canSave = (!reopening || note.trim().length > 0) && (!needReason || !!reason)

  return (
    <Dialog.Root open onOpenChange={(x) => { if (!x) onCancel() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-foreground/40 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content className={cn(
          'fixed left-1/2 top-1/2 z-50 w-[min(28rem,calc(100vw-2rem))]',
          '-translate-x-1/2 -translate-y-1/2 rounded-lg border bg-popover p-5 shadow-lg',
          'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
        )}>
          <Dialog.Title className="text-lead font-semibold">
            {reopening ? 'Kartani qayta ochish' : `Status: ${to.label}`}
          </Dialog.Title>
          <Dialog.Description className="mt-1.5 text-body text-muted-foreground">
            {reopening
              ? 'Yakuniy statusdan qaytarilmoqda — sabab tarixda qoladi, shuning uchun izoh majburiy.'
              : `Karta yopiladi va "${to.label}" deb belgilanadi.`}
          </Dialog.Description>

          {needReason && (
            <div className="mt-3">
              <div className="mb-1 text-caption font-semibold text-muted-foreground">
                Yutqazish sababi
              </div>
              <Select value={reason ?? ''} onValueChange={setReason}>
                <SelectTrigger className="h-9 w-full bg-card text-body">
                  <SelectValue placeholder="Tanlang" />
                </SelectTrigger>
                <SelectContent>
                  {lostReasons!.map((r) => (
                    <SelectItem key={r.code} value={r.code}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <textarea
            autoFocus
            className="mt-3 min-h-20 w-full rounded-md border bg-card px-3 py-2 text-body outline-none focus-visible:border-primary"
            placeholder={reopening ? 'Nega qayta ochilmoqda?' : 'Izoh (ixtiyoriy)'}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />

          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={onCancel}>Bekor</Button>
            <Button size="sm" disabled={!canSave}
              onClick={() => onConfirm(note.trim() || null, reason)}>
              Tasdiqlash
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
