import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import Icon from '../Icon'
import type { AuthUser, LoginAttempt, Setting, StaffRow, TopshiriqHolat } from '@/types'
import { ErpError } from './erpShared'

// HODIMLAR — faqat administrator uchun.
//
// NEGA BITTA EKRAN. Bu yerda ikki tushuncha uchrashadi:
//   HODIM (`erp.broker`) — kartaga mas'ul, vazifa bajaruvchisi, tarixdagi
//     ism. Tizimga KIRMASLIGI ham mumkin.
//   HISOB (`erp.app_user`) — login, parol, rol.
// Ularni alohida ro'yxatda ko'rsatsak, "Karimovga hisob ochilganmi?" degan
// savolga javob ikki ro'yxatni solishtirib topilardi. Shuning uchun har
// bir hodim qatorida uning hisobi ham ko'rinadi.
//
// Hodimga bog'lanmagan hisoblar (masalan `admin`) pastda alohida: ular
// hech qaysi qatorga tushmaydi va ko'zdan yo'qolmasligi kerak.

// ROLLAR SERVERDAN keladi (`GET /erp/auth/roles`). Ro'yxatni bu yerda
// takrorlash uchinchi nusxa bo'lardi (baza CHECK, `api/auth.py` ROLES va
// shu fayl) — rol qo'shilganda ekranda jimgina eskisi qolardi.
//
// Zaxira ro'yxat FAQAT so'rov yiqilganda ishlaydi: usiz rol yorlig'i
// o'rnida kod ko'rinardi ("menejer" emas, `menejer`).
const ROLE_FALLBACK: Array<{ code: string; label: string }> = [
  { code: 'admin', label: 'Administrator' },
  { code: 'rahbar', label: 'Rahbar' },
  { code: 'menejer', label: 'Menejer' },
  { code: 'broker', label: 'Broker' },
]

type Draft = {
  full_name: string
  email: string
  phone: string
  active: boolean
}

type AccDraft = {
  username: string
  password: string
  role: string
}

export default function StaffPage() {
  const f = useFormat()
  const [rows, setRows] = useState<StaffRow[] | null>(null)
  const [unlinked, setUnlinked] = useState<AuthUser[]>([])
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Ochiq tahrir formalari: bir vaqtda bittadan.
  const [editId, setEditId] = useState<number | null>(null)
  const [draft, setDraft] = useState<Draft>({ full_name: '', email: '', phone: '', active: true })
  const [accFor, setAccFor] = useState<number | null>(null)
  const [acc, setAcc] = useState<AccDraft>({ username: '', password: '', role: 'broker' })
  const [roles, setRoles] = useState(ROLE_FALLBACK)
  const [pwdFor, setPwdFor] = useState<number | null>(null)
  const [pwd, setPwd] = useState('')
  const [newName, setNewName] = useState('')

  function load() {
    api.staff()
      .then((r) => { setRows(r.staff); setUnlinked(r.unlinked_users) })
      .catch((e: Error) => { setError(e.message); setRows([]) })
  }

  useEffect(load, [])

  // Rol lug'ati bir marta: u ish davomida o'zgarmaydi.
  useEffect(() => {
    api.roles().then((r) => { if (r.roles?.length) setRoles(r.roles) })
      .catch(() => { /* zaxira ro'yxat qoladi */ })
  }, [])

  const roleLabel = (code: string) =>
    roles.find((r) => r.code === code)?.label || code

  /** Har amaldan keyin ro'yxat QAYTA o'qiladi: hisob ochilganda hodim
   *  qatori ham, "bog'lanmagan hisoblar" ro'yxati ham o'zgaradi. */
  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true); setError(null); setNote(null)
    try {
      await fn()
      setNote(ok)
      load()
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  function startEdit(s: StaffRow) {
    setAccFor(null); setPwdFor(null)
    setEditId(s.id)
    setDraft({
      full_name: s.full_name, email: s.email || '', phone: s.phone || '',
      active: s.active,
    })
  }

  function startAccount(s: StaffRow) {
    setEditId(null); setPwdFor(null)
    setAccFor(s.id)
    // Login taklifi: ismning oxirgi so'zi (odatda familiya), lotin harflari.
    const guess = s.full_name.trim().split(/\s+/).pop() || ''
    setAcc({ username: guess.toLowerCase().replace(/[^a-z0-9_.]/g, ''), password: '', role: 'broker' })
  }

  if (!rows && !error) return <Skeleton className="h-64 w-full rounded-lg" />

  return (
    <div className="space-y-4">
      {error && <ErpError msg={error} />}
      {note && (
        <div className="rounded-lg border border-ok/40 bg-ok-soft px-3 py-2 text-body text-ok-strong">
          {note}
        </div>
      )}

      <section className="rounded-lg border bg-card p-4">
        <h2 className="mb-1 text-body font-semibold">
          Hodimlar {rows ? `(${rows.length})` : ''}
        </h2>
        <p className="mb-3 text-caption text-muted-foreground">
          Hodim — kartaga mas'ul va tarixdagi ism. Hisob — tizimga kirish.
          Hodim hisobsiz ham bo'lishi mumkin (masalan omborchi).
        </p>

        {rows && rows.length === 0 && (
          <div className="text-body text-muted-foreground">
            Hodim yo'q. Pastdagi maydondan qo'shing.
          </div>
        )}

        <ul className="divide-y">
          {rows?.map((s) => (
            <li key={s.id} className="py-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className={s.active ? 'text-body font-medium' : 'text-body font-medium text-muted-foreground line-through'}>
                  {s.full_name}
                </span>

                {s.user ? (
                  <>
                    <span className="rounded bg-secondary px-1.5 py-px text-micro font-semibold text-primary">
                      {roleLabel(s.user.role)}
                    </span>
                    <span className="text-caption text-muted-foreground">
                      {s.user.username}
                      {!s.user.active && ' — hisob faol emas'}
                    </span>
                  </>
                ) : (
                  <span className="text-caption text-muted-foreground">hisobsiz</span>
                )}

                <span className="ml-auto text-caption text-muted-foreground tabular">
                  {s.opp_count} karta · {s.open_tasks} ochiq vazifa
                  {s.user?.last_login_at && ` · kirgan: ${f.dateFmt(s.user.last_login_at)}`}
                </span>
              </div>

              <div className="mt-1.5 flex flex-wrap gap-1.5">
                <Button size="sm" variant="outline" onClick={() => startEdit(s)}>
                  Tahrirlash
                </Button>
                {!s.user ? (
                  <Button size="sm" variant="outline" onClick={() => startAccount(s)}>
                    Hisob ochish
                  </Button>
                ) : (<>
                  <Button size="sm" variant="outline"
                    onClick={() => { setEditId(null); setAccFor(null); setPwdFor(s.user!.id); setPwd('') }}>
                    Parolni almashtirish
                  </Button>
                  <Select value={s.user.role} disabled={busy}
                    onValueChange={(v) => run(
                      () => api.updateUser(s.user!.id, {
                        full_name: s.full_name, role: v,
                        broker_id: s.id, active: s.user!.active,
                      }),
                      `${s.full_name}: rol o'zgartirildi`)}>
                    <SelectTrigger className="h-8 w-auto min-w-32 bg-card text-caption">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {roles.map((r) => (
                        <SelectItem key={r.code} value={r.code}>{r.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button size="sm" variant="outline" disabled={busy}
                    onClick={() => run(
                      () => api.updateUser(s.user!.id, {
                        full_name: s.full_name, role: s.user!.role,
                        // Hisob faolsizlantirilsa HODIM bog'lanishi
                        // saqlanadi: qaytadan yoqilganda yana o'sha odam.
                        broker_id: s.id, active: !s.user!.active,
                      }),
                      s.user!.active ? 'Hisob faolsizlantirildi' : 'Hisob yoqildi')}>
                    {s.user.active ? 'Hisobni yopish' : 'Hisobni yoqish'}
                  </Button>
                </>)}
              </div>

              {/* --- hodimni tahrirlash --- */}
              {editId === s.id && (
                <div className="mt-2 rounded-md border bg-background p-3">
                  <div className="grid gap-2 sm:grid-cols-3">
                    <Field label="To'liq ism" value={draft.full_name}
                      onChange={(v) => setDraft({ ...draft, full_name: v })} />
                    <Field label="Email" value={draft.email}
                      onChange={(v) => setDraft({ ...draft, email: v })} />
                    <Field label="Telefon" value={draft.phone}
                      onChange={(v) => setDraft({ ...draft, phone: v })} />
                  </div>
                  <label className="mt-2 flex items-center gap-2 text-caption">
                    <input type="checkbox" checked={draft.active}
                      onChange={(e) => setDraft({ ...draft, active: e.target.checked })} />
                    Faol hodim
                  </label>
                  {/* Ochiq ishi borni faolsizlantirib bo'lmaydi — server
                      409 qaytaradi va sabab ko'rsatiladi. */}
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" disabled={busy || !draft.full_name.trim()}
                      onClick={() => run(
                        () => api.updateBroker(s.id, {
                          full_name: draft.full_name.trim(),
                          email: draft.email.trim() || null,
                          phone: draft.phone.trim() || null,
                          active: draft.active,
                        }).then(() => setEditId(null)),
                        'Hodim saqlandi')}>
                      Saqlash
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>
                      Bekor qilish
                    </Button>
                  </div>
                </div>
              )}

              {/* --- hisob ochish --- */}
              {accFor === s.id && (
                <div className="mt-2 rounded-md border bg-background p-3">
                  <div className="grid gap-2 sm:grid-cols-3">
                    <Field label="Login" value={acc.username}
                      onChange={(v) => setAcc({ ...acc, username: v })} />
                    <div>
                      <div className="mb-1 text-caption font-semibold text-muted-foreground">
                        Parol (kamida 6 belgi)
                      </div>
                      <Input type="password" autoComplete="new-password"
                        value={acc.password}
                        onChange={(e) => setAcc({ ...acc, password: e.target.value })} />
                    </div>
                    <div>
                      <div className="mb-1 text-caption font-semibold text-muted-foreground">
                        Rol
                      </div>
                      <Select value={acc.role}
                        onValueChange={(v) => setAcc({ ...acc, role: v })}>
                        <SelectTrigger className="bg-card text-body">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {roles.map((r) => (
                            <SelectItem key={r.code} value={r.code}>{r.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <p className="mt-2 text-micro text-muted-foreground">
                    Parol shu yerda BIR MARTA ko'rsatiladi — uni hodimga
                    o'zingiz yetkazasiz. Bazada faqat xeshi saqlanadi.
                  </p>
                  <div className="mt-2 flex gap-2">
                    <Button size="sm"
                      disabled={busy || !acc.username.trim() || acc.password.length < 6}
                      onClick={() => run(
                        () => api.createUser({
                          username: acc.username.trim(), full_name: s.full_name,
                          password: acc.password, role: acc.role, broker_id: s.id,
                          email: s.email,
                        }).then(() => setAccFor(null)),
                        `${s.full_name} uchun hisob ochildi`)}>
                      Hisob ochish
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setAccFor(null)}>
                      Bekor qilish
                    </Button>
                  </div>
                </div>
              )}

              {/* --- parolni TIKLASH (admin) ---
                  Bu O'ZINIKINI almashtirish EMAS: admin boshqaning
                  parolini tiklaydi, ya'ni joriy parol so'ralmaydi (bu
                  odatda "unutdim" holati). Evaziga o'sha hisobning
                  HAMMA sessiyasi yopiladi — admin parolni tiklayotgan
                  bo'lsa, hisobga ishonch yo'q. Buni yashirmasdan
                  aytamiz (auth-6).

                  Parol uzunligi sharti BU YERDA takrorlanmaydi: u
                  serverda va uning xato matni nima qilish kerakligini
                  aytadi. Ikki joyda ikki xil raqam qolib ketmasin. */}
              {s.user && pwdFor === s.user.id && (
                <div className="mt-2 rounded-md border bg-background p-3">
                  <div className="mb-1 text-caption font-semibold text-muted-foreground">
                    {s.user.username} uchun yangi parol
                  </div>
                  <p className="mb-2 text-micro text-muted-foreground">
                    Joriy parol so'ralmaydi, lekin bu hisobning
                    <b> hamma sessiyasi yopiladi</b> — u qaytadan kirishi
                    kerak bo'ladi.
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <Input type="password" autoComplete="new-password"
                      className="max-w-64" value={pwd}
                      onChange={(e) => setPwd(e.target.value)} />
                    <Button size="sm" disabled={busy || !pwd}
                      onClick={() => run(
                        () => api.setUserPassword(s.user!.id, pwd)
                          .then((r) => {
                            setPwdFor(null); setPwd('')
                            return r
                          }),
                        'Parol tiklandi — hisobning sessiyalari yopildi')}>
                      Tiklash
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setPwdFor(null)}>
                      Bekor qilish
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>

        {/* --- yangi hodim --- */}
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
          <Input className="max-w-72" placeholder="Yangi hodimning to'liq ismi"
            value={newName} onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newName.trim()) {
                e.preventDefault()
                run(() => api.addBroker({ full_name: newName.trim() })
                  .then(() => setNewName('')), 'Hodim qo\'shildi')
              }
            }} />
          <Button size="sm" disabled={busy || !newName.trim()}
            onClick={() => run(
              () => api.addBroker({ full_name: newName.trim() })
                .then(() => setNewName('')),
              'Hodim qo\'shildi')}>
            <Icon name="plus" size={14} /> Qo'shish
          </Button>
          <span className="text-caption text-muted-foreground">
            Hisob keyin, alohida ochiladi.
          </span>
        </div>
      </section>

      {/* --- hodimga bog'lanmagan hisoblar --- */}
      {unlinked.length > 0 && (
        <section className="rounded-lg border bg-card p-4">
          <h2 className="mb-1 text-body font-semibold">
            Hodimga bog'lanmagan hisoblar ({unlinked.length})
          </h2>
          <p className="mb-3 text-caption text-muted-foreground">
            Odatda bu tizim administratori — u tenderlar bilan ishlamaydi.
            Bunday hisob kartaga mas'ul bo'lolmaydi va "mening ishlarim"
            filtriga tushmaydi.
          </p>
          <ul className="divide-y">
            {unlinked.map((u) => (
              <li key={u.id} className="flex flex-wrap items-baseline gap-2 py-2 text-body">
                <span className="font-medium">{u.username}</span>
                <span className="rounded bg-secondary px-1.5 py-px text-micro font-semibold text-primary">
                  {u.role_label || u.role}
                </span>
                <span className="text-caption text-muted-foreground">{u.full_name}</span>
                {!u.active && (
                  <span className="text-caption text-muted-foreground">faol emas</span>
                )}
                <span className="ml-auto text-caption text-muted-foreground tabular">
                  {u.last_login_at ? `kirgan: ${f.dateFmt(u.last_login_at)}` : 'hech qachon kirmagan'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {/* --- Tender-AI ulanishi --- */}
      <TaiUlanish />
      {/* --- tizim sozlamalari --- */}
      <SettingsPanel />
      {/* --- kirish urinishlari --- */}
      <LoginAttempts />
    </div>
  )
}

// TENDER-AI ULANISHI — yo'naltirish oqimi ishlaydimi.
//
// NEGA SHU EKRANDA: xarita ("biz qaysi ijarachimiz") — hodimlar
// bilan bitta savolning davomi: Tender-AI dagi aktor ERP hodimiga
// bog'lanadi. Va ikkalasi ham administrator ishi.
//
// SOZLANMAGAN HOLAT KO'RINIB TURADI. Ilgari buni faqat `curl` yoki
// `check_setup.py` bilan bilish mumkin edi; endi "nega hech narsa
// kelmayapti" degan savol shu paneldan javob oladi.
function TaiUlanish() {
  const [h, setH] = useState<TopshiriqHolat | null>(null)
  const [qiymat, setQiymat] = useState('')
  const [busy, setBusy] = useState(false)
  const [xabar, setXabar] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    api.topshiriqHolat()
      .then((r) => { setH(r); setQiymat(r.tai_company_id ? String(r.tai_company_id) : '') })
      .catch((e: Error) => setError(e.message))
  }

  useEffect(load, [])

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true); setError(null); setXabar(null)
    try {
      await fn()
      setXabar(ok)
      load()
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(false) }
  }

  if (!h) return null

  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-1 text-body font-semibold">Tender-AI ulanishi</h2>
      <p className="mb-3 text-caption text-muted-foreground">
        Tender-AI da "Olindi" deyilgan tender shu yerda ish kartasiga
        aylanadi. Buning uchun qaysi ijarachi ekanimiz ko'rsatilishi
        kerak — bu taxmin qilinmaydi.
      </p>
      {error && <ErpError msg={error} />}
      {xabar && (
        <div className="mb-2 rounded-md border border-ok/40 bg-ok-soft px-3 py-2 text-caption text-ok-strong">
          {xabar}
        </div>
      )}

      {/* Sozlanmagan yoki buzuq holat — OCHIQ aytiladi */}
      {h.sabab && (
        <div className="mb-2 rounded-md border border-soon/40 bg-soon-soft px-3 py-2 text-caption text-soon-strong">
          {h.sabab}
        </div>
      )}
      {h.oxirgi_xato && (
        <div className="mb-2 text-caption text-destructive">
          Oxirgi xato: {h.oxirgi_xato}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div>
          <div className="mb-1 text-caption font-semibold text-muted-foreground">
            Tender-AI ijarachisi (company_account.id)
          </div>
          <Input className="max-w-40" inputMode="numeric" value={qiymat}
            onChange={(e) => setQiymat(e.target.value)} />
        </div>
        <Button size="sm" disabled={busy}
          onClick={() => run(
            () => api.setTaiXarita(qiymat.trim() ? Number(qiymat) : null),
            qiymat.trim() ? 'Xarita saqlandi' : 'Xarita olib tashlandi')}>
          Saqlash
        </Button>
        <Button size="sm" variant="outline" disabled={busy || !h.tai_company_id}
          onClick={() => run(api.topshiriqSync, 'Sinxronlandi')}>
          Hozir sinxronlash
        </Button>
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-caption text-muted-foreground">
        <li>Tinglovchi: {h.tinglovchi ? 'ishlayapti' : 'ishlamayapti'}</li>
        <li>Zaxira so'rov: {h.oraliq} soniyada</li>
        {h.kutayotgan !== undefined && <li>Kutmoqda: {h.kutayotgan}</li>}
        {h.kartalar !== undefined && <li>Yo'naltirilgan kartalar: {h.kartalar}</li>}
      </ul>
    </section>
  )
}

// TIZIM SOZLAMALARI — huquqning kompaniyaga bog'liq qismi.
//
// NEGA SHU EKRANDA: sozlamalar HUQUQNI o'zgartiradi ("broker kartani
// o'zi yakunlaydimi"), ya'ni ular hodimlar va rollar bilan bitta
// savolning ikki tomoni. Alohida "Sozlamalar" bo'limi ochish esa
// bitta sahifalik ro'yxat uchun ortiqcha bo'lardi.
//
// Ro'yxat, standart qiymatlar va IZOHLAR serverdan keladi
// (`api/erp/sozlama.py`): ekran ikkinchi nusxa tutmaydi.
function SettingsPanel() {
  const f = useFormat()
  const [rows, setRows] = useState<Setting[] | null>(null)
  const [ready, setReady] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    api.settings()
      .then((r) => { setRows(r.settings); setReady(r.ready) })
      .catch((e: Error) => { setError(e.message); setRows([]) })
  }

  useEffect(load, [])

  async function toggle(x: Setting) {
    setBusy(x.key); setError(null)
    try {
      await api.setSetting(x.key, !x.value)
      load()
    } catch (e) {
      setError((e as Error).message.replace(/^\d+:\s*/, ''))
    } finally { setBusy(null) }
  }

  if (!rows) return null

  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-1 text-body font-semibold">Tizim sozlamalari</h2>
      <p className="mb-3 text-caption text-muted-foreground">
        Bular HUQUQNI o'zgartiradi va darhol kuchga kiradi. Kim
        o'zgartirgani yozib boriladi.
      </p>
      {error && <ErpError msg={error} />}
      {!ready && (
        <div className="text-body text-muted-foreground">
          schema_patch_erp_18.sql qo'llanmagan — sozlamalar standart
          qiymatda ishlayapti.
        </div>
      )}
      <ul className="divide-y">
        {rows.map((x) => (
          <li key={x.key} className="py-3">
            <div className="flex flex-wrap items-baseline gap-2">
              <label className="flex cursor-pointer items-center gap-2 text-body font-medium">
                <input type="checkbox" checked={x.value} disabled={!!busy}
                  onChange={() => toggle(x)} />
                {x.label}
              </label>
              {!x.changed && (
                <span className="rounded bg-secondary px-1.5 py-px text-micro
                                 font-semibold text-muted-foreground">
                  standart
                </span>
              )}
              {x.changed && x.updated_by && (
                <span className="ml-auto text-caption text-muted-foreground">
                  {x.updated_by}
                  {x.updated_at ? ` · ${f.dateFmt(x.updated_at)}` : ''}
                </span>
              )}
            </div>
            <p className="mt-1 text-caption text-muted-foreground">{x.help}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

// KIRISH URINISHLARI — "kim, qayerdan va qachon urindi".
//
// Ro'yxat bloklash bilan BIR MANBADAN o'qiydi: cheklov ham shu jurnaldan
// hisoblanadi. Ya'ni admin ekranda ko'rgan narsa — himoyaning haqiqiy
// holati, alohida hisoblagichning aks-sadosi emas.
//
// Diqqat qaratiladigan narsa — MAVJUD BO'LMAGAN login bilan urinish:
// hodim o'z loginini adashtirmaydi, lug'at bo'yicha urinayotgan dastur esa
// aynan shunday iz qoldiradi.
function LoginAttempts() {
  const f = useFormat()
  const [rows, setRows] = useState<LoginAttempt[] | null>(null)

  useEffect(() => {
    // Patch qo'llanmagan bo'lsa (503) blok jim yashiriladi.
    api.loginAttempts({ hours: 72, limit: 100 })
      .then(setRows).catch(() => setRows(null))
  }, [])

  if (!rows || !rows.length) return null
  const unknown = rows.filter((r) => !r.known_user).length

  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-1 text-body font-semibold">
        Muvaffaqiyatsiz kirish urinishlari ({rows.length})
      </h2>
      <p className="mb-3 text-caption text-muted-foreground">
        Oxirgi 3 kun. Bitta login va manzil uchun ketma-ket bir necha xatodan
        keyin kirish vaqtincha to'xtatiladi — hisobning o'zi bloklanmaydi.
        {unknown > 0 && (
          <>
            {' '}
            <span className="font-medium text-urgent-strong">
              {unknown} tasi mavjud bo'lmagan login bilan
            </span>
            {' '}— bu odatda parol tanlashga urinish izi.
          </>
        )}
      </p>
      <ul className="divide-y">
        {rows.map((r) => (
          <li key={r.id}
            className="flex flex-wrap items-baseline gap-2 py-1.5 text-body">
            <span className="font-medium">{r.username}</span>
            {!r.known_user && (
              <span className="rounded bg-secondary px-1.5 py-px text-micro
                               font-semibold text-urgent-strong">
                bunday login yo'q
              </span>
            )}
            <span className="tabular text-caption text-muted-foreground">
              {r.ip || 'manzil ko\u2019rsatilmagan'}
            </span>
            <span className="ml-auto tabular text-caption text-muted-foreground">
              {f.dateTimeFmt(r.created_at)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Field({ label, value, onChange }: {
  label: string; value: string; onChange: (v: string) => void
}) {
  return (
    <div>
      <div className="mb-1 text-caption font-semibold text-muted-foreground">
        {label}
      </div>
      <Input value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}
