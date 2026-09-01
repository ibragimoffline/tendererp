import { useEffect, useState } from 'react'
import { api } from '@/api'
import { useFormat } from '@/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import type { ContractRow, OwnCompany, OwnCompanyInput } from '@/types'
import { ErpError, can } from './erpShared'

// BIZNING KOMPANIYA + SHARTNOMALAR RO'YXATI (5A-1).
//
// Nega kerak: shartnoma IKKI tomonning rekvizitlarini talab qiladi.
// Mijozniki 2-bosqichda bor edi, biznikisi esa hech qayerda yo'q —
// tender-ai dagi `company_profile` qidiruv profili (kalit so'zlar, hududlar,
// sertifikatlar), unda na INN, na bank rekvizitlari.
//
// Bu yerda ikkalasi bir sahifada: rekvizitlar va ular ishlatilgan
// shartnomalar.

const FIELDS: { key: keyof OwnCompanyInput; label: string; wide?: boolean }[] = [
  { key: 'name', label: 'Kompaniya nomi', wide: true },
  { key: 'inn', label: 'INN (9 raqam)' },
  { key: 'oked', label: 'OKED' },
  { key: 'legal_form', label: 'Tashkiliy shakl (MCHJ / AJ / YaTT)' },
  { key: 'tax_mode', label: 'Soliq rejimi' },
  { key: 'address_legal', label: 'Yuridik manzil', wide: true },
  { key: 'address_actual', label: 'Faktik manzil', wide: true },
  { key: 'bank_name', label: 'Bank' },
  { key: 'bank_mfo', label: 'MFO' },
  { key: 'bank_account', label: 'Hisob raqami', wide: true },
  { key: 'director_name', label: 'Rahbar' },
  { key: 'phone', label: 'Telefon' },
  { key: 'email', label: 'Email' },
  { key: 'note', label: 'Izoh', wide: true },
]

const LABELS: Record<string, string> = {
  name: 'nom', inn: 'INN', legal_form: 'tashkiliy shakl',
  address_legal: 'yuridik manzil', bank_account: 'hisob raqami',
  bank_mfo: 'MFO', director_name: 'rahbar',
}

export default function OwnCompanyPage({ onOpenOpportunity }: {
  onOpenOpportunity: (oppId: number) => void
}) {
  const f = useFormat()
  const [own, setOwn] = useState<OwnCompany | null>(null)
  const [form, setForm] = useState<OwnCompanyInput>({ name: '' })
  const [rows, setRows] = useState<ContractRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.ownCompany()
      .then((o) => { setOwn(o); setForm(toForm(o)) })
      .catch((e: Error) => setError(e.message))
    api.contractList().then(setRows).catch(() => setRows([]))
  }, [])

  async function save() {
    setBusy(true); setError(null); setSaved(false)
    try {
      const o = await api.saveOwnCompany(form)
      setOwn(o); setForm(toForm(o)); setSaved(true)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  const set = (patch: Partial<OwnCompanyInput>) => {
    setForm((x) => ({ ...x, ...patch })); setSaved(false)
  }

  if (!own && !error) return <Skeleton className="h-64 w-full rounded-lg" />

  return (
    <div className="space-y-4">
      {error && <ErpError msg={error} />}

      <section className="rounded-lg border bg-card p-4">
        <h2 className="mb-1 text-body font-semibold">Bizning rekvizitlar</h2>
        <p className="mb-3 text-caption text-muted-foreground">
          Shartnoma va hisob-fakturada ishlatiladi. Tender-AI dagi kompaniya
          profili (qidiruv sozlamalari) bundan alohida — u o'z joyida qoladi.
        </p>

        {own && own.missing.length > 0 && (
          <div className="mb-3 rounded-lg border border-soon/40 bg-soon-soft px-3 py-2 text-body text-soon-strong">
            Shartnoma uchun yetishmayapti:{' '}
            {own.missing.map((k) => LABELS[k] || k).join(', ')}
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {FIELDS.map((fl) => (
            <div key={fl.key} className={fl.wide ? 'sm:col-span-2' : undefined}>
              <div className="mb-1 text-caption font-semibold text-muted-foreground">
                {fl.label}
              </div>
              <Input value={(form[fl.key] as string | null) ?? ''}
                onChange={(e) => set({
                  [fl.key]: e.target.value || null,
                } as Partial<OwnCompanyInput>)} />
            </div>
          ))}
        </div>

        {/* QQS — FAKTURA STAVKASIGA ta'sir qiladi. Uch holat: to'lovchi /
            to'lovchi emas / hali so'ralmagan. Oxirgisi `false` bilan bir
            xil emas: "bilmaymiz" degani ochiq savol va uni jimgina 0% ga
            aylantirib yubormaymiz. */}
        <div className="mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2">
          <div>
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Biz QQS to'lovchimizmi
            </div>
            <Select
              value={form.vat_payer === true ? 'yes'
                : form.vat_payer === false ? 'no' : 'unknown'}
              onValueChange={(v) => set({
                vat_payer: v === 'yes' ? true : v === 'no' ? false : null,
              })}>
              <SelectTrigger className="bg-card text-body">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="unknown">Hali so'ralmagan</SelectItem>
                <SelectItem value="yes">Ha, to'lovchi</SelectItem>
                <SelectItem value="no">Yo'q (aylanma solig'i)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="mb-1 text-caption font-semibold text-muted-foreground">
              Bizning stavkamiz (%)
            </div>
            <Input inputMode="decimal" disabled={form.vat_payer !== true}
              value={form.vat_rate ?? ''}
              onChange={(e) => set({
                vat_rate: e.target.value === '' ? null : Number(e.target.value),
              })} />
          </div>
          <p className="sm:col-span-2 text-caption text-muted-foreground">
            {form.vat_payer === false
              ? "Fakturalar QQS SIZ chiqadi — mijoz to'lovchi bo'lsa ham."
              : form.vat_payer === true
                ? 'Stavka mijozning stavkasi bilan solishtiriladi: kichigi olinadi.'
                : "So'ralmaguncha stavka faqat mijoz passportidan olinadi."}
          </p>
        </div>

        <div className="mt-4 flex items-center gap-3">
          {/* Rekvizitni O'ZGARTIRISH — administrator va rahbar ishi
              (`tizim.kompaniya`). Qolganlar ko'radi: faktura va
              shartnoma chop etishda kerak. Tugmani ko'rsatib qo'yish
              esa 403 va'da qilardi. */}
          {can('tizim.kompaniya') ? (
            <Button size="sm" disabled={busy} onClick={save}>
              {busy ? 'Saqlanmoqda…' : 'Saqlash'}
            </Button>
          ) : (
            <span className="text-caption text-muted-foreground">
              Rekvizitlarni administrator yoki rahbar o'zgartiradi.
            </span>
          )}
          {saved && <span className="text-caption text-ok-strong">Saqlandi</span>}
          {own?.updated_at && (
            <span className="text-caption text-muted-foreground">
              oxirgi o'zgarish: {f.dateFmt(own.updated_at)}
            </span>
          )}
        </div>
      </section>

      <section className="rounded-lg border bg-card p-4">
        <h2 className="mb-3 text-body font-semibold">
          Shartnomalar {rows ? `(${rows.length})` : ''}
        </h2>
        {!rows ? (
          <Skeleton className="h-24 w-full" />
        ) : rows.length === 0 ? (
          <div className="text-body text-muted-foreground">
            Shartnoma qayd etilmagan — karta ichida qo'shiladi.
          </div>
        ) : (
          <ul className="divide-y">
            {rows.map((k) => (
              <li key={k.id} className="flex flex-wrap items-baseline gap-2 py-2 text-body">
                <span className="rounded bg-secondary px-1.5 py-px text-micro font-semibold text-primary">
                  {k.status_label || k.status}
                </span>
                <span className="font-medium">{k.number || 'raqamsiz'}</span>
                <span className="tabular">{f.money(k.amount, k.currency)}</span>
                <span className="tabular text-caption text-muted-foreground">
                  {k.signed_at ? f.dateFmt(k.signed_at) : '—'}
                </span>
                <button type="button"
                  className="ml-auto max-w-[22rem] truncate text-caption text-primary hover:underline"
                  onClick={() => onOpenOpportunity(k.opportunity.id)}>
                  {k.opportunity.title || `Karta #${k.opportunity.id}`}
                </button>
                {k.opportunity.client_name && (
                  <span className="text-caption text-muted-foreground">
                    {k.opportunity.client_name}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function toForm(o: OwnCompany): OwnCompanyInput {
  return {
    name: o.name || '', inn: o.inn, oked: o.oked, legal_form: o.legal_form,
    tax_mode: o.tax_mode, address_legal: o.address_legal,
    address_actual: o.address_actual, bank_name: o.bank_name,
    bank_mfo: o.bank_mfo, bank_account: o.bank_account,
    director_name: o.director_name, phone: o.phone, email: o.email, note: o.note,
    vat_payer: o.vat_payer, vat_rate: o.vat_rate,
  }
}
