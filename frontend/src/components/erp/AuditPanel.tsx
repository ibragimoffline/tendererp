import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { cn } from '@/lib/utils'
import type { AuditReport } from '@/types'

// O'ZGARISHLAR JURNALI — "kim, qachon va nimani o'zgartirdi?"
//
// Ekranda IKKI SAVOL turadi va ular teng emas:
//
//   1. `after_issue` — CHIQARILGAN hujjatga tegilganmi? Faktura
//      `issued` bo'lgach o'zgarmasligi kerak; qatorlar va to'lovlar
//      qo'shilishi esa normal, shuning uchun ular alohida turdagi
//      yozuv sifatida ko'rinadi.
//   2. `outside_erp` — o'zgarish ERP interfeysidan TASHQARIDA
//      qilinganmi (to'g'ridan-to'g'ri SQL). Bu eng qizig'i: ilova
//      qoidalari bunday o'zgarishni to'sa olmaydi.
//
// "HAMMASI JOYIDA" degan javob ham AYTILADI. Bo'sh ro'yxat
// "tekshirilmadi" degani emas — buni ochiq yozmasa, foydalanuvchi
// jurnal ishlayaptimi yoki yo'qmi bilmaydi.

export default function AuditPanel() {
  const f = useFormat()
  const [d, setD] = useState<AuditReport | null>(null)
  const [onlyBad, setOnlyBad] = useState(false)

  useEffect(() => {
    // 503 — patch qo'llanmagan; 403 — broker. Ikkalasida ham panel
    // jim yashiriladi.
    api.audit({ days: 30, limit: 100, only_outside: onlyBad })
      .then(setD).catch(() => setD(null))
  }, [onlyBad])

  if (!d) return null
  const s = d.summary

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-body font-semibold">
          Hujjat o'zgarishlari ({d.days} kun)
        </h2>
        <label className="flex items-center gap-1.5 text-caption text-muted-foreground">
          <input type="checkbox" checked={onlyBad}
            onChange={(e) => setOnlyBad(e.target.checked)} />
          faqat ERP dan tashqaridagilar
        </label>
      </div>

      {/* Yig'ma javob — ro'yxatni o'qimasdan holat ma'lum bo'lsin. */}
      {d.clean ? (
        <p className="mb-3 text-caption text-ok-strong">
          Shubhali o'zgarish yo'q — {s.n} ta yozuv tekshirildi.
        </p>
      ) : (
        <p className="mb-3 text-caption text-urgent-strong">
          {s.after_issue > 0 && (
            <>Chiqarilgan hujjatga {s.after_issue} ta o'zgarish. </>
          )}
          {s.outside_erp > 0 && (
            <>ERP dan <b>tashqarida</b> qilingan: {s.outside_erp} ta.</>
          )}
        </p>
      )}

      {d.items.length === 0 ? (
        <p className="text-caption text-muted-foreground">
          Bu davrda yozuv yo'q.
        </p>
      ) : (
        <ul className="divide-y">
          {d.items.map((r) => (
            <li key={r.id}
              className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 py-1.5 text-body">
              <span className="font-medium">
                {r.doc_label} #{r.doc_id}
              </span>
              <span className="text-muted-foreground">
                {r.entity_label} {r.action_label}
              </span>
              {r.field && (
                <span className="tabular text-caption">
                  <b>{r.field}</b>
                  {': '}
                  <span className="text-muted-foreground">
                    {r.old_value ?? '—'}
                  </span>
                  {' → '}
                  {r.new_value ?? '—'}
                </span>
              )}
              {r.after_issue && (
                <span className="rounded bg-secondary px-1.5 py-px text-micro
                                 font-semibold text-soon-strong"
                  title={`Hujjat holati: ${r.doc_status}`}>
                  chiqarilgandan keyin
                </span>
              )}
              {r.outside_erp && (
                <span className="rounded bg-secondary px-1.5 py-px text-micro
                                 font-semibold text-urgent-strong"
                  title="To'g'ridan-to'g'ri bazaga yozilgan">
                  ERP dan tashqarida
                </span>
              )}
              <span className="ml-auto flex shrink-0 items-baseline gap-2
                               text-caption text-muted-foreground">
                <span>{r.actor || 'noma’lum'}</span>
                <span className="tabular">{f.dateTimeFmt(r.created_at)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className={cn('mt-2 text-micro text-muted-foreground')}>
        Jurnalni baza o'zi yozadi — uni o'zgartirib bo'lmaydi.
      </p>
    </section>
  )
}
