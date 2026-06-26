# CartonCloud Knowledge Base — offline manual

Offline markdown copy of CartonCloud's public help centre
(<https://help.cartoncloud.com/knowledge>), compiled for loading into a
claude.ai project so we can reason over "what's possible via the CC API / is a
given workflow worth building" without re-reading the site each chat.

Captured **2026-06-26**. 747 articles. Source content is CartonCloud's public
documentation (we're a CC customer); only the help centre was collected,
politely (1 req/sec, backoff), and only `/knowledge/` article pages.

## What to upload to the claude.ai project

The full KB is ~824k tokens — too big as one file. Pick what's relevant:

| File | Articles | ~Tokens | Use |
|------|----------|---------|-----|
| **`CartonCloud-API-Reference.md`** | 1 page | **33k** | **The complete REST API reference** (api-docs.cartoncloud.com): auth (OAuth2 client-credentials), every endpoint, request/response schemas, curl + JSON samples, webhooks. **Load this first for any API/workflow-feasibility question.** |
| `CartonCloud-Academy-Manual.md` | 46 | 70k | The curated **Academy** curriculum (the structured "how CC works" course). Best starting point for *how the product works*. |
| `sections/CC-KB-Integrations.md` | 94 | 103k | **API, webhooks, accounting/e-commerce/carrier connectors.** Load this for API-feasibility chats. |
| `sections/CC-KB-Warehouse-Management.md` | 138 | 172k | WMS: products, sale/purchase orders, locations, stock. Most relevant to Go Cold. |
| `sections/CC-KB-Mobile-App.md` | 73 | 78k | Scanner/mobile flows (warehouse + transport). |
| `sections/CC-KB-Invoicing.md` | 81 | 92k | Charging, rate cards, invoices. |
| `sections/CC-KB-Account-Management.md` | 201 | 211k | Settings, users, document templates, reporting, hardware. |
| `sections/CC-KB-Transport-Management.md` | 114 | 98k | TMS/consignments (lower priority — Go Cold is WMS-led). |
| `CartonCloud-KB-Full-Manual.md` | 747 | 824k | Everything in one file (only if the project can hold it). |

**Suggested minimal load for API/workflow planning:** `CartonCloud-API-Reference.md`
+ the Academy manual + `CC-KB-Integrations.md` + `CC-KB-Warehouse-Management.md`.

The API reference is a single static Slate page, so it's one fetch, not a crawl:

```bash
curl -s -A "Mozilla/5.0 (personal-archive)" \
  https://api-docs.cartoncloud.com/ -o cc_apidocs/index.html
python3 build_apidocs.py    # -> CartonCloud-API-Reference.md
```

Note: it documents no `warehouse-locations` endpoint — consistent with the
known gotcha that `/warehouse-locations/search` 404s on the public API.

Per-article markdown (one file per page) was also generated during the build but
is not committed here; re-run the builder to regenerate it under `md/`.

## Format notes

- Grouped by the KB's own breadcrumb sections, with a table of contents.
- Each article keeps its `_Source: <url>_` line so Claude can cite/trace back.
- Headings, lists, tables, **bold**, and links preserved; links are absolute.
- Video walkthroughs (YouTube embeds) captured as `**📹 Video:** <url>` lines.
- Images captured as `![alt](cdn-url)` — alt text + URL (not inlined, so the
  files stay text-light; the URLs are live CC CDN links).
- The two pages in `failed.json` are non-content (a support-ticket form and one
  404 dead link) — nothing of substance was lost.

## Refreshing this copy

Both scripts live in this folder and are resumable/polite:

```bash
python3 scrape.py          # re-crawls; skips anything already cached in html/
python3 build_manual.py    # rebuilds the manuals from cached html/
```

`scrape.py` caches each page to `html/<slug>.html` and skips files that already
exist, so a re-run only fetches new/changed pages. To force a full refresh,
delete `html/` first. Set `LIMIT=N` to fetch only N new pages (smoke test).
