import path from 'node:path'
// `defineConfig` VITEST dan olinadi: `test` bo'limining turi shu
// paketda e'lon qilingan. `vite` dan olinsa `tsc` uni notanish
// kalit deb hisoblaydi va qurilish yiqiladi.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// ERP interfeysi — ALOHIDA ilova, o'z portida (5174). Tender-AI :5173 da
// yonma-yon ishlaydi va ikkalasi bir-biriga havola bilan bog'lanadi.
//
// PROKSI: /api -> ERP backend (:8100). Tender-AI ga to'g'ridan-to'g'ri
// murojaat YO'Q — ERP unga faqat SERVER tomonidan boradi (api/tenderai.py).
export default defineConfig({
  // PLUGINLAR RO'YXATI — usiz Tailwind UMUMAN ishga tushmaydi.
  // `@import 'tailwindcss'` o'shanda oddiy CSS import bo'lib qoladi:
  // `@theme` va `@custom-variant` matn holida o'tib ketadi, birorta
  // utilita sinfi (`.flex`, `.rounded-lg`) YARATILMAYDI. Sahifa
  // butunlay bezaksiz chiqadi, `npm run build` esa muvaffaqiyatli
  // tugaydi — shuning uchun bu xato faqat EKRANDA ko'rinadi.
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  // SINOV MUHITI — `jsdom`, chunki komponentlar DOM ga tayanadi.
  // `globals: true` YO'Q: `describe`/`it` ataylab import qilinadi, aks
  // holda fayl qayerdan kelganini o'qib bo'lmaydi.
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
