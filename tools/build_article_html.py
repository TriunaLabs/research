"""Render an article's README.md to a styled standalone index.html.

Interim publisher until Fold Article Studio takes over this job.
Usage: python tools/build_article_html.py articles/ai-native-ssd
"""
import re
import sys
import os
import markdown

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="author" content="{author}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{og_image}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Article","headline":"{title}",
"author":{{"@type":"Person","name":"{author}"}},
"publisher":{{"@type":"Organization","name":"Triuna Labs","url":"https://triunalabs.com"}},
"datePublished":"{date}","image":"{og_image}","url":"{canonical}"}}
</script>
<style>
:root {{
  --surface: #fcfcfb; --ink: #1a1a19; --ink-2: #52514e; --muted: #898781;
  --hairline: #e1e0d9; --accent: #2a78d6; --quote-bg: #f5f4f1;
  --callout-bg: rgba(42, 120, 214, 0.07);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --surface: #1a1a19; --ink: #f2f1ec; --ink-2: #c3c2b7; --muted: #898781;
    --hairline: #383835; --accent: #5598e7; --quote-bg: #232322;
    --callout-bg: rgba(85, 152, 231, 0.12);
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--surface); color: var(--ink);
  font: 18px/1.7 "Segoe UI", system-ui, -apple-system, sans-serif;
}}
.wrap {{ max-width: 44rem; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
header.site {{ border-bottom: 1px solid var(--hairline); }}
header.site .wrap {{ padding: 1rem 1.25rem; display: flex; justify-content: space-between; align-items: baseline; }}
header.site a {{ color: var(--ink); text-decoration: none; font-weight: 600; }}
header.site .links a {{ color: var(--ink-2); font-weight: 400; font-size: .9rem; margin-left: 1rem; }}
.byline {{ color: var(--ink-2); font-size: .95rem; margin: .25rem 0 0; }}
h1 {{ font-size: 2.1rem; line-height: 1.25; margin: 1.6rem 0 .4rem; letter-spacing: -.01em; }}
h2 {{ font-size: 1.45rem; line-height: 1.3; margin: 2.6rem 0 .8rem; letter-spacing: -.01em; }}
h3 {{ font-size: 1.12rem; margin: 1.8rem 0 .6rem; }}
p, li {{ color: var(--ink); }}
a {{ color: var(--accent); }}
hr {{ border: 0; border-top: 1px solid var(--hairline); margin: 2.5rem 0; }}
blockquote {{
  margin: 1.4rem 0; padding: .9rem 1.2rem; background: var(--quote-bg);
  border-left: 4px solid var(--accent); border-radius: 0 8px 8px 0;
}}
blockquote p {{ margin: 0; }}
.callout {{
  margin: 1.6rem 0; padding: 1rem 1.3rem; border-radius: 10px;
  background: var(--callout-bg); border-left: 4px solid var(--accent);
  font-size: 1.05rem;
}}
.callout p {{ margin: 0; }}
.pullquote {{
  margin: 2.6rem auto; max-width: 36rem; text-align: center;
  font-size: 1.45rem; line-height: 1.45; font-style: italic; color: var(--ink);
}}
.pullquote::before, .pullquote::after {{
  content: ""; display: block; width: 4rem; height: 2px;
  background: var(--accent); margin: 1.1rem auto; opacity: .55;
}}
.thesis {{
  margin: 2rem 0; padding: 1.4rem 1.6rem; border: 2px solid var(--accent);
  border-radius: 14px; background: var(--callout-bg);
  font-size: 1.12rem; line-height: 1.65;
}}
.thesis p {{ margin: 0; }}
img {{ max-width: 100%; height: auto; border-radius: 10px; border: 1px solid var(--hairline); margin: 1.2rem 0; }}
.tablewrap {{ overflow-x: auto; margin: 1.4rem 0; }}
table {{ border-collapse: collapse; font-size: .92rem; min-width: 100%; }}
th, td {{ text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--hairline); vertical-align: top; }}
th {{ color: var(--ink-2); font-weight: 600; white-space: nowrap; }}
code {{ background: var(--quote-bg); padding: .1em .35em; border-radius: 5px; font-size: .88em; }}
pre code {{ display: block; padding: 1rem; overflow-x: auto; }}
footer.site {{ border-top: 1px solid var(--hairline); margin-top: 3rem; }}
footer.site .wrap {{ padding: 1.5rem 1.25rem; color: var(--muted); font-size: .88rem; }}
footer.site a {{ color: var(--ink-2); }}
</style>
</head>
<body>
<header class="site"><div class="wrap">
  <a href="https://triunalabs.com">Triuna Labs</a>
  <span class="links">
    <a href="https://github.com/TriunaLabs/research">Research repo</a>
    <a href="{repo_dir}">This article's code &amp; data</a>
  </span>
</div></header>
<main class="wrap">
<p class="byline">{author} &#183; Triuna Labs Research &#183; {date_human}</p>
{body}
</main>
<footer class="site"><div class="wrap">
  Prose licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> &#183;
  code <a href="https://github.com/TriunaLabs/research/blob/main/LICENSE">MIT</a> &#183;
  reproduce the benchmark: <a href="{repo_dir}/benchmark">scripts &amp; raw results</a> &#183;
  built with a <a href="https://github.com/TriunaLabs/research/blob/main/tools/build_article_html.py">40-line generator</a> (Fold Article Studio pending)
</div></footer>
</body>
</html>
"""

META = {
    "articles/ai-native-ssd": {
        "description": ("An LLM request is many kinds of work, and only some of it needs a GPU. "
                        "Why the winning AI architecture routes each operation to the cheapest tier "
                        "that can perform it - with a laptop-reproducible 102 GB data-movement benchmark."),
        "author": "Paul Woll",
        "date": "2026-08-18",
        "date_human": "August 18, 2026",
    },
}


def build(article_dir: str) -> str:
    key = article_dir.replace("\\", "/").rstrip("/")
    meta = META[key]
    src = os.path.join(article_dir, "README.md")
    with open(src, encoding="utf-8") as f:
        md = f.read()

    title_match = re.search(r"^#\s+(?:\S+\s)?(.+)$", md, re.M)   # strip leading emoji
    title = title_match.group(1).strip()

    # the template renders its own styled byline; drop the markdown one
    md = re.sub(r"^\*By Paul Woll.*\*$\n?", "", md, flags=re.M)

    body = markdown.markdown(md, extensions=["tables", "fenced_code"])
    body = re.sub(r"<table>", '<div class="tablewrap"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)

    # Typographic upgrades, keyed off the article's own quote conventions:
    #  - italic-only one-liner blockquotes -> large-type editorial pull-quotes
    #  - the thesis blockquote -> featured box
    #  - remaining (bold-claim) blockquotes -> tinted callout cards
    body = re.sub(
        r"<blockquote>\s*<p><em>(.*?)</em></p>\s*</blockquote>",
        r'<div class="pullquote">\1</div>', body, flags=re.S)
    body = re.sub(
        r"<blockquote>(\s*<p><strong>An LLM request is not one monolithic.*?)</blockquote>",
        r'<div class="thesis">\1</div>', body, flags=re.S)
    body = body.replace("<blockquote>", '<div class="callout">')
    body = body.replace("</blockquote>", "</div>")

    slug = key.split("/")[-1]
    canonical = f"https://research.triunalabs.com/articles/{slug}/"
    html = TEMPLATE.format(
        title=title, description=meta["description"], author=meta["author"],
        date=meta["date"], date_human=meta["date_human"], canonical=canonical,
        og_image=f"{canonical}images/05-same-problem.png",
        repo_dir=f"https://github.com/TriunaLabs/research/tree/main/{key}",
        body=body,
    )
    out = os.path.join(article_dir, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


if __name__ == "__main__":
    print("wrote", build(sys.argv[1] if len(sys.argv) > 1 else "articles/ai-native-ssd"))
