#!/usr/bin/env python3
"""Resumable, polite crawler for the CartonCloud Academy knowledge base.

Plain HTTP (content is in pre-rendered HTML). BFS from the Academy hub over
/knowledge/ article pages only. Caches every page to disk and skips anything
already cached, so it can be killed and restarted freely. Backs off on 429/5xx.

Output:
  html/<slug>.html   one file per page (the progress ledger)
  manifest.json      [{slug,url,title,breadcrumb,depth}]
  failed.json        urls that never succeeded
"""
import json, os, re, sys, time, html
from urllib.parse import urljoin, urldefrag, urlparse
import urllib.request, urllib.error, socket
from bs4 import BeautifulSoup

BASE = "https://help.cartoncloud.com"
ROOT = "https://help.cartoncloud.com/knowledge/cartoncloud-academy"
HERE = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(HERE, "html")
os.makedirs(HTML_DIR, exist_ok=True)

UA = "Mozilla/5.0 (personal-archive; CartonCloud customer building offline KB copy)"
DELAY = 1.0                       # be gentle: ~1 req/sec
MAX_DEPTH = 2                     # seeds=0, their links=1, those links=2
LIMIT = int(os.environ.get("LIMIT", "0"))   # 0 = no limit (small test = set LIMIT)

# Utility / non-article pages we don't want in the manual.
EXCLUDE_PAT = re.compile(
    r"/knowledge/(kb-tickets|kb-search-results|contact-us|contactsupport)\b")

def slugify(url):
    path = urlparse(url).path
    s = path.replace("/knowledge/", "").strip("/")
    s = s.replace("/", "__") or "index"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)

def is_article(url):
    if not url.startswith(BASE + "/knowledge/"):
        return False
    if EXCLUDE_PAT.search(url):
        return False
    return True

def canon(url):
    url, _ = urldefrag(url)            # drop #fragment
    url = url.split("?")[0]            # drop query
    return url.rstrip("/")

def fetch(url):
    """GET with retry/backoff. Returns html text or None."""
    delay = 2.0
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                wait = delay * attempt
                print(f"    {e.code} on {url} -> sleep {wait:.0f}s", flush=True)
                time.sleep(wait)
                continue
            print(f"    HTTP {e.code} on {url} (giving up)", flush=True)
            return None
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            wait = delay * attempt
            print(f"    {type(e).__name__} on {url} -> sleep {wait:.0f}s", flush=True)
            time.sleep(wait)
    return None

def parse_title(soup):
    t = soup.find("title")
    title = t.get_text(strip=True) if t else ""
    title = re.sub(r"\s*\|\s*CartonCloud.*$", "", title)
    return title or "(untitled)"

def parse_breadcrumb(soup):
    bc = soup.select_one(".kb-breadcrumbs, nav.breadcrumbs, .hs-breadcrumb")
    if not bc:
        # HubSpot breadcrumb module id
        bc = soup.find(id=re.compile("breadcrumb"))
    if not bc:
        return ""
    parts = [a.get_text(" ", strip=True) for a in bc.find_all(["a", "span", "li"])]
    parts = [p for p in parts if p]
    # collapse duplicates while preserving order
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p); out.append(p)
    return " > ".join(out)

def harvest_links(soup):
    out = set()
    for a in soup.find_all("a", href=True):
        u = canon(urljoin(BASE, a["href"]))
        if is_article(u):
            out.add(u)
    return out

def main():
    # seed queue: ROOT plus any pre-enumerated urls passed via manifest_urls.txt
    seeds = [canon(ROOT)]
    seedfile = os.path.join(HERE, "..", "manifest_urls.txt")
    if os.path.exists(seedfile):
        for line in open(seedfile):
            u = canon(line.strip())
            if u and is_article(u):
                seeds.append(u)
    seeds = list(dict.fromkeys(seeds))

    queue = [(u, 0) for u in seeds]
    seen = set(seeds)
    manifest, failed = [], []
    fetched = 0

    while queue:
        url, depth = queue.pop(0)
        slug = slugify(url)
        outf = os.path.join(HTML_DIR, slug + ".html")

        if os.path.exists(outf) and os.path.getsize(outf) > 0:
            text = open(outf, encoding="utf-8").read()           # resume: use cache
            cached = True
        else:
            if LIMIT and fetched >= LIMIT:
                print(f"  LIMIT {LIMIT} reached, stopping new fetches", flush=True)
                break
            print(f"[{len(manifest)+1}] d{depth} GET {url}", flush=True)
            text = fetch(url)
            fetched += 1
            if text is None:
                failed.append(url)
                time.sleep(DELAY)
                continue
            open(outf, "w", encoding="utf-8").write(text)
            cached = False
            time.sleep(DELAY)

        soup = BeautifulSoup(text, "html.parser")
        manifest.append({
            "slug": slug, "url": url, "depth": depth,
            "title": parse_title(soup),
            "breadcrumb": parse_breadcrumb(soup),
            "cached": cached,
        })

        if depth < MAX_DEPTH:
            for nu in sorted(harvest_links(soup)):
                if nu not in seen:
                    seen.add(nu)
                    queue.append((nu, depth + 1))

    manifest.sort(key=lambda m: m["slug"])
    json.dump(manifest, open(os.path.join(HERE, "manifest.json"), "w"), indent=2)
    json.dump(failed, open(os.path.join(HERE, "failed.json"), "w"), indent=2)
    print(f"\nDONE: {len(manifest)} pages cached, {len(failed)} failed, "
          f"{fetched} fetched this run.", flush=True)
    if failed:
        print("FAILED:", *failed, sep="\n  ")

if __name__ == "__main__":
    main()
