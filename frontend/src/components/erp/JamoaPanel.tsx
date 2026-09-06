import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import Icon from '../Icon'
import type { ErpBroker, Jamoa, JamoaAzo } from '@/types'
import { ErpError, can } from './erpShared'

// KARTA JAMOASI — bitta tenderda bir nechta hodim (28-patch).
//
// NEGA KERAK: kartada yakka mas'ul bor edi, amalda esa uch odam
// ishlaydi — narxni biri hisoblaydi, hujjatni ikkinchisi yig'adi,
// texnik qismni uchinchisi yozadi. Ular kartani ko'ra olmasdi ham,
// ya'ni ishlash uchun mas'ulning hisobidan kirish kerak bo'lardi.
//
// ASOSIY MAS'UL ALOHIDA KO'RSATILADI va u ro'yxatning boshida
// turadi: "kim javobgar" degan savol jamoa ro'yxatida yo'qolib
// ketmasligi kerak. Serverda ham u boshqa joyda saqlanadi
// (`opportunity.broker_id`), shuning uchun `asosiy` bayrog'i
// interfeys bezagi emas — u ma'lumotning o'zi.
//
// QIDIRUVLI TANLASH (§28): oddiy `<select>` o'nlab hodimda
// foydasiz bo'lardi. Ro'yxat yozilgan matn bo'yicha filtrlanadi va
// ALLAQACHON jamoada bo'lganlar ko'rsatilmaydi — bosib bo'lmaydigan
// qatorni ko'rsatish odamni chalg'itardi.

interface Props {
  oppId: number
  brokers: ErpBroker[]
  /** Jamoa o'zgardi — karta ekrani mas'ulni yangilasin. */
  onChanged?: () => void
}

/** Rol nishonlari. Serverdagi ro'yxat bilan mos: yangi rol
 *  qo'shilsa nishonsiz qoladi (`user`), lekin YO'QOLMAYDI. */
const ROL_ICON: Record<string, string> = {
  masul: 'check', narx: 'stats', hujjat: 'clip',
  texnik: 'box', yuridik: 'lock', kuzatuvchi: 'user',
}

export default function JamoaPanel({ oppId, brokers, onChanged }: Props) {
  const [jamoa, setJamoa] = useState<Jamoa | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [ochiq, setOchiq] = useState(false)
  const [q, setQ] = useState('')
  const [rol, setRol] = useState('kuzatuvchi')
  const [tarix, setTarix] = useState(false)

  const qosha = can('karta.jamoa_qosh')
  const chiqara = can('karta.jamoa_chiqar')
  const asosiyQila = can('karta.biriktirish')

  const yukla = useCallback(async (bilanTarix = false) => {
    try {
      setJamoa(await api.jamoa(oppId, bilanTarix))
      setErr('')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setJamoa(null)
    }
  }, [oppId])

  useEffect(() => { void yukla(tarix) }, [yukla, tarix])

  async function amal(fn: () => Promise<Jamoa>) {
    setBusy(true)
    try {
      setJamoa(await fn())
      setErr('')
      onChanged?.()
    } catch (e) {
      // XATO KO'RSATILADI, ichki tafsilotsiz (§29): server matni
      // allaqachon odam tilida ("Faolsizlantirilgan hodim...").
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const faol = useMemo(
    () => (jamoa?.azolar || []).filter((a) => !a.removed_at), [jamoa])
  const chiqarilgan = useMemo(
    () => (jamoa?.azolar || []).filter((a) => a.removed_at), [jamoa])

  /** Qo'shish uchun mumkin bo'lganlar: faol, hali jamoada emas. */
  const tanlanadi = useMemo(() => {
    const bor = new Set(faol.map((a) => a.broker_id))
    const s = q.trim().toLowerCase()
    return brokers
      .filter((b) => b.active !== false && !bor.has(b.id))
      .filter((b) => !s || b.full_name.toLowerCase().includes(s))
      .slice(0, 8)
  }, [brokers, faol, q])

  if (!jamoa && !err) {
    return <p className="text-body text-muted-foreground">Yuklanmoqda…</p>
  }

  return (
    <div data-testid="jamoa-panel" className="space-y-2">
      {err && <ErpError msg={err} />}

      {/* --- A'ZOLAR --- */}
      <div className="flex flex-wrap items-center gap-1.5">
        {faol.length === 0 && (
          <span className="text-body text-muted-foreground">
            Jamoa yo'q — mas'ul biriktirilmagan.
          </span>
        )}
        {faol.map((a) => (
          <Azo key={a.broker_id} a={a} busy={busy}
            chiqara={!!chiqara && !a.asosiy}
            asosiyQila={!!asosiyQila && !a.asosiy}
            rollar={jamoa?.rollar || []}
            onRol={(r) => void amal(() => api.jamoaRole(oppId, a.broker_id, r))}
            onAsosiy={() => void amal(() => api.jamoaPrimary(oppId, a.broker_id))}
            onChiqar={() => void amal(() => api.jamoaRemove(oppId, a.broker_id))} />
        ))}
        {qosha && (
          <Button variant="outline" size="sm" data-testid="jamoa-och"
            onClick={() => setOchiq((v) => !v)}>
            <Icon name="plus" size={13} /> Jamoani boshqarish
          </Button>
        )}
      </div>

      {/* --- QO'SHISH --- */}
      {ochiq && qosha && (
        <div className="rounded-lg border bg-surface-2 p-2">
          <div className="flex flex-wrap items-center gap-2">
            <Input value={q} data-testid="jamoa-qidiruv"
              onChange={(e) => setQ(e.target.value)}
              placeholder="Hodimni qidiring…" className="h-8 w-52" />
            <Select value={rol} onValueChange={setRol}>
              <SelectTrigger className="h-8 w-44" aria-label="Mas'uliyat">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(jamoa?.rollar || []).map((r) => (
                  <SelectItem key={r.kod} value={r.kod}>{r.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <ul className="mt-2 divide-y">
            {tanlanadi.length === 0 && (
              <li className="py-1.5 text-caption text-muted-foreground">
                {q ? 'Hodim topilmadi.' : 'Qo‘shiladigan hodim qolmadi.'}
              </li>
            )}
            {tanlanadi.map((b) => (
              <li key={b.id} className="flex items-center gap-2 py-1">
                <span className="min-w-0 flex-1 truncate text-body">
                  {b.full_name}
                </span>
                <Button size="sm" variant="ghost" disabled={busy}
                  data-testid={`jamoa-qosh-${b.id}`}
                  onClick={() => void amal(async () => {
                    const r = await api.jamoaAdd(oppId, b.id, rol)
                    setQ('')
                    return r
                  })}>
                  Qo‘shish
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* --- TARIX --- */}
      {/* "Kim qachon jamoada edi" — chiqarilgan a'zolar YO'QOLMAYDI
          (serverda `removed_at`, qator o'chirilmaydi). */}
      <button type="button" data-testid="jamoa-tarix"
        className="text-micro text-muted-foreground hover:underline"
        onClick={() => setTarix((v) => !v)}>
        {tarix ? 'Tarixni yashirish' : 'Chiqarilganlar'}
        {tarix && chiqarilgan.length > 0 && ` (${chiqarilgan.length})`}
      </button>
      {tarix && (
        <ul className="space-y-0.5">
          {chiqarilgan.length === 0 && (
            <li className="text-micro text-muted-foreground">
              Hech kim chiqarilmagan.
            </li>
          )}
          {chiqarilgan.map((a) => (
            <li key={`${a.broker_id}-${a.removed_at}`}
              className="text-micro text-muted-foreground">
              {a.full_name} — {a.rol_label} · chiqarildi
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Azo({ a, busy, chiqara, asosiyQila, rollar, onRol, onAsosiy, onChiqar }: {
  a: JamoaAzo
  busy: boolean
  chiqara: boolean
  asosiyQila: boolean
  rollar: { kod: string; label: string }[]
  onRol: (rol: string) => void
  onAsosiy: () => void
  onChiqar: () => void
}) {
  const [menu, setMenu] = useState(false)
  return (
    <span data-testid={`jamoa-azo-${a.broker_id}`}
      className={cn('relative flex items-center gap-1 rounded-md px-2 py-0.5 text-caption',
        a.asosiy ? 'bg-secondary font-semibold text-primary' : 'bg-surface-2')}>
      <Icon name={ROL_ICON[a.rol] || 'user'} size={12}
        className={a.asosiy ? '' : 'text-muted-foreground'} />
      {a.full_name}
      <span className="text-micro text-muted-foreground">{a.rol_label}</span>
      {/* ASOSIY AMALLAR + QOLGANLARI MENYUDA (§9): har amal uchun
          tugma qo'yilsa, a'zolar qatori tugmalar devoriga aylanardi. */}
      {(chiqara || asosiyQila) && (
        <button type="button" disabled={busy} aria-label={`${a.full_name} — amallar`}
          data-testid={`jamoa-menu-${a.broker_id}`}
          className="text-muted-foreground hover:text-foreground"
          onClick={() => setMenu((v) => !v)}>
          ⋯
        </button>
      )}
      {menu && (
        <div className="absolute left-0 top-full z-20 mt-1 w-52 rounded-md border bg-popover p-1 shadow-lg">
          {asosiyQila && (
            <button type="button" data-testid={`jamoa-asosiy-${a.broker_id}`}
              className="w-full rounded px-2 py-1 text-left text-caption hover:bg-accent"
              onClick={() => { setMenu(false); onAsosiy() }}>
              Asosiy mas'ul qilish
            </button>
          )}
          {chiqara && rollar.map((r) => (
            <button key={r.kod} type="button"
              className={cn('w-full rounded px-2 py-1 text-left text-caption hover:bg-accent',
                r.kod === a.rol && 'font-semibold text-primary')}
              onClick={() => { setMenu(false); onRol(r.kod) }}>
              {r.label}
            </button>
          ))}
          {chiqara && (
            <button type="button" data-testid={`jamoa-chiqar-${a.broker_id}`}
              className="w-full rounded px-2 py-1 text-left text-caption text-urgent-strong hover:bg-accent"
              onClick={() => { setMenu(false); onChiqar() }}>
              Jamoadan chiqarish
            </button>
          )}
        </div>
      )}
    </span>
  )
}
