import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Icon from '../Icon'
import { cn } from '@/lib/utils'
import type { ErpMeta, OpportunityFile } from '@/types'
import { ErpError, can } from './erpShared'

// SABAB HUJJATI — "nega yutqazdik / to'xtatdik / ulgurmadik" tafsiloti.
//
// NEGA `lost_reason` YETARLI EMAS: u ro'yxatdan bitta KOD (narx, muddat,
// hujjat...). Kod tasniflash uchun kerak — uni `GROUP BY` qilib bo'ladi
// va rahbar paneli shundan hisoblaydi. Lekin "aynan nima bo'ldi" degan
// savolga javob bermaydi: buyurtmachi xati, raqobatchi narxi, ichki
// yozuv. Ikkalasi BIRGA yuradi, biri ikkinchisining o'rnini bosmaydi.
//
// FAYL IXTIYORIY va bu ATAYLAB. Majburiy qilinsa broker dialogdan
// chiqish uchun bo'sh fayl yuklaydi va bizda "hujjat bor" degan YOLG'ON
// ko'rsatkich paydo bo'ladi — u hujjat umuman bo'lmaganidan yomonroq.
//
// SHUNING UCHUN YO'QLIGI OCHIQ YOZILADI. Blok yopiq kartada har doim
// ko'rinadi: "Sabab hujjati: yo'q". Jimgina bo'sh joy "biriktirilmagan"
// degani ham, "bu yerda bunday narsa yo'q" degani ham bo'lib ko'rinardi.

const KB = 1024

/** Hajmni odam o'qiydigan ko'rinishda. */
function hajm(n: number): string {
  if (n < KB) return `${n} B`
  if (n < KB * KB) return `${Math.round(n / KB)} KB`
  return `${(n / (KB * KB)).toFixed(1)} MB`
}

interface Props {
  oppId: number
  /** Kartaning HOZIRGI statusi — biriktirish shu holatlarda ochiladi. */
  oppStatus: string
  meta?: ErpMeta | null
}

export default function SababFayl({ oppId, oppStatus, meta }: Props) {
  const { dateTimeFmt } = useFormat()
  const [rows, setRows] = useState<OpportunityFile[] | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [izoh, setIzoh] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // Serverdan kelgan ro'yxat — ekran o'z nusxasini TUTMAYDI. Turlar yoki
  // holatlar o'zgarsa bitta joyda o'zgaradi (`api/erp/fayl.py`).
  const holatlar = meta?.fayl_holatlar ?? []
  const turlar = meta?.fayl_turlar ?? []
  const maxHajm = meta?.fayl_max_hajm ?? 0
  const yopiq = holatlar.includes(oppStatus)
  const tahrir = can('karta.fayl')

  const load = useCallback(async () => {
    try {
      setRows(await api.oppFiles(oppId))
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setRows([])
    }
  }, [oppId])

  useEffect(() => { void load() }, [load])

  // Patch qo'llanmagan bo'lsa blok UMUMAN ko'rsatilmaydi: "yuklash
  // ishlamadi" degan jim xato o'rniga bo'lmagan narsa ko'rinmaydi.
  if (meta && meta.fayl_ready === false) return null

  async function yukla(f: File) {
    setBusy(true)
    try {
      await api.addOppFile(oppId, f, izoh.trim() || undefined)
      setIzoh('')
      if (inputRef.current) inputRef.current.value = ''
      await load()
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function ochir(f: OpportunityFile) {
    // O'chirish IZ QOLDIRADI (`erp.doc_audit`) va buni oldindan aytamiz:
    // "bu amal yozib qo'yiladi" degani odamni ogohlantiradi, keyin
    // bilib qolgandan ko'ra.
    if (!window.confirm(
      `"${f.fayl_nom}" o'chirilsinmi?\n\n`
      + 'Fayl butunlay o\'chadi. O\'chirilgani jurnalda qoladi: '
      + 'kim, qachon va qaysi fayl.')) return
    setBusy(true)
    try {
      await api.deleteOppFile(f.id)
      await load()
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const bor = (rows?.length ?? 0) > 0

  return (
    <section className="mt-5" data-testid="sabab-fayl">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <h3 className="text-lead font-semibold">Sabab hujjati</h3>
        {/* YO'QLIGI OCHIQ YOZILADI — bo'sh joy emas. */}
        {rows !== null && !bor && (
          <span className="text-body text-muted-foreground">
            yo'q — biriktirilmagan
          </span>
        )}
      </div>

      {err && <ErpError msg={err} />}

      {bor && (
        <ul className="space-y-1.5">
          {rows!.map((f) => (
            <li key={f.id}
              className={cn('flex flex-wrap items-center gap-2 rounded-md',
                'border bg-surface-2 px-3 py-2 text-body')}>
              <Icon name="clip" className="size-4 shrink-0 text-muted-foreground" />
              <button type="button"
                onClick={() => void api.downloadOppFile(f.id, f.fayl_nom)}
                className="font-medium text-primary hover:underline">
                {f.fayl_nom}
              </button>
              <span className="text-muted-foreground">{hajm(f.hajm)}</span>
              {f.izoh && <span className="text-muted-foreground">· {f.izoh}</span>}
              <span className="ml-auto text-caption text-muted-foreground">
                {f.created_by || '—'}
                {f.created_at ? ` · ${dateTimeFmt(f.created_at)}` : ''}
              </span>
              {tahrir && (
                <Button variant="ghost" size="sm" disabled={busy}
                  onClick={() => void ochir(f)}>
                  O'chirish
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* --- BIRIKTIRISH ---
          Uch holatning har biri SABABINI aytadi. Tugmani sababsiz
          yashirish "nega yo'q?" degan savolni qoldirardi va odam uni
          bizdan emas, taxmindan javob olardi. */}
      {!tahrir && (
        <p className="mt-2 text-body text-muted-foreground">
          Hujjat biriktirish uchun ruxsatingiz yo'q.
        </p>
      )}
      {tahrir && !yopiq && (
        <p className="mt-2 text-body text-muted-foreground">
          Sabab hujjati faqat yakunlanmagan kartaga biriktiriladi
          (yutqazildi, rad etildi, ulgurmadik).
        </p>
      )}
      {tahrir && yopiq && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Input
            type="text" value={izoh} placeholder="Izoh (ixtiyoriy)"
            className="w-56" disabled={busy}
            onChange={(e) => setIzoh(e.target.value)} />
          <input
            ref={inputRef} type="file" disabled={busy}
            accept={turlar.join(',')}
            aria-label="Sabab hujjatini tanlash"
            className={cn('text-body file:mr-2 file:rounded-md file:border',
              'file:bg-secondary file:px-2 file:py-1 file:text-body')}
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void yukla(f)
            }} />
          {maxHajm > 0 && (
            <span className="text-caption text-muted-foreground">
              {turlar.join(' ')} · {hajm(maxHajm)} gacha
            </span>
          )}
        </div>
      )}
    </section>
  )
}
