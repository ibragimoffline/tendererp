import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '@/api'
import { useFormat } from '@/format'
import Icon from '../Icon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { Opportunity, SubmissionPackage } from '@/types'
import { ErpError } from './erpShared'

// TAKLIF VA TOPSHIRISH (4-bosqich).
//
// Bitta ekranda: narx hisobi, cheklist holati, mijoz hujjatlari va
// tenderning manbadagi statusi. Broker "hozir topshirsam bo'ladimi?"
// degan savolga shu yerdan javob oladi.
//
// CHEKLISTDAGI TO'SIQ — TAQIQ EMAS: hujjat topshirish paytida tayyor
// bo'lishi mumkin va qaror odamniki. Lekin ogohlantirish ko'rsatiladi va
// tasdiq TARIXGA yoziladi.
//
// Topshirilgan taklif MUZLATILADI: narx, o'sha paytdagi cheklist va
// hujjatlar ro'yxati nusxasi saqlanadi. Keyin smeta qayta hisoblansa ham
// topshirilgan versiya o'zgarmaydi.

interface SubmissionPanelProps {
  oppId: number
  onChanged: (o: Opportunity) => void
}

export default function SubmissionPanel({ oppId, onChanged }: SubmissionPanelProps) {
  const f = useFormat()
  const [pkg, setPkg] = useState<SubmissionPackage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [price, setPrice] = useState('')
  const [note, setNote] = useState('')
  const [confirmNote, setConfirmNote] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api.submissionPackage(oppId)
      .then((p) => {
        setPkg(p)
        setPrice(p.suggested_price != null ? String(p.suggested_price) : '')
      })
      .catch((e: ApiError) => setError(
        e.status === 503 ? 'Takliflar jadvali yo\'q: schema_patch_erp_4.sql qo\'llanmagan.'
          : e.message))
  }, [oppId])

  useEffect(() => { load() }, [load])

  async function submit() {
    if (!pkg) return
    setBusy(true); setError(null)
    try {
      const res = await api.submit(oppId, {
        price: price ? Number(price) : null,
        currency: pkg.currency, confirmed,
        confirmed_note: confirmNote || null, note: note || null,
        submitted_by: pkg.opportunity.broker?.name ?? null,
      })
      onChanged(res.opportunity)
      setNote(''); setConfirmNote(''); setConfirmed(false)
      load()
    } catch (e) {
      setError((e as Error).message)
    } finally { setBusy(false) }
  }

  if (error && !pkg) return <ErpError msg={error} />
  if (!pkg) return <Skeleton className="h-40 w-full rounded-lg" />

  const s = pkg.compliance?.summary
  const needConfirm = pkg.blocking > 0

  return (
    <div className="space-y-3">
      {error && <ErpError msg={error} />}

      {/* --- yig'ma holat --- */}
      <div className="grid gap-2 sm:grid-cols-3">
        <Box label="Narx hisobi"
          value={pkg.suggested_price != null
            ? f.money(pkg.suggested_price, pkg.currency) : '—'}
          hint={pkg.pricing ? 'tender-ai smetasidan' : 'hisoblanmagan'} />
        <Box label="Cheklist"
          value={s ? `${s.ready}/${pkg.compliance!.items.length}` : '—'}
          hint={s ? `${s.missing} yo'q · ${s.expired} muddati o'tgan` : 'olinmadi'}
          tone={pkg.blocking ? 'urgent' : 'ok'} />
        <Box label="Mijoz hujjatlari" value={String(pkg.documents.length)}
          hint={pkg.opportunity.client?.name || 'mijoz tanlanmagan'} />
      </div>

      {/* Ogohlantirishlar YASHIRILMAYDI — ular qaror uchun ma'lumot */}
      {pkg.warnings.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-soon/40 bg-soon-soft px-3 py-2 text-caption text-soon-strong">
          {pkg.warnings.map((w, i) => (
            <li key={i} className="flex gap-1.5">
              <Icon name="alert" size={12} className="mt-0.5 shrink-0" />
              {w}
            </li>
          ))}
        </ul>
      )}

      {pkg.source && (
        <div className="text-caption text-muted-foreground">
          Manbadagi status: <b>{pkg.source.name || pkg.source.status}</b>
          {pkg.source.closed && ' · tender yopilgan'}
        </div>
      )}

      {/* --- topshirish --- */}
      <div className="rounded-lg border p-3">
        <div className="mb-2 text-caption font-semibold text-muted-foreground">
          Topshirishni qayd etish
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <div className="mb-1 text-micro text-muted-foreground">
              Taklif narxi ({pkg.currency || '—'})
            </div>
            <Input className="w-48 tabular" inputMode="decimal" value={price}
              onChange={(e) => setPrice(e.target.value)} placeholder="0" />
          </div>
          <div className="min-w-48 flex-1">
            <div className="mb-1 text-micro text-muted-foreground">Izoh</div>
            <Input value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="ixtiyoriy" />
          </div>
        </div>

        {needConfirm && (
          <div className="mt-2 rounded-md border border-urgent/40 bg-urgent-soft px-3 py-2">
            <label className="flex cursor-pointer items-start gap-2 text-body text-urgent-strong">
              <input type="checkbox" checked={confirmed} className="mt-1"
                onChange={(e) => setConfirmed(e.target.checked)} />
              <span>
                Cheklistda <b>{pkg.blocking}</b> ta to'siq bor. Baribir
                topshirilganini tasdiqlayman — tasdiq tarixga yoziladi.
              </span>
            </label>
            {confirmed && (
              <Input className="mt-2" value={confirmNote}
                onChange={(e) => setConfirmNote(e.target.value)}
                placeholder="Sabab (ixtiyoriy): masalan hujjat topshirish paytida tayyor bo'ladi" />
            )}
          </div>
        )}

        <Button size="sm" className="mt-3"
          disabled={busy || (needConfirm && !confirmed)}
          onClick={submit}>
          {busy ? 'Saqlanmoqda…' : 'Topshirildi deb belgilash'}
        </Button>
      </div>

      {/* --- muzlatilgan versiyalar --- */}
      {pkg.submissions.length > 0 && (
        <div>
          <div className="mb-1 text-caption font-semibold text-muted-foreground">
            Topshirilgan versiyalar ({pkg.submissions.length})
          </div>
          <ul className="space-y-1">
            {pkg.submissions.map((sub) => (
              <li key={sub.id} className="flex flex-wrap items-baseline gap-2 rounded-md border px-3 py-2 text-body">
                <span className="font-semibold">v{sub.version}</span>
                <span className="tabular">{f.money(sub.price, sub.currency)}</span>
                <span className="tabular text-caption text-muted-foreground">
                  {f.dateFmt(sub.submitted_at)}
                </span>
                {sub.submitted_by && (
                  <span className="text-caption text-muted-foreground">{sub.submitted_by}</span>
                )}
                {sub.blocking_count > 0 && (
                  <span className="rounded bg-urgent-soft px-1.5 py-px text-micro font-semibold text-urgent-strong"
                    title={sub.confirmed_note || undefined}>
                    {sub.blocking_count} to'siq bilan
                  </span>
                )}
                {sub.compliance?.summary && (
                  <span className="text-micro text-muted-foreground">
                    cheklist: {sub.compliance.summary.ready} tayyor
                  </span>
                )}
                {sub.note && <span className="text-caption">— {sub.note}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Box({ label, value, hint, tone }: {
  label: string; value: string; hint?: string; tone?: 'ok' | 'urgent'
}) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2">
      <div className="text-caption text-muted-foreground">{label}</div>
      <div className={cn('tabular text-lead font-semibold',
        tone === 'urgent' && 'text-urgent-strong',
        tone === 'ok' && 'text-ok-strong')}>
        {value}
      </div>
      {hint && <div className="text-micro text-muted-foreground">{hint}</div>}
    </div>
  )
}
