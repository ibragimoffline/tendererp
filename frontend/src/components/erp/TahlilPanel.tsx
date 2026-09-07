import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import type { ErpTahlil, TahlilBolim } from '@/types'

// TENDER-AI TAHLILI — qaror PAYTIDAGI surat.
//
// NEGA SNAPSHOT: qoidalar (moslik, malaka, cheklist, ombor mosligi)
// Tender-AI da va ularning ikkinchi nusxasi bo'lmasligi kerak. ERP
// ularni qayta hisoblamaydi — u qaror paytida yozilgan NUSXANI
// ko'rsatadi. Tender-AI da ma'lumot keyin o'zgarsa, bu blok
// o'zgarmaydi va aynan shu kerak: broker qaysi ma'lumotga qarab ish
// boshlaganini keyin ham ko'rish mumkin.
//
// IKKI QOIDA EKRANDA
// ══════════════════
// 1. YIQILGAN BO'LIM YASHIRILMAYDI. Tender-AI da biror qism
//    hisoblanmagan bo'lsa ("ombor: xato") shu yerda sababi bilan
//    ko'rinadi. Bo'limni jimgina tashlab ketish "hammasi joyida"
//    degan yolg'on taassurot qoldirardi.
//
// 2. TALAB "TASDIQLANGAN" DEB O'QILMASIN. Tender-AI da talablarning
//    inson tomonidan tasdiqlanishi 0 marta ishlatilgan
//    (`UPDATED.md` §18). Shuning uchun tasdiqlanmagan talab ochiq
//    "ko'rilmagan" yorlig'i bilan chiqadi.

const ISHONCH_YORLIQ: Record<string, string> = {
  erp_sessiya: 'tasdiqlangan',
  aktor_elon: 'e‘lon qilingan',
  kompaniya_sessiyasi: 'hodim ko‘rsatilmagan',
  servis: 'avtomat',
}

const BOLIM_NOMI: Record<string, string> = {
  moslik: 'Moslik',
  ai: 'AI tavsiyasi',
  malaka: 'Malaka',
  talablar: 'Talablar',
  cheklist: 'Cheklist',
  ombor: 'Ombor',
  narx: 'Narx',
  havolalar: 'Havolalar',
}

const TARTIB = ['moslik', 'ai', 'malaka', 'talablar', 'cheklist', 'ombor',
  'narx', 'havolalar']

const HOLAT_RANG: Record<string, string> = {
  ok: 'text-ok-strong',
  fail: 'text-destructive',
  risk: 'text-soon-strong',
  malumot_yoq: 'text-muted-foreground',
}

type Bolim = TahlilBolim<Record<string, unknown>>

function qiymat(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'ha' : 'yo‘q'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** Talab TASDIQLANGANMI. Tender-AI da `review_status` — `approved`
 *  bo'lmasa odam ko'rmagan. */
function korilmagan(t: Record<string, unknown>): boolean {
  return (t.holat ?? 'pending_review') !== 'approved'
}

export default function TahlilPanel({ oppId }: { oppId: number }) {
  const f = useFormat()
  const [items, setItems] = useState<ErpTahlil[] | null>(null)
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    setItems(null); setIdx(0)
    api.tahlil(oppId)
      .then((r) => setItems(r.items))
      // Tahlil — QO'SHIMCHA ma'lumot. U kelmasa karta ochilaveradi.
      .catch(() => setItems([]))
  }, [oppId])

  if (items === null) return <Skeleton className="h-24 w-full rounded-lg" />
  // Qo'lda ochilgan kartada tahlil bo'lmaydi — blok umuman
  // ko'rsatilmaydi (bo'sh quti "nimadir yo'qolgan" degan taassurot
  // qoldirardi).
  if (items.length === 0) return null

  const t = items[idx]
  const p = (t.payload || {}) as Record<string, Bolim>

  return (
    <section className="mt-5">
      <h3 className="mb-2 flex flex-wrap items-baseline gap-2 text-caption font-semibold text-muted-foreground">
        Tahlil (Tender-AI)
        <span className="tabular font-normal">{f.dateFmt(t.captured_at)}</span>
        {t.ishonch && (
          <span className="rounded bg-secondary px-1.5 py-px text-micro font-semibold text-primary">
            {ISHONCH_YORLIQ[t.ishonch] || t.ishonch}
          </span>
        )}
        {items.length > 1 && (
          <span className="ml-auto flex items-center gap-1 font-normal">
            {items.map((x, i) => (
              <button key={x.id} type="button"
                onClick={() => setIdx(i)}
                className={cn('rounded px-1.5 py-px text-micro',
                  i === idx ? 'bg-secondary font-semibold text-primary'
                    : 'text-muted-foreground hover:bg-accent')}>
                {i === 0 ? 'oxirgi' : f.dateFmt(x.captured_at)}
              </button>
            ))}
          </span>
        )}
      </h3>

      <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
        {TARTIB.filter((k) => p[k]).map((k) => (
          <Bolimcha key={k} nom={BOLIM_NOMI[k] || k} kalit={k} b={p[k]} />
        ))}
      </div>
    </section>
  )
}

function Bolimcha({ nom, kalit, b }: { nom: string; kalit: string; b: Bolim }) {
  // YIQILGAN BO'LIM — sababi bilan (yuqoridagi 1-qoida).
  if (!b.ok) {
    return (
      <div className="text-caption">
        <span className="font-semibold">{nom}:</span>{' '}
        <span className="text-soon-strong">olinmadi — {b.xato || 'sabab yozilmagan'}</span>
      </div>
    )
  }
  const d = (b.data || {}) as Record<string, unknown>

  if (kalit === 'talablar') {
    const royxat = (d.royxat as Record<string, unknown>[]) || []
    return (
      <div className="text-caption">
        <div className="font-semibold">{nom}</div>
        {royxat.length === 0 && (
          <div className="text-muted-foreground">Talab ajratilmagan.</div>
        )}
        <ul className="mt-1 space-y-1">
          {royxat.slice(0, 10).map((t, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-1.5">
              {/* 2-QOIDA: ko'rilmagan talab OCHIQ belgilanadi */}
              {korilmagan(t) && (
                <span className="rounded bg-soon-soft px-1.5 py-px text-micro font-semibold text-soon-strong">
                  ko'rilmagan
                </span>
              )}
              <span>{qiymat(t.matn)}</span>
              {!!t.file_ref && (
                <span className="text-micro text-muted-foreground">
                  ({qiymat(t.file_ref)})
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  if (kalit === 'malaka') {
    const mezonlar = (d.mezonlar as Record<string, unknown>[]) || []
    return (
      <div className="text-caption">
        <div className="font-semibold">
          {nom}: {qiymat(d.qaror)}
          {!!d.sabab && (
            <span className="ml-1 font-normal text-muted-foreground">
              — {qiymat(d.sabab)}
            </span>
          )}
        </div>
        <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
          {mezonlar.map((m, i) => (
            <li key={i} className={HOLAT_RANG[String(m.status)] || ''}>
              {qiymat(m.label)}: {qiymat(m.status)}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  if (kalit === 'havolalar') {
    return (
      <div className="flex flex-wrap gap-3 text-caption">
        <span className="font-semibold">{nom}:</span>
        {d.manba_url ? (
          <a className="underline" href={String(d.manba_url)}
            target="_blank" rel="noopener noreferrer">Manbadagi e'lon</a>
        ) : <span className="text-muted-foreground">manba havolasi yo'q</span>}
        {d.tender_ai_url ? (
          <a className="underline" href={String(d.tender_ai_url)}
            target="_blank" rel="noopener noreferrer">Tender-AI</a>
        ) : (
          <span className="text-muted-foreground">
            Tender-AI havolasi yo'q{d.tender_ai_url_sababi
              ? ` (${qiymat(d.tender_ai_url_sababi)})` : ''}
          </span>
        )}
      </div>
    )
  }

  // Qolganlari: kalit-qiymat qatori. Ichki ro'yxatlar soni bilan
  // ko'rsatiladi — butun JSON ni yoyish ekranni ko'mib tashlardi.
  return (
    <div className="text-caption">
      <span className="font-semibold">{nom}:</span>{' '}
      {Object.entries(d).map(([k, v]) => (
        <span key={k} className="mr-3">
          <span className="text-muted-foreground">{k}:</span>{' '}
          {Array.isArray(v) ? `${v.length} ta` : qiymat(v)}
        </span>
      ))}
    </div>
  )
}
