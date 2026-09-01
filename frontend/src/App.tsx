import { useEffect, useState } from 'react'
import { api, getToken, setUnauthorizedHandler } from '@/api'
import Icon from './components/Icon'
import Dashboard from './components/erp/Dashboard'
import OpportunitiesPage from './components/erp/OpportunitiesPage'
import ClientsPage from './components/erp/ClientsPage'
import MyTasksPage from './components/erp/MyTasksPage'
import OwnCompanyPage from './components/erp/OwnCompanyPage'
import StaffPage from './components/erp/StaffPage'
import StockPage from './components/erp/StockPage'
import InvoicePage from './components/erp/InvoicePage'
import LoginPage from './components/erp/LoginPage'
import MyPasswordPanel from './components/erp/MyPasswordPanel'
import TakeTenderDialog from './components/erp/TakeTenderDialog'
import { ErpError, SchemaMissing, can, permLevel, roleAtLeast, setPerms } from './components/erp/erpShared'
import NotificationBell from './components/erp/NotificationBell'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useTheme } from '@/theme'
import type { Theme } from '@/theme'
import type { AuthUser, ErpBroker, ErpHealth } from '@/types'

// TENDER-AI ERP — alohida ilova.
//
// TENDER-AI BILAN BOG'LANISH — ikki chuqur havola (deep link):
//   /?take=<tender_id>  — tender panelidagi "ERP da ishga olish" tugmasi;
//                         ochilishi bilan "Ishga olish" formasi chiqadi.
//   /?opp=<opp_id>      — "ERP kartasi" havolasi; o'sha karta ochiladi.
// Teskari yo'nalish — kartadagi "Tender panelini ochish": tender-ai ning
// o'z manzili (`/erp/meta` -> tender_web), yangi oynada.
//
// Router kutubxonasi YO'Q: uch bo'lim va ikki parametr uchun `useState`
// yetarli (tender-ai dagi bilan bir xil qaror).

type View = 'dashboard' | 'opportunities' | 'mytasks' | 'clients' | 'company'
  | 'stock' | 'invoices' | 'staff'

// MENYU GURUHLARGA BO'LINGAN. Yetti bandli tekis ro'yxatda ko'z har
// safar boshidan qidiradi; uch guruhda esa "pul bilan ishlayapman"
// degan fikr menyuning yarmini darhol chiqarib tashlaydi.
//
// Guruh nomlari ISH bo'yicha, modul bo'yicha emas: "Kundalik ish",
// "Pul va hujjatlar", "Sozlash".
interface NavItem {
  key: View
  icon: string
  label: string
  /** Sarlavha ostidagi bir qatorli izoh — ekran nima uchunligini aytadi */
  hint: string
}

const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Kundalik ish',
    items: [
      { key: 'dashboard', icon: 'stats', label: 'Boshqaruv paneli',
        hint: 'Bugungi holat: vazifalar, muddatlar, natija' },
      // Kunni shu ekrandan boshlanadi: bugun nima qilish kerak
      { key: 'mytasks', icon: 'check', label: 'Mening ishlarim',
        hint: 'Menga biriktirilgan vazifalar' },
      { key: 'opportunities', icon: 'briefcase', label: 'Ishdagi tenderlar',
        hint: 'Kartalar, bosqichlar va tahlil' },
      { key: 'clients', icon: 'user', label: 'Mijoz korxonalar',
        hint: 'Passport, rekvizitlar, hujjatlar' },
    ],
  },
  {
    title: 'Pul va hujjatlar',
    items: [
      // Hisob-fakturalar va to'lovlar (5B-2)
      { key: 'invoices', icon: 'clip', label: 'Hisob-fakturalar',
        hint: "Faktura, to'lov, dalolatnoma" },
      // Ombor: qoldiqning egasi ERP (5B-1)
      { key: 'stock', icon: 'box', label: 'Ombor',
        hint: 'Qoldiq, harakatlar, rezerv' },
      // Bizning rekvizitlar + shartnomalar (5A-1)
      { key: 'company', icon: 'briefcase', label: 'Kompaniya va shartnomalar',
        hint: 'Bizning rekvizitlar, QQS, shartnomalar' },
    ],
  },
  {
    title: 'Sozlash',
    items: [
      // Hodimlar va ularning hisoblari — faqat administrator ko'radi
      { key: 'staff', icon: 'user', label: 'Hodimlar',
        hint: 'Hisoblar, rollar, kirish urinishlari' },
    ],
  },
]

const NAV: NavItem[] = NAV_GROUPS.flatMap((g) => g.items)

/** Ismning bosh harflari — avatar o'rniga. Rasm yuklash ERP uchun
 *  ortiqcha; ikki harf odamni ro'yxatda ajratish uchun yetarli. */
function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '').join('') || '?'
}

/** MAVZU ALMASHTIRGICH — uchta holat, ikkita emas.
 *  "Tizim" alohida qiymat: kompyuter kechqurun qorong'iga o'tsa, ERP
 *  ham o'tishi kerak (`theme.ts`). */
function ThemeSwitch({ theme, onChange }: {
  theme: Theme
  onChange: (t: Theme) => void
}) {
  const opts: { key: Theme; icon: string; label: string }[] = [
    { key: 'light', icon: 'sun', label: "Yorug'" },
    { key: 'dark', icon: 'moon', label: "Qorong'i" },
    { key: 'system', icon: 'monitor', label: 'Tizim' },
  ]
  return (
    <div role="group" aria-label="Mavzu"
      className="mx-2.5 my-1.5 flex gap-0.5 rounded-md bg-muted p-0.5">
      {opts.map((o) => (
        <button key={o.key} type="button" onClick={() => onChange(o.key)}
          title={o.label} aria-pressed={theme === o.key}
          className={cn('flex flex-1 items-center justify-center rounded-[5px] py-1 transition-colors',
            theme === o.key
              ? 'bg-card text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground')}>
          <Icon name={o.icon} size={14} />
        </button>
      ))}
    </div>
  )
}

function readParam(name: string): number | null {
  const v = new URLSearchParams(window.location.search).get(name)
  const n = v ? Number(v) : NaN
  return Number.isFinite(n) && n > 0 ? n : null
}

/** Havola ishlatilgach manzil qatori tozalanadi — sahifa yangilanganda
 *  o'sha oyna qayta ochilib qolmasin (tender-ai dagi ?tender= bilan bir xil). */
function clearQuery() {
  if (window.location.search) {
    window.history.replaceState({}, '', window.location.pathname)
  }
}

export default function App() {
  // Kun BOSHQARUV PANELIDAN boshlanadi: "nima qilishim kerak?" degan
  // savolga javob birinchi ekranda turishi kerak.
  const [view, setView] = useState<View>('dashboard')
  const [health, setHealth] = useState<ErpHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Chuqur havolalar — faqat birinchi yuklashda o'qiladi
  const [takeTender] = useState<number | null>(() => readParam('take'))
  const [oppFocus, setOppFocus] = useState<number | null>(() => readParam('opp'))
  const [takeOpen, setTakeOpen] = useState<boolean>(() => readParam('take') !== null)

  // Brokerlar ro'yxati bir marta: "Mening ishlarim" filtri uchun.
  const [brokers, setBrokers] = useState<ErpBroker[]>([])
  // O'z parolini almashtirish oynasi (auth-6)
  const [pwdOpen, setPwdOpen] = useState(false)
  const { theme, setTheme } = useTheme()

  // KIRISH. `undefined` — hali tekshirilmadi (token bor, so'rov ketyapti);
  // `null` — kirilmagan. Ikkisini ajratmasak, sahifa har yangilanganda
  // kirish ekrani bir lahza chaqnab ketardi.
  const [user, setUserState] = useState<AuthUser | null | undefined>(
    () => (getToken() ? undefined : null))

  /** Foydalanuvchi bilan birga uning HUQUQLAR kesimi ham saqlanadi
   *  (`erpShared.setPerms`). Ikkisi bitta joyda o'rnatiladi: aks holda
   *  kirish bir yo'ldan (login), huquq boshqasidan (me) kelib, ular
   *  ajralib qolishi mumkin edi. */
  function setUser(u: AuthUser | null | undefined) {
    setPerms(u && typeof u === 'object' ? u.perms : null)
    setUserState(u)
  }

  useEffect(() => {
    // 401 — sessiya tugadi: kirish ekraniga qaytamiz (api.ts chaqiradi).
    setUnauthorizedHandler(() => setUser(null))
    return () => setUnauthorizedHandler(null)
  }, [])

  useEffect(() => {
    if (user === undefined) {
      // Saqlangan token haqiqiymi — bir marta tekshiriladi
      api.me().then(setUser).catch(() => setUser(null))
      return
    }
    if (!user) return
    api.health().then(setHealth).catch((e: Error) => setError(e.message))
    api.brokers().then(setBrokers).catch(() => {})
    clearQuery()
  }, [user])

  async function logout() {
    await api.logout().catch(() => {})
    setUser(null); setHealth(null); setBrokers([])
  }

  /** Kartani ochish: bo'lim almashadi va o'sha karta ko'rsatiladi.
   *  focusId QAYTA o'rnatiladi (avval null) — bir xil kartani ikkinchi marta
   *  bosganda ham ochilsin. */
  function openOpportunity(oppId: number) {
    setOppFocus(null)
    setView('opportunities')
    setTimeout(() => setOppFocus(oppId), 0)
  }

  // Token tekshirilmaguncha bo'sh ekran — kirish formasi chaqnamasin
  if (user === undefined) return <div className="min-h-screen bg-background" />
  if (!user) return <LoginPage onLogin={setUser} />

  // Tahlil odamlar haqidagi ko'rsatkichni ham beradi — brokerga ko'rsatilmaydi
  const isManager = roleAtLeast(user.role, 'menejer')
  // Bo'limlar HUQUQ bo'yicha yashiriladi (rol bo'yicha emas): "kim
  // ko'radi" degan qaror serverdagi matritsada, bu yerda faqat uning
  // natijasi ishlatiladi.
  const nav = NAV.filter((n) => (n.key !== 'company' || isManager)
    && (n.key !== 'staff' || can('tizim.hodim')))
  const current = NAV.find((n) => n.key === view)

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* --- yon panel --- */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r bg-sidebar px-3 py-4 md:flex">
        <div className="mb-4 flex items-center gap-2.5 px-1">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Icon name="briefcase" size={17} />
          </span>
          <div className="min-w-0">
            <div className="truncate text-body font-semibold leading-tight">Tender ERP</div>
            <div className="truncate text-micro text-muted-foreground">ichki ish kartalari</div>
          </div>
        </div>

        {/* Menyu GURUHLARGA bo'lingan: yetti bandli tekis ro'yxatda ko'z
            har safar boshidan qidiradi. Guruh sarlavhasi — o'qilmaydigan
            bezak emas, u ro'yxatning yarmini darhol chiqarib tashlaydi. */}
        <nav className="flex-1 overflow-y-auto">
          {NAV_GROUPS.map((g) => {
            const items = g.items.filter((n) => nav.some((x) => x.key === n.key))
            if (!items.length) return null
            return (
              <div key={g.title} className="mb-3">
                <div className="px-2.5 pb-1 text-micro font-semibold uppercase tracking-wide text-muted-foreground">
                  {g.title}
                </div>
                {items.map((n) => (
                  <button key={n.key} onClick={() => setView(n.key)}
                    title={n.hint}
                    aria-current={view === n.key ? 'page' : undefined}
                    className={cn(
                      'flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-body transition-colors',
                      view === n.key
                        ? 'bg-sidebar-accent font-semibold text-sidebar-accent-foreground'
                        : 'text-foreground/85 hover:bg-accent hover:text-foreground')}>
                    <Icon name={n.icon} size={17}
                      className={view === n.key ? '' : 'text-muted-foreground'} />
                    <span className="flex-1 truncate">{n.label}</span>
                  </button>
                ))}
              </div>
            )
          })}
        </nav>

        {/* Kim kirgan + chiqish */}
        <div className="mt-2 border-t pt-2">
          <div className="flex items-center gap-2.5 px-2.5 py-1.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-caption font-semibold text-secondary-foreground">
              {initials(user.full_name || user.username)}
            </span>
            <div className="min-w-0">
              <div className="truncate text-body font-medium leading-tight">
                {user.full_name}
              </div>
              <div className="truncate text-micro text-muted-foreground">
                {user.role_label || user.role}
              </div>
            </div>
          </div>

          {/* BILDIRISHNOMA — yo'naltirish oqimi kartani o'zi
              ochadi, ya'ni "sizga ish berildi" degan gap biror
              joyda aytilishi kerak (`api/erp/xabar.py`). */}
          <NotificationBell onOpenOpportunity={openOpportunity} />

          <ThemeSwitch theme={theme} onChange={setTheme} />
          {/* O'Z parolini almashtirish — HAR KIM uchun (auth-6).
              Hodimlar ekrani faqat adminga ochiq, ya'ni brokerda
              parolini o'zgartirishning boshqa yo'li yo'q edi. */}
          <button onClick={() => setPwdOpen(true)}
            className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-caption text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
            <Icon name="lock" size={14} />
            Parolni o'zgartirish
          </button>
          <button onClick={logout}
            className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-caption text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
            <Icon name="close" size={14} />
            Chiqish
          </button>
        </div>

        {/* Tender-AI ga qaytish — ikkinchi ilova yonma-yon ishlaydi */}
        {health?.tender_ai_web && (
          <a className="mt-2 flex items-center gap-2 rounded-md px-2.5 py-2 text-caption text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            href={health.tender_ai_web} target="_blank" rel="noopener noreferrer">
            <Icon name="external" size={14} />
            Tender-AI
          </a>
        )}
      </aside>

      {pwdOpen && (
        <MyPasswordPanel userId={user.id} onClose={() => setPwdOpen(false)} />
      )}

      {/* --- asosiy qism --- */}
      <main className="min-w-0 flex-1 px-4 py-4 md:px-6">
        <header className="mb-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <div className="min-w-0">
              <h1 className="text-lead font-semibold leading-tight">
                {current?.label}
              </h1>
              {/* Bir qatorli izoh — ekran NIMA UCHUNligini aytadi.
                  Sarlavhaning o'zi ("Ombor") buni aytmaydi. */}
              {current?.hint && (
                <p className="mt-0.5 text-caption text-muted-foreground">
                  {current.hint}
                </p>
              )}
            </div>
          </div>

          {/* Mobil ekranda yon panel yo'q — bo'lim almashtirgich shu yerda.
              Gorizontal siljish: bandlar siqilib o'qilmas bo'lib
              qolgandan ko'ra surilgani afzal. */}
          <div className="-mx-4 mt-3 flex gap-1 overflow-x-auto px-4 pb-1 md:hidden">
            {nav.map((n) => (
              <button key={n.key} onClick={() => setView(n.key)}
                className={cn('shrink-0 rounded-md px-2.5 py-1 text-caption transition-colors',
                  view === n.key
                    ? 'bg-secondary font-semibold text-primary'
                    : 'text-muted-foreground hover:bg-accent')}>
                {n.label}
              </button>
            ))}
          </div>
        </header>

        {error && <ErpError msg={error} />}

        {/* EGALIK: "o'z ishlarim" HISOB HODIMGA bog'langanda ishlaydi
            (`api/erp/egalik.py`). Bog'lanmagan bo'lsa ro'yxatlar bo'sh
            keladi — sababini AYTAMIZ, aks holda odam "ma'lumot
            yo'qoldi" deb o'ylardi. */}
        {permLevel('karta.korish') === 'own' && !user.broker_id && (
          <div className="mb-3 rounded-lg border border-soon/40 bg-soon-soft px-3 py-2.5 text-body text-soon-strong">
            <span className="font-semibold">Hisobingiz hodimga bog'lanmagan.</span>{' '}
            Shuning uchun kartalar, mijozlar va hujjatlar ro'yxati bo'sh.
            Administrator "Hodimlar" ekranida hisobingizni hodim yozuviga
            bog'lashi kerak.
          </div>
        )}

        {/* Tender-AI yiqilgan bo'lsa ERP ISHLAYVERADI: mavjud kartalar
            ochiladi, faqat cheklist va yangi karta olish ishlamaydi. Buni
            yashirmaymiz. */}
        {health && !health.ok && (
          <ErpError msg="Baza mavjud emas — kartalar ko'rsatilmaydi." />
        )}
        {health && health.ok && !health.schema_ready && <SchemaMissing />}
        {health && health.ok && health.schema_ready && !health.clients_ready && (
          <div className="mb-3">
            <SchemaMissing patch="schema_patch_erp_2.sql" />
          </div>
        )}

        {!health && !error && <Skeleton className="h-64 w-full rounded-lg" />}

        {health?.ok && health.schema_ready && (<>
          {view === 'dashboard' && (
            <Dashboard user={user} onOpenOpportunity={openOpportunity}
              onGo={(v) => setView(v as View)} />
          )}
          {view === 'opportunities' && (
            <OpportunitiesPage focusId={oppFocus} tenderWeb={health.tender_ai_web} />
          )}
          {view === 'mytasks' && (
            <MyTasksPage brokers={brokers} onOpenOpportunity={openOpportunity} />
          )}
          {view === 'clients' && (
            <ClientsPage onOpenOpportunity={openOpportunity} />
          )}
          {view === 'company' && (
            <OwnCompanyPage onOpenOpportunity={openOpportunity} />
          )}
          {view === 'stock' && <StockPage />}
          {view === 'invoices' && <InvoicePage />}
          {view === 'staff' && can('tizim.hodim') && <StaffPage />}
        </>)}
      </main>

      {/* Tender-AI dan "ERP da ishga olish" bilan kelingan bo'lsa forma
          darhol ochiladi — foydalanuvchi tenderni qidirib o'tirmasin. */}
      {/* Karta yaratish — rahbar-menejer amali (`karta.yaratish`).
          Tender-AI dan "ERP da ishga olish" havolasi bilan kelgan
          brokerga forma OCHILMAYDI: u to'ldirib bo'lib, oxirida 403
          olardi. Buning o'rniga nima qilish kerakligi aytiladi. */}
      {takeOpen && takeTender !== null && !can('karta.yaratish') && (
        <div className="fixed inset-x-0 bottom-4 mx-auto w-fit rounded-lg border bg-card px-4 py-3 text-body shadow">
          Tenderni ishga olishni rahbar yoki menejer bajaradi.
          <button type="button" className="ml-3 text-caption underline"
            onClick={() => setTakeOpen(false)}>yopish</button>
        </div>
      )}
      {takeOpen && takeTender !== null && can('karta.yaratish') && (
        <TakeTenderDialog
          tenderId={takeTender}
          onClose={() => setTakeOpen(false)}
          onOpenOpportunity={(id) => { setTakeOpen(false); setOppFocus(id); setView('opportunities') }}
        />
      )}
    </div>
  )
}
