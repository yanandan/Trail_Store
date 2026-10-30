"""Trail Supply: a dependency-free knowledge graph and tool-using retail agent."""
import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent


def ai_plan(message):
    """Optional LLM tool call; only a validated search plan crosses into retrieval."""
    key = os.environ.get('TRAIL_AI_API_KEY')
    if not key:
        return None
    properties = {
        'activities': {'type': 'array', 'items': {'type': 'string', 'enum': ['hiking', 'backpacking', 'running', 'camping']}},
        'weather': {'type': 'array', 'items': {'type': 'string', 'enum': ['rain', 'cold', 'wind', 'dry']}},
        'category': {'type': 'string', 'enum': ['All', 'Footwear', 'Packs', 'Apparel', 'Accessories', 'Shelter']},
        'budget': {'type': ['number', 'null'], 'description': 'Maximum price per item, or null if unspecified'},
    }
    payload = {'model': os.environ.get('TRAIL_AI_MODEL', 'gpt-4o-mini'), 'messages': [
        {'role': 'system', 'content': 'You plan product searches for an outdoor store. Extract only explicitly requested constraints. Call search_catalog once. Budget is per item. Do not invent product facts, prices, inventory or constraints.'},
        {'role': 'user', 'content': message}],
        'tools': [{'type': 'function', 'function': {'name': 'search_catalog', 'description': 'Search the product knowledge graph and validate availability and budget.', 'parameters': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}, 'strict': True}}],
        'tool_choice': {'type': 'function', 'function': {'name': 'search_catalog'}}}
    req = urllib.request.Request('https://api.openai.com/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.load(response)
    call = data['choices'][0]['message']['tool_calls'][0]['function']
    if call['name'] != 'search_catalog':
        raise ValueError('Unexpected tool')
    plan = json.loads(call['arguments'])
    for field in ['activities', 'weather']:
        if not isinstance(plan.get(field), list) or any(v not in properties[field]['items']['enum'] for v in plan[field]):
            raise ValueError('Invalid plan')
    if plan.get('category') not in properties['category']['enum']:
        raise ValueError('Invalid category')
    budget = plan.get('budget')
    if budget is not None and (type(budget) not in (int, float) or not 0 <= budget <= 1000000):
        raise ValueError('Invalid budget')
    return plan
PRODUCTS = [
    dict(id='p1', name='Ridgeline Trail Shoes', category='Footwear', price=125, stock=18, activities=['hiking', 'running'], features=['grip', 'lightweight'], weather=['dry'], icon='🥾', description='Grippy, lightweight shoes for fast days on dry trails.'),
    dict(id='p2', name='Stormcrest Hiking Boots', category='Footwear', price=185, stock=9, activities=['hiking', 'backpacking'], features=['waterproof', 'grip', 'support'], weather=['rain', 'cold'], icon='🥾', description='Waterproof boots with support for wet trails and loaded packs.'),
    dict(id='p3', name='Cloudbreak Rain Shell', category='Apparel', price=110, stock=24, activities=['hiking', 'backpacking', 'running'], features=['waterproof', 'lightweight'], weather=['rain', 'wind'], icon='🧥', description='A packable waterproof layer for changing mountain weather.'),
    dict(id='p4', name='Daybreak 22L Pack', category='Packs', price=79, stock=15, activities=['hiking'], features=['lightweight', 'hydration-ready'], weather=['dry', 'rain'], icon='🎒', description='A compact day pack with room for layers, snacks and water.'),
    dict(id='p5', name='Traverse 55L Pack', category='Packs', price=210, stock=6, activities=['backpacking', 'camping'], features=['support', 'hydration-ready'], weather=['dry', 'rain'], icon='🎒', description='A supportive overnight pack for multi-day escapes.'),
    dict(id='p6', name='Switchback Trekking Poles', category='Accessories', price=65, stock=20, activities=['hiking', 'backpacking'], features=['support', 'lightweight'], weather=['dry', 'rain'], icon='🏔️', description='Adjustable poles for balance and steady descents.'),
    dict(id='p7', name='Alpine Warmth Fleece', category='Apparel', price=85, stock=12, activities=['hiking', 'camping', 'backpacking'], features=['insulated'], weather=['cold', 'wind'], icon='🧥', description='A warm midlayer for crisp mornings and evenings at camp.'),
    dict(id='p8', name='Starlight Two-Person Tent', category='Shelter', price=249, stock=4, activities=['camping', 'backpacking'], features=['waterproof', 'lightweight'], weather=['rain', 'wind', 'dry'], icon='⛺', description='A compact two-person shelter for three-season trips.'),
    dict(id='p9', name='Flow 2L Hydration Reservoir', category='Accessories', price=32, stock=28, activities=['hiking', 'running', 'backpacking'], features=['hydration'], weather=['dry', 'rain'], icon='💧', description='A two-liter reservoir compatible with our hydration-ready packs.'),
    dict(id='p10', name='Summit Carbon Trail Shoes', category='Footwear', price=159, stock=0, activities=['running'], features=['grip', 'lightweight'], weather=['dry'], icon='👟', description='Responsive trail running shoes. Currently out of stock.'),
]


def graph():
    nodes, edges = {}, []
    for p in PRODUCTS:
        nodes[p['id']] = dict(id=p['id'], label=p['name'], type='product')
        for field, relation in [('category', 'IN_CATEGORY'), ('activities', 'SUITED_FOR'), ('features', 'HAS_FEATURE'), ('weather', 'SUITS_WEATHER')]:
            for value in ([p[field]] if field == 'category' else p[field]):
                key = field + ':' + value
                nodes[key] = dict(id=key, label=value, type=field)
                edges.append(dict(source=p['id'], target=key, relation=relation))
    for pack in ['p4', 'p5']:
        edges.append(dict(source=pack, target='p9', relation='COMPATIBLE_WITH'))
    return dict(nodes=list(nodes.values()), edges=edges)


def agent(message, category='All'):
    """Bounded plan → graph retrieval → stock/budget validation → explanation."""
    text = message.lower()
    aliases = {'hiking': ['hike', 'hiking', 'day walk'], 'backpacking': ['backpacking', 'multi-day', 'overnight'], 'running': ['running', 'run'], 'camping': ['camping', 'camp']}
    activities = [k for k, terms in aliases.items() if any(t in text for t in terms)]
    weather = [k for k, terms in {'rain': ['rain', 'wet', 'waterproof'], 'cold': ['cold', 'winter', 'warm'], 'wind': ['wind'], 'dry': ['dry', 'sunny']}.items() if any(t in text for t in terms)]
    match = re.search(r'(?:under|below|budget(?:\s+of)?|up to|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d{1,2})?)|\$(\d+(?:\.\d{1,2})?)', text)
    budget = float(next(g for g in match.groups() if g)) if match else None
    mode = 'Local tool agent · no language model'
    planning_note = None
    try:
        plan = ai_plan(message)
        if plan:
            activities, weather = plan['activities'], plan['weather']
            budget = budget if match else plan['budget']
            if category == 'All':
                category = plan['category']
            mode = 'AI tool agent · OpenAI planner + validated graph retrieval'
    except Exception:
        # Provider error details may contain sensitive metadata; never send them to clients.
        planning_note = 'AI planning unavailable; used local rules. No provider response was used.'
    requested = category
    if requested == 'All':
        for cat, words in {'Footwear': ['shoes', 'boots', 'footwear'], 'Packs': ['backpack ', 'pack ', 'packs'], 'Apparel': ['jacket', 'shell', 'fleece', 'apparel'], 'Shelter': ['tent', 'shelter']}.items():
            if any(w in text for w in words):
                requested = cat
                break
    trace = [dict(tool='plan_request', detail=f"Activity: {', '.join(activities) or 'any'} · Weather: {', '.join(weather) or 'any'} · Category: {requested} · Per-item budget: {'$'+format(budget, 'g') if budget is not None else 'not set'}")]
    if planning_note:
        trace[0]['detail'] += ' · ' + planning_note
    candidates = [p for p in PRODUCTS if (requested == 'All' or p['category'] == requested) and (not activities or any(a in p['activities'] for a in activities)) and (not weather or all(w in p['weather'] for w in weather))]
    trace.append(dict(tool='query_knowledge_graph', detail=f"Traversed SUITED_FOR, SUITS_WEATHER and IN_CATEGORY edges; found {len(candidates)} matching products."))
    available = [p for p in candidates if p['stock'] > 0 and (budget is None or p['price'] <= budget)]
    trace.append(dict(tool='check_inventory_and_price', detail=f"{len(available)} products in stock and within the per-item budget. No constraints were relaxed."))
    available.sort(key=lambda p: (-sum(f in text for f in p['features']), p['price']))
    recommendations = []
    g = graph()
    for p in available[:4]:
        evidence = [e for e in g['edges'] if e['source'] == p['id'] and (e['target'] in ['activities:'+a for a in activities] + ['weather:'+w for w in weather] or e['relation'] == 'IN_CATEGORY')]
        recommendations.append(dict(**p, evidence=evidence, reason='; '.join([f"Suited for {a}" for a in activities if a in p['activities']] + [f"Suitable for {w}" for w in weather] + [f"{p['stock']} in stock", f"${p['price']}" ])))
    trace.append(dict(tool='explain_recommendations', detail=f"Returned {len(recommendations)} recommendations with graph evidence. Inventory and prices are sample data."))
    answer = ('Here are the strongest matches from our sample catalog. Your budget applies to each item, not a complete kit.' if recommendations else 'No in-stock products match all those constraints. Try a higher per-item budget or a different category or weather condition.')
    if not activities:
        answer += ' Tell me your activity for more focused recommendations.'
    return dict(answer=answer, products=recommendations, trace=trace, constraints=dict(activities=activities, weather=weather, budget=budget, category=requested), mode=mode)


class Handler(BaseHTTPRequestHandler):
    def send(self, status, data, mime='application/json'):
        body = json.dumps(data).encode() if mime == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/catalog':
            return self.send(200, dict(products=PRODUCTS, graph=graph()))
        if path == '/api/health':
            return self.send(200, dict(status='ok', mode='local', products=len(PRODUCTS)))
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if path not in files:
            return self.send(404, dict(error='Not found'))
        name, mime = files[path]
        self.send(200, (ROOT / 'static' / name).read_bytes(), mime)

    def do_POST(self):
        if self.path != '/api/agent':
            return self.send(404, dict(error='Not found'))
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 16384:
                return self.send(400, dict(error='Request must be between 1 and 16384 bytes'))
            body = json.loads(self.rfile.read(length))
            message = body.get('message', '')
            if not isinstance(message, str) or not message.strip() or len(message) > 2000:
                return self.send(400, dict(error='Enter a request of 1–2000 characters'))
            category = body.get('category', 'All')
            if category not in ['All', 'Footwear', 'Packs', 'Apparel', 'Accessories', 'Shelter']:
                return self.send(400, dict(error='Unknown category'))
            self.send(200, agent(message, category))
        except (ValueError, AttributeError, TypeError):
            self.send(400, dict(error='Invalid JSON request'))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    print(f'Trail Supply listening on {args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
