"""Build a single portable HTML file. Only maintainers need Python to rebuild."""
import json
from pathlib import Path
from app import PRODUCTS, graph

root = Path(__file__).parent
static = root / 'static'
html = (static / 'index.html').read_text()
css = (static / 'style.css').read_text()
css = css[css.index(':root'):]
js = (static / 'app.js').read_text()
js = js.replace("const $=s=>document.querySelector(s); let catalog, active=null;", "const $=s=>document.querySelector(s); let active=null;\nconst catalog=" + json.dumps(dict(products=PRODUCTS, graph=graph()), ensure_ascii=False) + ';')
start = "const r=await fetch('/api/agent'"
end = "$('#answer').textContent=data.answer;"
a, b = js.index(start), js.index(end)
js = js[:a] + "const data=localAgent($('#prompt').value,$('#category').value);" + js[b:]
js = js[:js.index("fetch('/api/catalog')")] + "$('#catalog').replaceChildren(...catalog.products.map(p=>card(p)));draw();\n"
js += "$('#prompt').value='waterproof hiking boots under $200';$('#form').requestSubmit();\n"
html = html.replace('<link rel="stylesheet" href="/style.css">', '<style>' + css + '</style>')
html = html.replace('href="/"', 'href="#"')
html = html.replace('FIELD NOTES / DEMO STORE', 'OFFLINE / BROWSER DEMO')
html = html.replace('<script src="/app.js"></script>', '<script>' + (static / 'local-agent.js').read_text() + '\n' + js + '</script>')
html = html.replace('<section class="workspace">', '<div class="browser-help" style="background:#e7edd9;padding:16px 20px;border-radius:8px;margin:0 0 22px;line-height:1.7"><b>You’re ready to explore.</b> A sample search is loaded below. Try a trip suggestion or type your own request, then select <b>Find my gear</b>. Use <b>Explore graph evidence</b> on a result to see its connections. Everything runs in this browser; no server, sign-in or API key is needed.</div><section class="workspace">')
output = root / 'Trail-Supply-Demo.html'
output.write_text(html)
print(output)
