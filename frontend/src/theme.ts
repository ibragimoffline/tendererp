import { useEffect, useState } from 'react'

// MAVZU — yorug' / qorong'i / tizim.
//
// Uchta holat, ikkita emas. "Tizim" — ALOHIDA qiymat, "yorug'" ning
// sinonimi emas: kompyuter kechqurun o'zi qorong'iga o'tsa, ERP ham
// o'tishi kerak. Ikki holatli tugma buni ifodalay olmaydi.
//
// Tanlov `localStorage` da: bu brauzerdagi qulaylik, serverda saqlash
// kerak bo'lgan ma'lumot emas.

export type Theme = 'light' | 'dark' | 'system'

const KEY = 'erp.theme'
const THEMES: Theme[] = ['light', 'dark', 'system']

export function readTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return THEMES.includes(v as Theme) ? (v as Theme) : 'system'
  } catch {
    // Xususiy oyna yoki cheklangan brauzer — sozlama o'qilmasa
    // "tizim" bo'yicha ishlaymiz, ilova to'xtamaydi.
    return 'system'
  }
}

/** `dark` sinfini `<html>` ga qo'yadi/oladi. CSS `@custom-variant dark
 *  (&:is(.dark *))` shu sinfga tayanadi. */
function apply(theme: Theme) {
  const dark = theme === 'dark'
    || (theme === 'system'
      && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
  // Brauzerning o'z elementlari (scrollbar, formalar) ham mos kelsin.
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme)

  useEffect(() => {
    apply(theme)
    try {
      localStorage.setItem(KEY, theme)
    } catch { /* saqlanmasa ham ishlayveradi */ }

    // "Tizim" tanlangandagina tizim o'zgarishini kuzatamiz: aniq
    // tanlov qilingan bo'lsa uni bosib ketmaslik kerak.
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => apply('system')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [theme])

  return { theme, setTheme }
}
