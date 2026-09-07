import { useEffect } from 'react'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import Icon from '../Icon'
import type { Invoice } from '@/types'

// BOSMA SHAKL — brauzer chop etadi, PDF kutubxonasi YO'Q.
//
// NEGA KUTUBXONA EMAS: PDF yaratish uchun kutubxona (reportlab,
// weasyprint) shrift, sahifa o'lchami va o'rnatish muammolarini olib
// keladi. Brauzer esa buni allaqachon biladi va "PDF ga saqlash" ham
// uning chop etish oynasida bor.
//
// YURIDIK KUCH YO'Q. O'zbekistonda faktura elektron shaklda, operator
// orqali yuboriladi (`api/erp/invoice_export.py` dagi izohga qarang).
// Bu shakl — mijozga yuborish, imzolatish va ichki tekshiruv uchun.
// Shuning uchun sarlavhada shu ochiq yozilgan.
//
// MA'LUMOT SNAPSHOTDAN: rekvizitlar fakturaga chiqarilgan paytda
// ko'chirilgan va keyin o'zgarmagan. Bu shakl passportga QARAMAYDI.

export default function InvoicePrint({ inv, onClose }: {
  inv: Invoice
  onClose: () => void
}) {
  const f = useFormat()

  // Escape bilan yopish — chop etish oynasi ochilmagan bo'lsa ham.
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const vatRates = Array.from(new Set((inv.lines || []).map((l) => l.vat_rate)))

  return (
    <div className="fixed inset-0 z-50 overflow-auto bg-background">
      {/* Boshqaruv paneli — CHOP ETISHDA KO'RINMAYDI (`print:hidden`) */}
      <div className="sticky top-0 flex flex-wrap items-center gap-2 border-b bg-card px-4 py-2 print:hidden">
        <Button size="sm" onClick={() => window.print()}>
          <Icon name="clip" size={13} /> Chop etish
        </Button>
        <Button size="sm" variant="ghost" onClick={onClose}>Yopish</Button>
        <span className="text-caption text-muted-foreground">
          Chop etish oynasida "PDF ga saqlash" ham bor.
        </span>
      </div>

      <div className="mx-auto max-w-[820px] bg-white p-8 text-black print:p-0">
        <h1 className="mb-1 text-center text-lead font-bold">
          Hisob-faktura {inv.number ? `№ ${inv.number}` : ''}
        </h1>
        <p className="mb-5 text-center text-caption">
          {inv.issued_at ? f.dateFmt(inv.issued_at) : 'sanasi ko\'rsatilmagan'}
          {inv.contract_number && ` · shartnoma ${inv.contract_number}`}
          {inv.due_at && ` · to'lov muddati ${f.dateFmt(inv.due_at)}`}
        </p>

        {/* --- TOMONLAR (snapshot) --- */}
        <table className="mb-5 w-full border border-black text-caption">
          <tbody>
            <Row label="Sotuvchi" p={inv.own} />
            <Row label="Xaridor" p={inv.client} />
          </tbody>
        </table>

        {/* --- QATORLAR --- */}
        <table className="w-full border-collapse border border-black text-caption">
          <thead>
            <tr>
              <Th className="w-8">№</Th>
              <Th>Tovar / xizmat nomi</Th>
              <Th className="w-16">Birlik</Th>
              <Th className="w-20 text-right">Miqdor</Th>
              <Th className="w-28 text-right">Narx</Th>
              <Th className="w-28 text-right">Summa</Th>
              <Th className="w-16 text-right">QQS %</Th>
              <Th className="w-28 text-right">QQS summa</Th>
              <Th className="w-32 text-right">Jami</Th>
            </tr>
          </thead>
          <tbody>
            {(inv.lines || []).map((l, i) => (
              <tr key={l.id}>
                <Td>{i + 1}</Td>
                <Td>{l.name}</Td>
                <Td>{l.unit || ''}</Td>
                <Td className="text-right tabular">{l.qty}</Td>
                <Td className="text-right tabular">{f.money(l.price, inv.currency)}</Td>
                <Td className="text-right tabular">{f.money(l.net, inv.currency)}</Td>
                <Td className="text-right tabular">{l.vat_rate}</Td>
                <Td className="text-right tabular">{f.money(l.vat, inv.currency)}</Td>
                <Td className="text-right tabular">{f.money(l.total, inv.currency)}</Td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-bold">
              <Td className="text-right" colSpan={5}>Jami</Td>
              <Td className="text-right tabular">
                {f.money(inv.totals?.net ?? 0, inv.currency)}
              </Td>
              <Td />
              <Td className="text-right tabular">
                {f.money(inv.totals?.vat ?? 0, inv.currency)}
              </Td>
              <Td className="text-right tabular">
                {f.money(inv.totals?.total ?? 0, inv.currency)}
              </Td>
            </tr>
          </tfoot>
        </table>

        {/* SUMMA SO'Z BILAN — raqamdagi nolni qo'shib qo'yish oson,
            so'zdagisini esa emas. Matn SERVERDA yasaladi va sinaladi. */}
        <p className="mt-3 text-caption">
          <span className="font-semibold">To'lash uchun jami: </span>
          {inv.totals?.words || ''}
        </p>

        {/* QQS holati — nega stavka shunday ekani hujjatda ko'rinsin. */}
        <p className="mt-1 text-micro">
          {inv.client.vat_payer === false
            ? 'Xaridor QQS to\'lovchisi emas — faktura QQS siz.'
            : vatRates.length === 1 && vatRates[0] === 0
              ? 'QQS qo\'llanmagan.'
              : `QQS stavkalari: ${vatRates.join(', ')}%`}
        </p>

        {inv.note && (
          <p className="mt-3 text-caption">
            <span className="font-semibold">Izoh: </span>{inv.note}
          </p>
        )}

        {/* --- IMZOLAR --- */}
        <div className="mt-10 grid grid-cols-2 gap-8 text-caption">
          <Sign role="Sotuvchi" name={inv.own.director} />
          <Sign role="Xaridor" name={inv.client.director} />
        </div>

        <p className="mt-8 text-micro text-neutral-500">
          Ushbu shakl ichki foydalanish va imzolatish uchun. Soliq hisoboti
          uchun elektron hisob-faktura (EHF) operator orqali yuboriladi.
        </p>
      </div>
    </div>
  )
}

function Row({ label, p }: { label: string; p: Invoice['own'] }) {
  return (
    <tr className="align-top">
      <td className="w-24 border border-black px-2 py-1 font-semibold">{label}</td>
      <td className="border border-black px-2 py-1">
        <div className="font-semibold">{p.name || '—'}</div>
        <div>INN: {p.inn || '—'}{p.address ? ` · ${p.address}` : ''}</div>
        <div>
          {p.bank || '—'}
          {p.mfo ? ` · MFO ${p.mfo}` : ''}
          {p.account ? ` · h/r ${p.account}` : ''}
        </div>
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
