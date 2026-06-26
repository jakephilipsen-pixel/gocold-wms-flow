#!/usr/bin/env python3
"""Convert the CartonCloud API Reference (a single Slate page) to markdown.

The doc is one static HTML file (api-docs.cartoncloud.com). Slate lays prose,
code samples (<pre class="highlight shell|json">) and parameter tables out in a
linear `.content` flow, so a single walk reproduces the reference faithfully.

Output: CartonCloud-API-Reference.md  (one file, TOC + all endpoints)
"""
import os, re, sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup, NavigableString, Tag

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "index.html")
OUT = os.path.join(HERE, "CartonCloud-API-Reference.md")
BASE = "https://api-docs.cartoncloud.com"
LANG = {"shell": "bash", "json": "json", "ruby": "ruby", "python": "python",
        "php": "php", "javascript": "javascript", "java": "java"}

def redact_secrets(md):
    """Neutralise Postman keys CC ships in its public docs so the artifact is
    safe to commit (GitHub push-protection flags PMAT- access tokens)."""
    md = re.sub(r"access_key=PMAT-[A-Za-z0-9]+", "access_key=REDACTED", md)
    md = re.sub(r"(getpostman\.com/collections/)[A-Za-z0-9]+", r"\1REDACTED", md)
    md = re.sub(r"(api\.postman\.com/collections/)[A-Za-z0-9-]+", r"\1REDACTED", md)
    return md

def esc(t):
    return t.replace(" ", " ")

def inline(node):
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            out.append(esc(str(c)))
        elif isinstance(c, Tag):
            n = c.name
            if n in ("strong", "b"):
                s = inline(c).strip(); out.append(f"**{s}**" if s else "")
            elif n in ("em", "i"):
                s = inline(c).strip(); out.append(f"*{s}*" if s else "")
            elif n == "code":
                out.append(f"`{c.get_text()}`")
            elif n == "br":
                out.append("  \n")
            elif n == "a":
                href = c.get("href", ""); txt = inline(c).strip() or href
                out.append(f"[{txt}]({urljoin(BASE, href)})" if href else txt)
            else:
                out.append(inline(c))
    return "".join(out)

def code_lang(pre):
    for cls in pre.get("class", []):
        if cls in LANG:
            return LANG[cls]
    return ""

def fenced(pre):
    lang = code_lang(pre)
    code = pre.get_text()
    code = code.replace(" ", " ").rstrip("\n")
    return f"```{lang}\n{code}\n```"

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
    out = ["| " + " | ".join(c.replace("|", "\\|") for c in rows[0]) + " |",
           "| " + " | ".join(["---"] * ncol) + " |"]
    for r in rows[1:]:
        out.append("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)

def list_md(node, ordered, depth=0):
    lines, i = [], 1
    for li in node.find_all("li", recursive=False):
        nested = li.find_all(["ul", "ol"], recursive=False)
        parts = []
        for c in li.children:
            if isinstance(c, Tag) and c.name in ("ul", "ol"):
                continue
            parts.append(inline(c) if isinstance(c, Tag) else esc(str(c)))
        text = " ".join(p.strip() for p in parts if p.strip())
        bullet = f"{i}." if ordered else "-"
        lines.append(f"{'  '*depth}{bullet} {text}".rstrip())
        for sub in nested:
            lines.append(list_md(sub, sub.name == "ol", depth + 1))
        i += 1
    return "\n".join(l for l in lines if l)

def block(node):
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
            lvl = min(6, int(n[1]) + 1)            # demote: doc keeps one top #
            s = inline(c).strip()
            if s:
                anchor = c.get("id")
                parts.append("#" * lvl + " " + s +
                             (f' <a id="{anchor}"></a>' if anchor else ""))
        elif n == "p":
            s = inline(c).strip()
            if s:
                parts.append(s)
        elif n == "pre":
            parts.append(fenced(c))
        elif n == "ul":
            s = list_md(c, False);  parts.append(s) if s else None
        elif n == "ol":
            s = list_md(c, True);   parts.append(s) if s else None
        elif n == "table":
            s = table_md(c);        parts.append(s) if s else None
        elif n == "blockquote":
            s = inline(c).strip()
            if s:
                parts.append("> " + s.replace("\n", "\n> "))
        elif n in ("hr",):
            parts.append("---")
        else:   # div.highlight wrappers, sections, spans -> recurse
            s = block(c).strip()
            if s:
                parts.append(s)
    return "\n\n".join(p for p in (x.strip() for x in parts if x) if p)

def main():
    soup = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")
    content = soup.select_one(".content") or soup.body
    title = (soup.find("title").get_text(strip=True)
             if soup.find("title") else "CartonCloud API Reference")

    # TOC from h1/h2 (Slate section + endpoint headings), using Slate ids
    toc = []
    for h in content.find_all(["h1", "h2"]):
        txt = h.get_text(" ", strip=True)
        hid = h.get("id")
        if not txt or not hid:
            continue
        indent = "" if h.name == "h1" else "  "
        toc.append(f"{indent}- [{txt}](#{hid})")

    body = block(content)
    body = re.sub(r"\n{3,}", "\n\n", body)

    md = [f"# {title}\n",
          f"_Offline copy of {BASE}/ — the complete CartonCloud REST API "
          "reference (auth, endpoints, request/response schemas, code samples). "
          "Captured for API-feasibility planning._\n",
          "## Contents\n", "\n".join(toc), "\n---\n", body, ""]
    out = "\n".join(md)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = redact_secrets(out)
    open(OUT, "w", encoding="utf-8").write(out)

    print(f"Wrote {OUT}")
    print(f"  {len(out):,} chars (~{len(out)//4:,} tokens)")
    print(f"  TOC entries: {len(toc)}  |  code blocks: {body.count('```')//2}  "
          f"|  tables: {body.count('| --- |')}")

if __name__ == "__main__":
    main()
