"""Genera i PDF dei progetti (public/pdf/) dalla vista di stampa della PWA.

Uso:  cd public && python3 -m http.server 8765   (in un altro terminale)
      python3 tools/make_pdfs.py
Richiede: pip install playwright && playwright install chromium (oppure Chrome installato).
"""
import asyncio, json, os, re, shutil, subprocess, sys
from playwright.async_api import async_playwright

BASE = os.environ.get('LAB_URL', 'http://localhost:8765/')
OUT = os.path.join(os.path.dirname(__file__), '..', 'public', 'pdf')
CHROME = shutil.which('google-chrome') or shutil.which('chromium')

FOOTER = ('<div style="font-size:8px;width:100%;padding:0 12mm;color:#6b7280;display:flex;justify-content:space-between">'
          '<span>ESP32 Lab</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=['--no-sandbox']) if CHROME else await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto(BASE)
        ids = await pg.evaluate("import('./js/projects.js').then(m => m.PROJECTS.map(p => [p.n, p.id]))")
        targets = [(f'ESP32-Lab-{n:02d}-{pid}.pdf', pid) for n, pid in ids] + [('ESP32-Lab-manuale.pdf', 'tutti')]
        for name, pid in targets:
            await pg.goto(BASE + '#/stampa/' + pid)
            await pg.wait_for_selector('body[data-ready="1"]', timeout=20000)
            await pg.emulate_media(media='print')
            await pg.pdf(path=os.path.join(OUT, name), format='A4', print_background=True,
                         display_header_footer=True, header_template='<span></span>', footer_template=FOOTER,
                         margin={'top': '12mm', 'bottom': '14mm', 'left': '12mm', 'right': '12mm'})
            await pg.emulate_media(media='screen')
            print('ok', name)
        await b.close()

asyncio.run(main())
