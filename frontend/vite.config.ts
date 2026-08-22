import path from 'node:path'
import { defineConfig } from 'vite'
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
