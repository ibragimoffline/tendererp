"""
QURILGAN INTERFEYSNI TEKSHIRISH — "build o'tdi" degani "ishlaydi" emas.

    .venv/Scripts/python.exe check_build.py

NEGA BU FAYL BOR.

`frontend/vite.config.ts` da `plugins` ro'yxati tushib qolgan edi:
`react` va `tailwindcss` import qilingan, lekin ro'yxatga qo'shilmagan.
Natijada Tailwind UMUMAN ishga tushmagan — `@import 'tailwindcss'`
oddiy CSS importga aylangan, birorta utilita sinfi (`.flex`,
`.rounded-lg`) yaratilmagan va interfeys butunlay bezaksiz chiqqan.

Eng yomoni: `tsc` ham, `npm run build` ham **muvaffaqiyatli** tugagan.
Utilitasiz CSS ham to'g'ri CSS, ya'ni hech qanday vosita xato
ko'rsatmagan. Xato faqat EKRANDA ko'ringan va uni haftalar davomida
hech kim sezmagan.

Shuning uchun bu yerda "quriladimi" emas, **NATIJASI TO'G'RIMI** degan
savol tekshiriladi.

(ESLint qo'shilmadi va bu ham qaror: `typescript-eslint` TypeScript 7
ni hozircha butunlay rad etadi — ishga tushishdan bosh tortadi. U
qo'llab-quvvatlaganda `no-unused-vars` shu xatoni ham ushlagan bo'lardi.)
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FE = os.path.join(ROOT, "frontend")
DIST = os.path.join(FE, "dist")

#: Qurilgan CSS ichida ALBATTA bo'lishi kerak bo'lgan sinflar.
#: Ular ilovaning har ekranida ishlatiladi — bittasi ham yo'q bo'lsa,
#: Tailwind yurmagan.
REQUIRED_CLASSES = (".flex", ".grid", ".rounded-lg", ".bg-card",
                    ".text-muted-foreground")

#: Qurilgan CSS da QOLMASLIGI kerak: bu Tailwind direktivalari, ular
#: kompilyatsiya qilinishi shart. Qolgan bo'lsa — xom fayl uzatilyapti.
FORBIDDEN = ("@custom-variant", "@theme inline", "@import 'tailwindcss'")

_fail = 0
_pass = 0


def check(cond: bool, msg: str, extra: str = "") -> None:
    global _fail, _pass
    if cond:
        _pass += 1
        print(f"  OK    {msg}")
    else:
        _fail += 1
        print(f"  XATO  {msg}" + (f"\n        -> {extra}" if extra else ""))


def read(path: str) -> str:
    with open(path, "rb") as f:
        return f.read().decode("utf-8", "replace")


def main() -> int:
    print("QURILGAN INTERFEYS TEKSHIRUVI")
    print("=" * 50)

    # --- 1. Konfiguratsiya: aynan o'sha xato takrorlanmasin ---
    cfg_path = os.path.join(FE, "vite.config.ts")
    if not os.path.isfile(cfg_path):
        check(False, "vite.config.ts topilmadi", cfg_path)
        return 1
    cfg = read(cfg_path)
    m = re.search(r"plugins\s*:\s*\[([^\]]*)\]", cfg)
    plugins = m.group(1) if m else ""
    check(bool(m), "vite.config.ts da `plugins` ro'yxati bor",
          "usiz Tailwind ham, React plagini ham ishga tushmaydi")
    check("react()" in plugins, "  plugins: react() bor")
    check("tailwindcss()" in plugins, "  plugins: tailwindcss() bor")

    # Import qilinib, ishlatilmagan plagin — o'sha xatoning izi.
    for name in ("react", "tailwindcss"):
        if re.search(rf"^import\s+{name}\s+from", cfg, re.M):
            check(f"{name}()" in plugins,
                  f"  `{name}` import qilingan VA ishlatilgan",
                  "import bor, lekin plugins ro'yxatida yo'q — "
                  "aynan shu xato interfeysni bezaksiz qoldirgan edi")

    # --- 2. Qurilgan fayllar bormi ---
    index = os.path.join(DIST, "index.html")
    if not os.path.isfile(index):
        check(False, "frontend/dist qurilmagan",
              "npm run build  (yoki run_erp.ps1 -Prod)")
        print("=" * 50)
        print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
        return 1
    check(True, "frontend/dist qurilgan")

    html = read(index)
    css_ref = re.search(r'href="([^"]*assets/[^"]*\.css)"', html)
    js_ref = re.search(r'src="([^"]*assets/[^"]*\.js)"', html)
    check(bool(css_ref), "index.html da CSS havolasi bor")
    check(bool(js_ref), "index.html da JS havolasi bor")
    check("erp.theme" in html,
          "mavzu skripti `<head>` da (chaqnash bo'lmasin)")

    # --- 3. ENG MUHIMI: CSS haqiqiy utilitalarni o'z ichiga oladimi ---
    if css_ref:
        css_path = os.path.join(DIST, css_ref.group(1).lstrip("/"))
        if not os.path.isfile(css_path):
            check(False, "CSS fayli topilmadi", css_path)
        else:
            css = read(css_path)
            kb = len(css.encode("utf-8")) / 1024
            missing = [c for c in REQUIRED_CLASSES if c not in css]
            check(not missing,
                  f"CSS da utilita sinflari bor ({kb:.0f} KB)",
                  f"YO'Q: {', '.join(missing)} — Tailwind ishga "
                  f"tushmagan bo'lishi mumkin")
            left = [d for d in FORBIDDEN if d in css]
            check(not left, "Tailwind direktivalari kompilyatsiya qilingan",
                  f"xom holda qolgan: {', '.join(left)}")
            check(".dark" in css, "qorong'i mavzu qoidalari bor")

    # --- 4. JS bo'sh emasmi ---
    if js_ref:
        js_path = os.path.join(DIST, js_ref.group(1).lstrip("/"))
        if not os.path.isfile(js_path):
            check(False, "JS fayli topilmadi", js_path)
        else:
            kb = os.path.getsize(js_path) / 1024
            check(kb > 100, f"JS to'plami to'la ({kb:.0f} KB)",
                  "juda kichik — qurilish yarim qolganmi?")

    print("=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    if _fail:
        print("\nInterfeys BUZUQ holatda qurilgan. Ishlab chiqarishga "
              "qo'ymang.")
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
