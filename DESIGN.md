---
version: 1
name: tender-erp-design
description: "Zich ichki ish quroli uchun dizayn shartnomasi. Asos 13px, yorug' va qorong'i mavzu teng huquqli, ranglar OKLCH da o'lchab qurilgan: to'yinganlik SHOSHILINCHLIK bilan o'sadi, shuning uchun ro'yxatning aksariyat qatori deyarli rangsiz turadi va faqat bugun tugaydigani ko'zga tashlanadi. Chuqurlik soya bilan emas, SIRT POG'ONASI va bir piksellik chegara bilan beriladi. Aksent rang kam ishlatiladi: asosiy amal tugmasi, fokus halqasi va havola. Bezak uchun animatsiya yo'q."

source:
  reference: "https://github.com/voltagent/awesome-design-md — design-md/linear.app/DESIGN.md"
  note: "Linear fayli ularning MARKETING saytini yozadi (faqat qorong'i #010102 fon, lavanda aksent, 80px sarlavha). Bu yerda undan TIZIM QOIDALARI olingan, tokenlari emas — quyidagi 'Manbadan nima olindi' bo'limiga qarang."

colors:
  primary: "#335eb7"
  on-primary: "#ffffff"
  primary-dark: "#79a3f6"
  ink: "#1d2434"
  ink-subtle: "#616978"
  ink-dark: "#e6eaf0"
  ink-subtle-dark: "#a0a8b6"
  canvas: "#f6f8fc"
  surface-1: "#ffffff"
  surface-2: "#f3f6fb"
  surface-3: "#e6efff"
  canvas-dark: "#11151e"
  surface-1-dark: "#1a202a"
  surface-2-dark: "#242933"
  surface-3-dark: "#293346"
  hairline: "#e1e5ed"
  hairline-soft: "#eceff5"
  hairline-dark: "#2f3642"
  field: "#ced4de"
  ring: "#335eb7"
  ok: "#419368"
  ok-strong: "#2b5f43"
  ok-soft: "#ebf7f0"
  soon: "#ae7200"
  soon-strong: "#714900"
  soon-soft: "#fff2e1"
  urgent: "#d74745"
  urgent-strong: "#902828"
  urgent-soft: "#fff0ee"
  destructive: "#902828"
  chart-1: "#335fbc"
  chart-2: "#b57a00"
  chart-3: "#872b78"
  chart-4: "#218f56"

typography:
  display:
    fontFamily: IBM Plex Sans Variable
    fontSize: 24px
    fontWeight: 600
    lineHeight: 2rem
    letterSpacing: -0.015em
  title:
    fontFamily: IBM Plex Sans Variable
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.625rem
    letterSpacing: 0
  lead:
    fontFamily: IBM Plex Sans Variable
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.375rem
    letterSpacing: 0
  body:
    fontFamily: IBM Plex Sans Variable
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.25rem
    letterSpacing: 0
  caption:
    fontFamily: IBM Plex Sans Variable
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.0625rem
    letterSpacing: 0
  micro:
    fontFamily: IBM Plex Sans Variable
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1rem
    letterSpacing: 0.01em

rounded:
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: 36px
    heightTouch: 40px
    padding: 0 16px
  button-secondary:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: 34px
    heightTouch: 40px
    padding: 0 12px
    border: "1px {colors.field}"
  button-ghost:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: 34px
    heightTouch: 40px
  button-destructive:
    backgroundColor: "{colors.destructive}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
  text-input:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: 36px
    heightTouch: 44px
    padding: 0 12px
    border: "1px {colors.field}"
    fontSizeTouch: 16px
  status-badge:
    backgroundColor: "{colors.surface-3}"
    textColor: "{colors.ink-subtle}"
    typography: "{typography.micro}"
    rounded: "{rounded.xs}"
    padding: 1px 6px
  card:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: 16px
    border: "1px {colors.hairline}"
  inner-panel:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 12px
    border: "1px {colors.hairline}"
  dialog:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: 20px
  sidebar-item:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 6px 10px
  sidebar-item-selected:
    backgroundColor: "{colors.surface-3}"
    textColor: "{colors.primary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
  stat-tile:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    rounded: "{rounded.lg}"
    padding: 10px 12px
    border: "1px {colors.hairline}"
---

## Bu fayl nima

Interfeys qarorlarining YAGONA manbasi. Ranglar, o'lchamlar va shakl
`frontend/src/index.css` da yashaydi — bu yerda esa ULARNI QANDAY
ISHLATISH yozilgan. Ikkalasi ajralib ketmasligi kerak: token o'zgarsa,
shu fayl ham o'zgaradi.

Manba: [awesome-design-md](https://github.com/voltagent/awesome-design-md)
ro'yxatidagi `design-md/linear.app/DESIGN.md`. Linear tanlandi, chunki u
shu ro'yxatdagi yagona **zich ish quroli**: qolganlari (Apple, Nike,
Ferrari, Stripe) — marketing sahifalari, ularning katta sarlavhasi va
havodor oralig'i kuniga o'nlab marta ochiladigan jadval interfeysiga
mos kelmaydi. Loyiha tipografiyasi allaqachon shu yo'nalishda edi
(`index.css`: "asos 13px (Linear, Retool kabi)").

---

## Manbadan nima olindi, nima olinmadi

### Olindi

| Linear qoidasi | Bu yerda |
|---|---|
| Chuqurlik soya bilan emas, **sirt pog'onasi + bir piksellik chegara** bilan | `canvas → surface-1 → surface-2 → surface-3`, har bir kartada `border` |
| **Radius pog'onasi** xs 4 · sm 6 · md 8 · lg 12 · xl 16 · pill | `index.css` dagi `--radius-*`; tugma/maydon 8px, karta 12px |
| Tugma va maydon radiusi bir xil (`md`) — hech qachon pill emas | `button.tsx`, `input.tsx` |
| **Holat nishoni** — `xs` 4px, `micro` tipografiya, 1px 6px ichki oraliq | `erpShared.tsx` → `StatusBadge`, `PriorityBadge` |
| **Tegish nishoni**: asosiy amal ≥40px, maydon sensorli ekranda ≥44px | `button.tsx`, `input.tsx`, `App.tsx` |
| **Aksent kam**: brend belgisi, asosiy tugma, fokus halqasi, havola | `bg-primary` faqat shu joylarda |
| Fokus — 2px halqa, alohida daraja (elevation 4) | `index.css` `:focus-visible` |
| Tanlangan holat — **sirt ko'tarilishi**, alohida rang emas | yon panel va tab bandlari |
| Bo'shliq asosi 4px | Tailwind pog'onasi |

### OLINMADI (va nega)

| Linear qoidasi | Nega yo'q |
|---|---|
| `#010102` yagona qorong'i fon, yorug' mavzu yo'q | ERP kunduzi ofisda ochiladi. Ikkala mavzu ham TENG: `index.css` da qorong'i qadamlar alohida tanlangan, yorug'ining ag'darilishi emas |
| Lavanda `#5e6ad2` aksent | Loyiha aksenti `#335eb7` — u OKLCH da holat ranglari bilan **bitta oilada** o'lchangan. Almashtirilsa butun palitra qayta o'lchanishi kerak bo'lardi |
| 80px/56px/40px sarlavha pog'onasi, -3px tracking | Bu marketing o'lchami. Zich jadvalda eng katta sarlavha 24px |
| "Yagona semantik rang — yashil" | ERP da uchta holat rangi SHART: muddat yetarli / yaqin / o'tgan. Ularsiz shoshilinchlikni faqat matndan o'qish kerak bo'lardi |
| "Har bo'lim mahsulot suratidan boshlanadi" | Bu marketing sahifa ritmi, ilova ichida ma'nosi yo'q |
| Karta 24px ichki oraliq | Zich ro'yxatda 16px — 24px bir ekranga ikki barobar kam qator sig'dirardi |

---

## Rang

### Asos

Hamma rang OKLCH da qurilgan: har ROL uchun yorug'lik qat'iy, ottenka
o'zgaradi. Sabab va o'lchovlar `index.css` boshida.

**Diqqat iyerarxiyasi — asosiy g'oya.** Uchta bir xil baland "svetofor"
rangi o'rniga to'yinganlik shoshilinchlik bilan o'sadi:

```
ok      C 0.016 / 0.072 / 0.105   (fon / matn / to'ldirish)
soon    C 0.040 / 0.098 / 0.128
urgent  C 0.055 / 0.140 / 0.180
```

Ro'yxatdagi qatorlarning aksariyati deyarli rangsiz turadi; haqiqatan
bugun tugaydigani yolg'iz o'zi ko'zga tashlanadi.

### Sirt pog'onasi

| Daraja | Yorug' | Qorong'i | Qayerda |
|---|---|---|---|
| canvas | `#f6f8fc` | `#11151e` | sahifa foni |
| surface-1 | `#ffffff` | `#1a202a` | karta, panel, oyna |
| surface-2 | `#f3f6fb` | `#242933` | ichki blok, o'chirilgan holat |
| surface-3 | `#e6efff` | `#293346` | tanlangan band, nishon foni |

**Ichki panel — CHUQURLASHADI, ko'tarilmaydi.** Kartaning ichidagi blok
`bg-background` (canvas) oladi: ikkala mavzuda ham u kartadan bir qadam
quyuqroq. Linear qorong'ida yuqoriga ko'taradi, lekin yorug' mavzuda oq
kartadan yuqoriga qadam yo'q — shuning uchun bu yerda idioma teskari va
IKKALA mavzuda BIR XIL: karta ko'tariladi, uning ichidagisi cho'kadi.

### Qoidalar

- **MUST**: har rang tokendan olinadi. `text-[#333]` yoki `bg-slate-100`
  yozilmaydi.
- **MUST**: holat faqat rang bilan berilmaydi — yonida matn turadi
  ("3 kun qoldi", "muddati o'tgan").
- **MUST**: `-strong` — MATN uchun (4.5:1+), tayanchsiz nom
  (`--ok`, `--urgent`) — nuqta va to'ldirish uchun (3:1+).
- **SHOULD**: aksent (`bg-primary`) faqat: brend belgisi, asosiy amal
  tugmasi, fokus halqasi, havola, grafik seriyasi.
- **NEVER**: aksent karta yoki bo'lim foni sifatida.

---

## Tipografika

Bitta oila — **IBM Plex Sans Variable**. Monoshirin shrift yo'q:
sonlarni tekislash uchun `.tabular` sinfi (`font-variant-numeric:
tabular-nums`) bor va u shriftni almashtirmaydi.

| Token | O'lcham | Qayerda |
|---|---|---|
| `text-display` | 24px / 600 | sahifa sarlavhasi |
| `text-title` | 18px / 600 | panel sarlavhasi, KPI qiymati |
| `text-lead` | 15px / 600 | karta sarlavhasi, ajratilgan qiymat |
| `text-body` | 13px / 400 | **asosiy**: jadval, forma, tugma |
| `text-caption` | 12px / 400 | ikkilamchi ma'lumot |
| `text-micro` | 11px / 600 | nishon, bo'lim yorlig'i |

- **MUST**: `text-[13px]` kabi o'zboshimcha o'lcham yozilmaydi — faqat
  shu olti pog'ona.
- **MUST**: har qanday son (summa, miqdor, sana, foiz) `.tabular` bilan.
- **MUST**: sensorli ekranda matn maydoni 16px (`text-base md:text-body`)
  — iOS Safari kichikroq maydonda sahifani zumlab, qaytarmaydi.
- **SHOULD**: uzun matn idishi `truncate` / `line-clamp-*` bilan,
  flex bolasi `min-w-0` bilan.

---

## Shakl va chuqurlik

### Radius

| Token | Qiymat | Qayerda |
|---|---|---|
| `rounded` | 4px | nishon, kichik chip |
| `rounded-sm` | 6px | ichki mayda element |
| `rounded-md` | 8px | **tugma, maydon, ichki panel** |
| `rounded-lg` | 12px | **karta, oyna, panel** |
| `rounded-xl` | 16px | eng tashqi idish (kam) |
| `rounded-full` | pill | avatar |

- **MUST**: bola radiusi ota radiusidan katta emas (konsentrik).
  Karta 12px → uning ichidagi panel 8px → nishon 4px.

### Chuqurlik

| Daraja | Usul | Qayerda |
|---|---|---|
| 0 | chegarasiz, soyasiz | matn, ro'yxat qatori |
| 1 | `surface-1` + 1px `hairline` | karta, panel |
| 2 | `canvas` + 1px `hairline` (cho'kkan) | karta ichidagi blok |
| 3 | `surface-1` + `shadow-lg` + fon pardasi | oyna, drawer |
| 4 | `ring-2 ring-ring ring-offset-2` | fokus |

- **NEVER**: tugmaga soya. Zich panelda o'nlab tugma turadi va har
  biridagi soya shovqin. Chegara va fon farqi yetarli.
- **SHOULD**: soya faqat sahifadan ko'tarilgan qatlamda (oyna, drawer).

---

## Tegish va fokus

Linear pog'onasi olindi va sensorli ekran uchun kuchaytirildi:

| Element | Ish stoli | Sensorli (`max-sm`) |
|---|---|---|
| Asosiy tugma | 36px | **40px** |
| `sm` tugma | 34px | **40px** |
| Ikonli tugma | 36px | **40px** |
| Matn maydoni | 36px | **44px** |
| Mavzu / bo'lim almashtirgichi | 28px | **44px** |

- **MUST**: ko'rinadigan nishon 24px dan kichik bo'lsa, tegish maydoni
  kengaytiriladi.
- **MUST**: `:focus-visible` halqasi butun ilovada BITTA qoidada
  (`index.css`). Komponent o'zicha `outline-none` yozmaydi.
- **MUST**: yopishqoq sarlavha va pastki panel fokusdagi elementni
  yopib qo'ymaydi.
- **MUST**: ikondan boshqa mazmuni yo'q tugmada `aria-label` bo'ladi —
  `Icon` `aria-hidden`, ya'ni usiz tugmaning NOMI umuman yo'q.

---

## Harakat

- **MUST**: bezak uchun animatsiya yo'q. Harakat faqat holat
  o'zgarganini bildiradi va 150–200 ms davom etadi.
- **MUST**: `prefers-reduced-motion: reduce` da hammasi o'chadi
  (`index.css` da umumiy qoida bor).
- **MUST**: faqat `transform` va `opacity` animatsiya qilinadi.
- **NEVER**: `transition: all`.

---

## Matn

Interfeys matni — eng oson o'sadigan va eng qiyin qisqaradigan qism.
Chegaralar MAQSAD, qonun emas: ma'no, xavfsizlik va aniqlik ustun.

| Tur | Chegara |
|---|---|
| Tugma | ≤ 3 so'z |
| Yorliq | ≤ 4 so'z |
| Sahifa / bo'lim sarlavhasi | ≤ 5 so'z |
| Bo'sh holat sarlavhasi | ≤ 6 so'z |
| Tooltip | ≤ 12 so'z |
| Bildirishnoma (toast) | ≤ 12 so'z |
| Izoh (helper) | ≤ 18 so'z |
| Xato | ≤ 20 so'z, agar qo'shimcha kontekst shart bo'lmasa |

### Qisqartirishdan oldin — O'CHIRIB ko'ring

Qayta yozishdan ko'ra olib tashlash afzal, agar gap:

- interfeys ko'z bilan aytib turgan narsani takrorlasa (ochilish nishoni,
  ustun sarlavhasi, yonidagi tugma nomi);
- yaqin atrofda allaqachon aytilgan bo'lsa;
- interfeysning ko'rinib turgan xulqini tushuntirsa;
- qaror uchun kerak bo'lgan ma'lumot bermasa (ko'pincha bu SABAB:
  "nega shunday qilingan" — uning joyi kodda, ekranda emas).

Har gapga bitta savol:

> **Bu gap yo'qolsa, foydalanuvchi holatni to'g'ri tushunib, to'g'ri
> amalni bajara oladimi?**

Javob "ha" bo'lsa — o'chiriladi.

### Nima QISQARMAYDI

- **Xatoning chiqish yo'li.** "Nima bo'ldi" yetarli emas, "endi nima
  qilish kerak" ham turishi shart.
- **Yolg'onni to'sadigan gap.** "Sanoq to'g'ri qoladi", "haqiqiy foyda
  bundan kam" — ular raqamning qanday o'qilishini o'zgartiradi.
- **Bosma hujjatdagi huquqiy izoh.** Qog'ozga tushadi va u yerda
  kontekst yo'q.
- **Ikki tushunchani ajratadigan ta'rif.** Masalan "Hodim — kartaga
  mas'ul. Hisob — tizimga kirish."

---

## Holat va bo'shliq

Har ekran to'rt holatni ko'rsatishi kerak va uchalasi ham YOZILGAN
bo'lishi kerak, jimgina bo'sh qolmasligi:

| Holat | Qoida |
|---|---|
| Yuklanmoqda | `Skeleton` — o'lchami keyingi mazmunga yaqin bo'lsin |
| Bo'sh | sabab + keyingi qadam ("Tender panelidan 'ERP da ishga olish' bilan boshlanadi") |
| Xato | sabab + nima qilish kerak; xato JIMGINA YUTILMAYDI |
| Huquq yo'q | tugma KO'RSATILMAYDI (bosilganda 403 beradigan tugma — yolg'on va'da) |

---

## Chop etish

Bosma shakl butun ekranni egallaydi (`fixed inset-0`), `@media print`
da fon va soya olib tashlanadi, jadval qatori sahifa o'rtasidan
bo'linmaydi. Batafsili `index.css` oxirida.

---

## O'zgartirish tartibi

1. Token `index.css` da o'zgaradi, komponentda emas.
2. Shu fayldagi jadval ham yangilanadi — ikkisi ajralib ketmasin.
3. `npm run test` (qoidalar sinovi ranglarni tekshirmaydi, mazmunni
   tekshiradi) va `python check_build.py` (Tailwind haqiqatan
   yurganmi) ishga tushiriladi.
