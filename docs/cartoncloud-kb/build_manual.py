#!/usr/bin/env python3
"""Build a markdown manual from the cached CartonCloud Academy HTML.

Reads manifest.json + html/<slug>.html, extracts each article's body
(the kb-article-module with the most text), converts it to clean markdown,
and writes:
  md/<slug>.md                     one file per article
  CartonCloud-Academy-Manual.md    single combined doc (TOC + all articles)

No external deps beyond bs4. Hub/category pages (no article body) are recorded
as section dividers, not content.
"""
import json, os, re, glob
from urllib.parse import urljoin
from bs4 import BeautifulSoup, NavigableString, Tag

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(HERE, "html")
MD_DIR = os.path.join(HERE, "md")
os.makedirs(MD_DIR, exist_ok=True)
BASE = "https://help.cartoncloud.com"
MODULE_RE = re.compile(r"hs_cos_wrapper_kb-article-module-\d+$")
VIDEO_HOSTS = ("youtube.com", "youtu.be", "wistia", "vimeo", "fast.wistia",
               "loom.com", "vidyard")

# ---- inline + block HTML -> markdown ---------------------------------------

def esc(t):
    return t.replace(" ", " ")

def inline(node):
    """Render inline content of a node to a markdown string."""
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            out.append(esc(str(c)))
        elif isinstance(c, Tag):
            n = c.name
            if n in ("strong", "b"):
                s = inline(c).strip()
                out.append(f"**{s}**" if s else "")
            elif n in ("em", "i"):
                s = inline(c).strip()
                out.append(f"*{s}*" if s else "")
            elif n == "code":
                out.append(f"`{c.get_text()}`")
            elif n == "br":
                out.append("  \n")
            elif n == "a":
                href = c.get("href", "")
                txt = inline(c).strip() or href
                if href:
                    href = urljoin(BASE, href)
                    out.append(f"[{txt}]({href})")
                else:
                    out.append(txt)
            elif n == "img":
                out.append(img_md(c))
            elif n in ("iframe",):
                out.append(media_md(c))
            elif n in ("span", "u", "sub", "sup", "font", "small", "abbr", "mark"):
                out.append(inline(c))
            else:
                out.append(inline(c))
    return "".join(out)

def img_md(c):
    src = c.get("src") or c.get("data-src") or ""
    if src:
        src = urljoin(BASE, src)
    alt = (c.get("alt") or "").strip()
    return f"![{alt}]({src})" if src else ""

def media_md(c):
    src = c.get("src") or c.get("data-src") or ""
    src = urljoin(BASE, src) if src else ""
    label = "Video"
    if any(h in src for h in VIDEO_HOSTS):
        label = "Video"
    return f"\n\n**📹 {label}:** {src}\n\n" if src else ""

def list_md(node, ordered, depth=0):
    lines = []
    i = 1
    for li in node.find_all("li", recursive=False):
        # split inline content from nested lists
        nested = li.find_all(["ul", "ol"], recursive=False)
        # render li's own inline text (excluding nested lists)
        clone_parts = []
        for c in li.children:
            if isinstance(c, Tag) and c.name in ("ul", "ol"):
                continue
            if isinstance(c, NavigableString):
                clone_parts.append(esc(str(c)))
            elif isinstance(c, Tag):
                if c.name == "p":
                    clone_parts.append(inline(c))
                else:
                    clone_parts.append(inline(c) if c.name not in ("ul", "ol") else "")
        text = " ".join(p.strip() for p in clone_parts if p.strip())
        bullet = f"{i}." if ordered else "-"
        indent = "  " * depth
        lines.append(f"{indent}{bullet} {text}".rstrip())
        for sub in nested:
            lines.append(list_md(sub, sub.name == "ol", depth + 1))
        i += 1
    return "\n".join(l for l in lines if l)

def table_md(node):
    rows = []
    for tr in node.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        rows.append([inline(c).strip().replace("\n", " ") for c in cells])
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "| " + " | ".join(["---"] * ncol) + " |"]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)

def block(node):
    """Walk block-level children of the body and emit markdown blocks."""
    parts = []
    for c in node.children:
        if isinstance(c, NavigableString):
            t = esc(str(c)).strip()
            if t:
                parts.append(t)
            continue
        if not isinstance(c, Tag):
            continue
        n = c.name
        if n in ("h1", "h2", "h3", "h4", "h5", "h6"):
            lvl = max(2, int(n[1]))           # keep article title as the only h1
            s = inline(c).strip()
            if s:
                parts.append("#" * lvl + " " + s)
        elif n == "p":
            s = inline(c).strip()
            if s:
                parts.append(s)
        elif n == "ul":
            s = list_md(c, False)
            if s:
                parts.append(s)
        elif n == "ol":
            s = list_md(c, True)
            if s:
                parts.append(s)
        elif n == "table":
            s = table_md(c)
            if s:
                parts.append(s)
        elif n == "blockquote":
            s = block(c).strip()
            if s:
                parts.append("\n".join("> " + ln for ln in s.splitlines()))
        elif n in ("hr",):
            parts.append("---")
        elif n in ("img",):
            s = img_md(c)
            if s:
                parts.append(s)
        elif n in ("iframe",):
            s = media_md(c).strip()
            if s:
                parts.append(s)
        elif n in ("figure", "figcaption"):
            parts.append(block(c).strip())
        elif n in ("div", "section", "span"):
            # containers: recurse, but if it's purely inline, render inline
            if c.find(["p", "div", "ul", "ol", "table", "h2", "h3", "h4",
                       "blockquote", "iframe", "figure"]):
                s = block(c).strip()
            else:
                s = inline(c).strip()
            if s:
                parts.append(s)
        else:
            s = block(c).strip()
            if s:
                parts.append(s)
    # join with blank lines, drop empties
    return "\n\n".join(p for p in (x.strip() for x in parts) if p)

# ---- body selection --------------------------------------------------------

def pick_body(soup):
    cands = soup.find_all(id=MODULE_RE)
    best, best_len = None, 0
    for el in cands:
        # skip the title module (it just wraps the h1)
        if el.find("h1"):
            continue
        L = len(el.get_text(" ", strip=True))
        if L > best_len:
            best, best_len = el, L
    return best if best_len >= 40 else None

# ---- main ------------------------------------------------------------------

def redact_secrets(md):
    """Neutralise Postman keys CC ships in its public docs so the artifact is
    safe to commit (GitHub push-protection flags these)."""
    md = re.sub(r"access_key=PMAT-[A-Za-z0-9]+", "access_key=REDACTED", md)
    md = re.sub(r"(getpostman\.com/collections/)[A-Za-z0-9]+", r"\1REDACTED", md)
    md = re.sub(r"(api\.postman\.com/collections/)[A-Za-z0-9-]+", r"\1REDACTED", md)
    return md

def clean_md(md):
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    return md.strip() + "\n"

def render_manual(articles, title, blurb):
    out = []
    out.append(f"# {title}\n")
    out.append(blurb + "\n")
    out.append("## Contents\n")
    last_grp = None
    for a in articles:
        if a["group"] != last_grp:
            out.append(f"\n**{a['group']}**\n")
            last_grp = a["group"]
        out.append(f"- [{a['title']}](#{a['slug']})")
    out.append("\n---\n")
    last_grp = None
    for a in articles:
        if a["group"] != last_grp:
            out.append(f"\n# {a['group']}\n")
            last_grp = a["group"]
        out.append(f'<a id="{a["slug"]}"></a>')
        out.append(f"## {a['title']}\n")
        out.append(f"_Source: {a['url']}_\n")
        out.append(a["md"])
        out.append("\n---\n")
    combined = "\n".join(out)
    return redact_secrets(re.sub(r"\n{3,}", "\n\n", combined))

def main():
    manifest = json.load(open(os.path.join(HERE, "manifest.json")))
    articles = []
    hubs = []
    for e in manifest:
        f = os.path.join(HTML_DIR, e["slug"] + ".html")
        if not os.path.exists(f):
            continue
        soup = BeautifulSoup(open(f, encoding="utf-8").read(), "html.parser")
        body = pick_body(soup)
        bc = e.get("breadcrumb", "")
        grp = re.sub(r"^CartonCloud Help\s*>?\s*", "", bc).strip() or "General"
        if body is None:
            hubs.append((grp, e["title"], e["slug"], e["url"]))
            continue
        md = clean_md(block(body))
        articles.append({"group": grp, "title": e["title"], "slug": e["slug"],
                         "url": e["url"], "breadcrumb": bc, "md": md,
                         "academy": "CartonCloud Academy" in bc})
        with open(os.path.join(MD_DIR, e["slug"] + ".md"), "w", encoding="utf-8") as fh:
            fh.write(f"# {e['title']}\n\n> Source: {e['url']}\n")
            if bc:
                fh.write(f"> Path: {bc}\n")
            fh.write("\n" + md)

    articles.sort(key=lambda a: (a["group"].lower(), a["title"].lower()))
    academy = [a for a in articles if a["academy"]]

    full_md = render_manual(
        articles,
        "CartonCloud Knowledge Base — Offline Manual (Full)",
        f"_Compiled from {BASE}/knowledge for offline reference — planning CC API "
        f"availability & workflow feasibility. {len(articles)} articles, full KB._")
    open(os.path.join(HERE, "CartonCloud-KB-Full-Manual.md"), "w",
         encoding="utf-8").write(full_md)

    acad_md = render_manual(
        academy,
        "CartonCloud Academy — Offline Manual",
        f"_The curated CartonCloud Academy curriculum from "
        f"{BASE}/knowledge/cartoncloud-academy. {len(academy)} articles._")
    open(os.path.join(HERE, "CartonCloud-Academy-Manual.md"), "w",
         encoding="utf-8").write(acad_md)

    # per-top-level-section files, so each comfortably fits a claude.ai upload
    sec_dir = os.path.join(HERE, "sections")
    os.makedirs(sec_dir, exist_ok=True)
    from collections import OrderedDict
    tops = OrderedDict()
    for a in articles:
        top = a["group"].split(" > ")[0]
        tops.setdefault(top, []).append(a)

    print(f"Articles: {len(articles)} (Academy curriculum: {len(academy)})  "
          f"|  Hub/nav pages skipped: {len(hubs)}")
    print(f"Full manual:    {len(full_md):,} chars (~{len(full_md)//4:,} tok)")
    print(f"Academy manual: {len(acad_md):,} chars (~{len(acad_md)//4:,} tok)")
    print("Per-section files (sections/):")
    for top, arts in sorted(tops.items(), key=lambda x: -len(x[1])):
        md = render_manual(
            arts, f"CartonCloud KB — {top}",
            f"_{len(arts)} articles from the '{top}' section of {BASE}/knowledge._")
        fn = re.sub(r"[^A-Za-z0-9]+", "-", top).strip("-")
        open(os.path.join(sec_dir, f"CC-KB-{fn}.md"), "w",
             encoding="utf-8").write(md)
        print(f"   {len(arts):3d} arts  ~{len(md)//4:>7,} tok  CC-KB-{fn}.md")

if __name__ == "__main__":
    main()
