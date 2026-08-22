import { useEffect } from 'react'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import Icon from '../Icon'
import type { Act } from '@/types'

// DALOLATNOMANING BOSMA SHAKLI.
//
// Fakturaning bosma shakli bilan bir xil qoidalar (`InvoicePrint.tsx`):
// brauzer chop etadi, PDF kutubxonasi yo'q, ma'lumot snapshotdan,
// yuridik kuchi yo'qligi shaklning O'ZIDA yozilgan.
//
// FARQI — MAZMUNIDA: aktda bank rekvizitlari YO'Q (u to'lov hujjati
// emas) va matnda "ish bajarildi, tomonlarning da'vosi yo'q" degan
// jumla bor — aktning butun ma'nosi shu.

export default function ActPrint({ act, onClose }: {
  act: Act
  onClose: () => void
}) {
  const f = useFormat()

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const period = act.period_from || act.period_to
    ? `${act.period_from ? f.dateFmt(act.period_from) : '…'} — `
      + `${act.period_to ? f.dateFmt(act.period_to) : '…'}`
    : null

  return (
    <div className="fixed inset-0 z-50 overflow-auto bg-background">
      <div className="sticky top-0 flex flex-wrap items-center gap-2 border-b bg-card px-4 py-2 print:hidden">
        <Button size="sm" onClick={() => window.print()}>
          <Icon name="clip" size={13} /> Chop etish
        </Button>
        <Button size="sm" variant="ghost" onClick={onClose}>Yopish</Button>
        <span className="text-caption text-muted-foreground">
          Bu shakl imzolatish uchun. Elektron dalolatnoma operator orqali
          yuboriladi.
        </span>
      </div>

      <div className="mx-auto max-w-[820px] bg-white p-8 text-black print:p-0">
        <h1 className="mb-1 text-center text-lead font-bold">
          Bajarilgan ishlar dalolatnomasi{act.number ? ` № ${act.number}` : ''}
        </h1>
        <p className="mb-5 text-center text-caption">
          {act.act_date ? f.dateFmt(act.act_date) : 'sanasi ko\'rsatilmagan'}
          {period && ` · davr: ${period}`}
          {act.invoice_number && ` · faktura ${act.invoice_number}`}
          {act.contract_number && ` · shartnoma ${act.contract_number}`}
        </p>

        {/* Bank rekvizitlari YO'Q — akt to'lov hujjati emas. */}
        <table className="mb-5 w-full border border-black text-caption">
          <tbody>
            <Party label="Topshirdi" p={act.own} />
            <Party label="Qabul qildi" p={act.client} />
          </tbody>
        </table>

        <table className="w-full border-collapse border border-black text-caption">
          <thead>
            <tr>
              <Th className="w-8">№</Th>
              <Th>Bajarilgan ish / topshirilgan tovar</Th>
              <Th className="w-16">Birlik</Th>
              <Th className="w-20 text-right">Miqdor</Th>
              <Th className="w-28 text-right">Narx</Th>
              <Th className="w-28 text-right">Summa</Th>
              <Th className="w-16 text-right">QQS %</Th>
              <Th className="w-32 text-right">Jami</Th>
            </tr>
          </thead>
          <tbody>
            {(act.lines || []).map((l, i) => (
              <tr key={l.id}>
                <Td>{i + 1}</Td>
                <Td>{l.name}</Td>
                <Td>{l.unit || ''}</Td>
                <Td className="text-right tabular">{l.qty}</Td>
                <Td className="text-right tabular">{f.money(l.price, act.currency)}</Td>
                <Td className="text-right tabular">{f.money(l.net, act.currency)}</Td>
                <Td className="text-right tabular">{l.vat_rate}</Td>
                <Td className="text-right tabular">{f.money(l.total, act.currency)}</Td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-bold">
              <Td className="text-right" colSpan={5}>Jami</Td>
              <Td className="text-right tabular">
                {f.money(act.totals?.net ?? 0, act.currency)}
              </Td>
              <Td />
              <Td className="text-right tabular">
                {f.money(act.totals?.total ?? 0, act.currency)}
              </Td>
            </tr>
          </tfoot>
        </table>

        <p className="mt-3 text-caption">
          <span className="font-semibold">Jami: </span>
          {act.totals?.words || ''}
        </p>

        {/* AKTNING BUTUN MA'NOSI shu jumlada. */}
        <p className="mt-4 text-caption">
          Yuqorida ko'rsatilgan ishlar to'liq va sifatli bajarildi.
          Tomonlarning bir-biriga da'vosi yo'q.
        </p>

        {act.note && (
          <p className="mt-3 text-caption">
            <span className="font-semibold">Izoh: </span>{act.note}
          </p>
        )}

        <div className="mt-10 grid grid-cols-2 gap-8 text-caption">
          <Sign role="Topshirdi" name={act.own.director} />
          <Sign role="Qabul qildi" name={act.client.director} />
        </div>

        <p className="mt-8 text-micro text-neutral-500">
          Ushbu shakl imzolatish va ichki foydalanish uchun. Soliq hisoboti
          uchun elektron dalolatnoma operator orqali yuboriladi.
        </p>
      </div>
    </div>
  )
}

function Party({ label, p }: { label: string; p: Act['own'] }) {
  return (
    <tr className="align-top">
      <td className="w-28 border border-black px-2 py-1 font-semibold">{label}</td>
      <td className="border border-black px-2 py-1">
        <div className="font-semibold">{p.name || '—'}</div>
        <div>INN: {p.inn || '—'}{p.address ? ` · ${p.address}` : ''}</div>
      </td>
    </tr>
  )
}

function Th({ children, className = '' }: { children?: React.ReactNode; className?: string }) {
  return (
    <th className={`border border-black px-2 py-1 text-left font-semibold ${className}`}>
      {children}
    </th>
  )
}

function Td({ children, className = '', colSpan }: {
  children?: React.ReactNode; className?: string; colSpan?: number
}) {
  return (
    <td colSpan={colSpan} className={`border border-black px-2 py-1 ${className}`}>
      {children}
    </td>
  )
}

function Sign({ role, name }: { role: string; name: string | null }) {
  return (
    <div>
      <div className="font-semibold">{role}</div>
      <div className="mt-6 border-b border-black" />
      <div className="mt-1">{name || ''}</div>
      <div className="text-micro text-neutral-500">imzo, M.O'.</div>
    </div>
  )
}
