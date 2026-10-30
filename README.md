# Trail Supply

A small ecommerce product discovery application for outdoor trail gear. Python 3.11+; no third-party dependencies or provider key required.

## Browser-only demo — no installation

Download `Trail-Supply-Demo.html` and double-click it to open it in a modern browser. It contains its own styles, scripts, sample catalog, graph and recommendation engine. No Python, server, internet connection or API key is needed. A working sample search loads automatically; use the suggestion buttons or enter a request and select **Find my gear**. Select **Explore graph evidence** on a result, click graph nodes, and use **Reset graph** to return to all connections.

This offline version uses local matching rules, not a live language model. Nothing is sent over the network. Budgets apply per item. Try **waterproof hiking boots under $200** to get **Stormcrest Hiking Boots ($185)**, or **hiking boots under $1** to see the no-match response.

Maintainers can regenerate the standalone file with `python build_browser_demo.py` after changing the source catalog or interface. End users only need the generated HTML file.

## Run

```sh
cd /workspace/trail-store
python app.py --port 8080
```

Open port 8080 using your development environment's port access, or browse to http://127.0.0.1:8080 on a local machine. The app binds to loopback by default; use `--host 0.0.0.0` only when your hosting environment requires it. This demo has no user authentication; do not expose it publicly without adding authentication and request limits.

```sh
python -m unittest discover -s tests -v
```

## What it does

- Ten illustrative products with prices, inventory, activities, features and weather suitability.
- An in-memory knowledge graph with typed category, activity, feature, weather and pack/reservoir compatibility edges.
- Interactive graph exploration and graph evidence on each recommendation.
- A bounded local tool agent: parse constraints, traverse graph relationships, validate stock and per-item budget, then explain matches. Four visible steps expose the decision trace. This is a deterministic agent prototype, not an LLM-powered assistant. It supports common English activity/weather/category phrases; it does not understand arbitrary natural language or maintain conversation history.
- No checkout, payments, orders, live inventory, model calls or personal data collection.

Budgets are **per item**, not a complete-kit total. Weather matches require all detected conditions, activity matches accept any detected activity. Results never relax those constraints. Seed data and matching rules live in `app.py`; browser UI lives in `static/`. The graph is rebuilt from the catalog, so update catalog records to change product facts. Google Fonts is optional; system fallbacks work offline.

## API

- `GET /api/health`: readiness and mode
- `GET /api/catalog`: products, graph nodes and relationships
- `POST /api/agent`: JSON such as `{"message":"hiking in rain under $150","category":"All"}` returns recommendations, evidence, parsed constraints and tool trace

## Optional AI planner

The app also supports an OpenAI language-model planner that calls a structured `search_catalog` tool. Set `TRAIL_AI_API_KEY` securely in your runtime and optionally `TRAIL_AI_MODEL` (default `gpt-4o-mini`), allow `api.openai.com` in environment networking, and restart the server. Do not put the key in source files or chat. Requests are sent to OpenAI only when that variable is present. The model translates natural language into validated activity, weather, category and budget constraints; the local graph and inventory tools determine all product facts and recommendations. Provider errors fall back to local rules and appear in the tool trace. The response `mode` identifies the planner used. This optional provider integration has not been validated with a live credential; the default demo works locally.

## Next integration steps

Replace seed catalog with store data and connect inventory reads to your commerce platform. Keep budget/stock checks deterministic. Add provider credentials through secure environment settings, never source control. Live model behavior has not been tested in this version.
