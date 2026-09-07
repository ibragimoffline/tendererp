import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import Icon from '../Icon'
import type { ContractSpecification } from '@/types'
import { ErpError } from './erpShared'

// SHARTNOMA ILOVASI — SPETSIFIKATSIYA.
//
// ERP shartnoma MATNINI yozmaydi va bu ongli qaror: huquqiy matn yurist
// ishi, uni shablondan o'ylab topish esa noto'g'ri hujjat chiqarish
// demak. ERP shartnomani QAYD qiladi (raqam, sana, summa, holat).
//
// ERP chiqaradigan qism — ILOVA: tovar/xizmat ro'yxati, miqdor, narx,
// jami. Bu aynan ERP da bor va har bitimda o'zgaradigan qism.
//
// MA'LUMOT UCH MANBADAN, MUZLATILGANI USTUN:
//   invoice  — shu shartnoma bo'yicha chiqarilgan faktura (snapshot);
//   reserves — kartaga ajratilgan tovar (hozirgi holat);
//   none     — hech biri yo'q, ro'yxat bo'sh va shakl buni AYTADI.
// Manba shaklning o'zida ko'rsatiladi — o'quvchi raqamlar qayerdan
// kelganini bilishi kerak.

export default function ContractPrint({ contractId, onClose }: {
  contractId: number
  onClose: () => void
}) {
  const f = useFormat()
  const [spec, setSpec] = useState<ContractSpecification | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.contractSpecification(contractId)
      .then(setSpec)
      .catch((e: Error) => setError(e.message))
  }, [contractId])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 overflow-auto bg-background">
      <div className="sticky top-0 flex flex-wrap items-center gap-2 border-b bg-card px-4 py-2 print:hidden">
        <Button size="sm" onClick={() => window.print()} disabled={!spec}>
          <Icon name="clip" size={13} /> Chop etish
        </Button>
        <Button size="sm" variant="ghost" onClick={onClose}>Yopish</Button>
        <span className="text-caption text-muted-foreground">
          Bu — shartnomaning ILOVASI. Shartnoma matni ERP da saqlanmaydi.
        </span>
      </div>

      {error && <div className="p-4"><ErpError msg={error} /></div>}
      {!spec && !error && <div className="p-8"><Skeleton className="h-64 w-full" /></div>}

      {spec && (
        <div className="mx-auto max-w-[820px] bg-white p-8 text-black print:p-0">
          <h1 className="mb-1 text-center text-lead font-bold">
            {spec.contract.number
              ? `${spec.contract.number}-sonli shartnomaga ilova`
              : 'Shartnomaga ilova'}
          </h1>
          <p className="mb-5 text-center text-caption">
            spetsifikatsiya
            {spec.contract.signed_at && ` · ${f.dateFmt(spec.contract.signed_at)}`}
            {spec.invoice_number && ` · faktura ${spec.invoice_number}`}
          </p>

          <table className="mb-5 w-full border border-black text-caption">
            <tbody>
              <Party label="Yetkazib beruvchi" p={spec.own} />
              <Party label="Xaridor" p={spec.client} />
            </tbody>
          </table>

          {spec.lines.length === 0 ? (
            // BO'SH ro'yxatni yashirmaymiz: "ma'lumot yo'q" ham javob.
            <p className="my-8 text-center text-caption">
              Pozitsiya topilmadi. Faktura yoki ajratilgan tovar kiriting va
              ilovani qayta chiqaring.
            </p>
          ) : (
            <>
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
                    <Th className="w-32 text-right">Jami</Th>
                  </tr>
                </thead>
                <tbody>
                  {spec.lines.map((l, i) => (
                    <tr key={l.id}>
                      <Td>{i + 1}</Td>
                      <Td>{l.name}</Td>
                      <Td>{l.unit || ''}</Td>
                      <Td className="text-right tabular">{l.qty}</Td>
                      <Td className="text-right tabular">
                        {f.money(l.price, spec.contract.currency)}
                      </Td>
                      <Td className="text-right tabular">
                        {f.money(l.net, spec.contract.currency)}
                      </Td>
                      <Td className="text-right tabular">{l.vat_rate}</Td>
                      <Td className="text-right tabular">
                        {f.money(l.total, spec.contract.currency)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="font-bold">
                    <Td className="text-right" colSpan={7}>Jami</Td>
                    <Td className="text-right tabular">
                      {f.money(spec.totals?.total ?? 0, spec.contract.currency)}
                    </Td>
                  </tr>
                </tfoot>
              </table>

              <p className="mt-3 text-caption">
                <span className="font-semibold">Jami: </span>
                {spec.totals?.words || ''}
              </p>
            </>
          )}

          {/* Shartnomadagi summa bilan ilova summasi FARQ QILSA — buni
              aytamiz. Jim qoldirsak, ikki raqam ikki hujjatda turib
              qolardi va farqni hech kim sezmasdi. */}
          {spec.contract.amount != null && spec.totals
            && Math.abs(spec.contract.amount - spec.totals.total) > 0.01 && (
            <p className="mt-3 text-caption">
              <span className="font-semibold">Diqqat: </span>
              shartnomada ko'rsatilgan summa{' '}
              {f.money(spec.contract.amount, spec.contract.currency)} — ilova
              summasidan farq qiladi. Tekshiring.
            </p>
          )}

          <div className="mt-10 grid grid-cols-2 gap-8 text-caption">
            <Sign role="Yetkazib beruvchi" name={spec.own.director} />
            <Sign role="Xaridor" name={spec.client.director} />
          </div>

          {/* Manba shaklning O'ZIDA: raqamlar qayerdan kelgani ko'rinsin. */}
          <p className="mt-8 text-micro text-neutral-500">
            {spec.source === 'invoice'
              ? `Ma'lumot ${spec.invoice_number || ''} fakturadan olindi `
                + '(hujjat chiqarilgan paytdagi holat).'
              : spec.source === 'reserves'
                ? "Ma'lumot ombordan ajratilgan tovarlardan olindi (hozirgi "
                  + 'holat). Narxlarni tekshiring.'
                : "Ma'lumot manbai topilmadi."}
            {' '}Shartnoma matni ERP da saqlanmaydi — bu ilova unga
            qo'shimcha.
          </p>
        </div>
      )}
    </div>
  )
}

function Party({ label, p }: { label: string; p: ContractSpecification['own'] }) {
  return (
    <tr className="align-top">
      <td className="w-36 border border-black px-2 py-1 font-semibold">{label}</td>
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
