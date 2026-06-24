import posixpath
import re
import urllib.parse
from bs4 import BeautifulSoup

# Detects SPA/meta-refresh stubs:  <meta http-equiv="refresh" content="0;URL='...'">
_META_REFRESH_RE = re.compile(
    r'<meta[^>]+http-equiv\s*=\s*["\']?refresh["\']?[^>]*?content\s*=\s*["\']?([^"\'>]*)',
    re.IGNORECASE,
)


class TransformerService:
    """
    Transforms raw ZIM HTML into a modern, website-like reader page.

    Features added on top of the ZIM's own markup:
      • Sticky right-rail Table of Contents with active-section highlighting
      • Reading progress bar
      • Article header card (breadcrumb, reading-time, archive badge)
      • Wikipedia-style link preview cards on hover
      • Improved lightbox: prev/next arrow keys, image captions, counter
      • postMessage protocol for parent-window navigation + reading-mode prefs
      • CSS variables driven by reader preferences (font-size, column width, theme)
    """

    # ------------------------------------------------------------------
    @staticmethod
    def resolve_zim_path(current_page_path: str, relative_path: str) -> str:
        """Resolve a relative ZIM asset/link path against the current page's absolute path."""
        if relative_path.startswith(("http://", "https://", "mailto:", "data:", "#")):
            return relative_path

        unquoted = urllib.parse.unquote(relative_path)
        path_only = unquoted.split("?")[0].split("#")[0]
        hash_suffix = ""
        if "#" in unquoted:
            hash_suffix = "#" + unquoted.split("#")[1]

        parent_dir = posixpath.dirname(current_page_path)
        resolved = posixpath.normpath(posixpath.join(parent_dir, path_only))
        resolved = resolved.replace("\\", "/")

        while resolved.startswith("../"):
            resolved = resolved[3:]

        return resolved + hash_suffix

    # ------------------------------------------------------------------
    @classmethod
    def transform_html(
        cls,
        html_content: bytes,
        archive_id: str,
        current_page_path: str,
        theme: str = "dark",
        backend_url: str = "",
        archive_title: str = "",
    ) -> str:
        """Modernize ZIM HTML — preserves ZIM CSS, adds Kiwi reader shell."""
        # Decode the raw HTML once so we can do quick sniffing before BS parses.
        try:
            html_text = html_content.decode("utf-8", errors="ignore")
        except Exception:
            html_text = html_content.decode("latin1", errors="ignore")

        # ── Detect SPA-style meta-refresh stub ─────────────────────────
        # These tiny pages only bounce the browser to a JS-driven index.html
        # whose dynamic content can't render through our iframe proxy.
        # Render a friendly explainer instead of a confusing blank page.
        meta_refresh = _META_REFRESH_RE.search(html_text)
        if meta_refresh and len(html_text) < 2000:
            return cls._render_empty_state(
                title="This article uses dynamic loading",
                reason=(
                    "The ZIM file stored this article as a redirect shell that "
                    "expects the original site's JavaScript app to load the body. "
                    "That app can't run through Kiwi's offline reader."
                ),
                hint="Try a different article from the same archive — most are fine.",
                archive_title=archive_title,
                theme=theme,
            )

        try:
            soup = BeautifulSoup(html_text, "html.parser")
        except Exception:
            return html_text

        # --- Rewrite <a> internal links ---
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith(("http://", "https://", "mailto:", "data:", "javascript:", "#")):
                continue
            resolved = cls.resolve_zim_path(current_page_path, href)
            hash_part = ""
            if "#" in resolved:
                parts = resolved.split("#", 1)
                resolved, hash_part = parts[0], "#" + parts[1]
            a_tag["href"] = (
                f"{backend_url}/api/articles/{archive_id}/view/{resolved}{hash_part}"
            )
            # Mark internal Kiwi links so the JS can recognise them reliably
            a_tag["data-kiwi-internal"] = "1"

        # --- Rewrite <img src> ---
        for img_tag in soup.find_all("img", src=True):
            src = img_tag["src"]
            if not src.startswith(("http://", "https://", "data:")):
                resolved = cls.resolve_zim_path(current_page_path, src)
                img_tag["src"] = f"{backend_url}/api/articles/{archive_id}/media/{resolved}"

        # --- Rewrite <source src> (video / audio) ---
        for src_tag in soup.find_all("source", src=True):
            src = src_tag["src"]
            if not src.startswith(("http://", "https://", "data:")):
                resolved = cls.resolve_zim_path(current_page_path, src)
                src_tag["src"] = f"{backend_url}/api/articles/{archive_id}/media/{resolved}"

        # --- Collect ZIM <head> stylesheets & inline <style> blocks ---
        zim_head_html = []
        head = soup.find("head")
        if head:
            for tag in head.find_all(["link", "style"]):
                rel = tag.get("rel", []) if tag.name == "link" else []
                if tag.name == "link" and "stylesheet" in rel:
                    href = tag.get("href", "")
                    if href.startswith(("http://", "https://", "//")):
                        continue
                    if href and not href.startswith("data:"):
                        resolved = cls.resolve_zim_path(current_page_path, href)
                        zim_head_html.append(
                            f'<link rel="stylesheet" type="text/css" '
                            f'href="{backend_url}/api/articles/{archive_id}/media/{resolved}">'
                        )
                elif tag.name == "style":
                    zim_head_html.append(str(tag))

        # --- Extract title ---
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Article"

        # --- Extract body content (inline styles preserved) ---
        body = soup.find("body")
        if body:
            body_content = "".join(str(child) for child in body.children)
        else:
            body_content = str(soup)

        # --- Estimate reading time (200 words/min average) ---
        plain_text = body.get_text(" ", strip=True) if body else ""
        word_count = len(plain_text.split())
        reading_minutes = max(1, round(word_count / 200))

        # ── Catch articles with no visible content ─────────────────────
        # Some ZIM entries are <body></body> or <body><script></script></body>
        # — title appears but body is effectively empty. Show a useful state
        # instead of a confusing blank page.
        # BUT: API references and DevDocs pages are often 90% code and 10%
        # prose. `body.get_text()` collapses code blocks into short pieces,
        # so word_count can be < 8 even when there's plenty of useful code.
        # Count <pre>/<code> characters too as an escape hatch.
        if word_count < 8 and body is not None:
            code_chars = sum(
                len(el.get_text("", strip=True))
                for el in body.find_all(["pre", "code"])
            )
            if code_chars >= 200:
                word_count = max(word_count, code_chars // 5)  # treat as enough
        if word_count < 8:
            return cls._render_empty_state(
                title=title,
                reason=(
                    "The ZIM file doesn't contain text content for this entry — "
                    "it may be an image-only page, a navigation stub, or its "
                    "content was stored in a format Kiwi can't render."
                ),
                hint="Try a different article from this archive.",
                archive_title=archive_title,
                theme=theme,
            )

        # --- Build output ---
        theme_class = (
            "kiwi-dark"
            if theme == "dark"
            else "kiwi-sepia"
            if theme == "sepia"
            else "kiwi-light"
        )
        kiwi_css = cls._kiwi_css()
        kiwi_js = cls._kiwi_js(archive_id, current_page_path, backend_url)

        # Article header card injected at the top of the content
        archive_badge = (
            f'<span class="kiwi-archive-badge">{archive_title}</span>'
            if archive_title
            else ""
        )
        header_card = f"""
        <div class="kiwi-article-header">
            <div class="kiwi-breadcrumb">
                {archive_badge}
                <span class="kiwi-breadcrumb-sep">›</span>
                <span class="kiwi-breadcrumb-current">{title}</span>
            </div>
            <h1 class="kiwi-title">{title}</h1>
            <div class="kiwi-meta">
                <span class="kiwi-meta-item">📖 {reading_minutes} min read</span>
                <span class="kiwi-meta-item">{word_count:,} words</span>
            </div>
        </div>
        """

        return f"""<!DOCTYPE html>
<html lang="en" class="{theme_class}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {"".join(zim_head_html)}
    <style>{kiwi_css}</style>
</head>
<body>
    <div class="kiwi-progress" id="kiwi-progress"></div>
    <div class="kiwi-toc" id="kiwi-toc" aria-hidden="true">
        <div class="kiwi-toc-header">Contents</div>
        <ul class="kiwi-toc-list" id="kiwi-toc-list"></ul>
    </div>
    <div class="kiwi-wrapper">
        {header_card}
        <div class="kiwi-content">
            {body_content}
        </div>
    </div>

    <!-- Lightbox -->
    <div class="kiwi-lightbox" id="kiwi-lightbox">
        <button class="kiwi-lb-close" aria-label="Close">×</button>
        <button class="kiwi-lb-prev" aria-label="Previous">‹</button>
        <button class="kiwi-lb-next" aria-label="Next">›</button>
        <div class="kiwi-lb-counter" id="kiwi-lb-counter"></div>
        <img class="kiwi-lb-img" id="kiwi-lb-img" alt="">
        <div class="kiwi-lb-caption" id="kiwi-lb-caption"></div>
    </div>

    <!-- Link preview popover (Wikipedia-style) -->
    <div class="kiwi-preview" id="kiwi-preview"></div>

    <button class="kiwi-scroll-top" id="kiwi-scroll-top" aria-label="Scroll to top">↑</button>

    <script>{kiwi_js}</script>
</body>
</html>"""

    # ------------------------------------------------------------------
    @classmethod
    def _render_empty_state(
        cls,
        title: str,
        reason: str,
        hint: str,
        archive_title: str = "",
        theme: str = "dark",
        suggestions: list | None = None,
    ) -> str:
        """
        Return a clean, branded "this article has no readable content" page.
        Used when we detect a meta-refresh SPA shell or an article whose body
        is empty / contains no extractable text.
        """
        theme_class = (
            "kiwi-dark" if theme == "dark"
            else "kiwi-sepia" if theme == "sepia"
            else "kiwi-light"
        )
        # Reuse the reader CSS so the empty state matches the rest of the app.
        css = cls._kiwi_css()
        badge = f'<span class="kiwi-archive-badge">{archive_title}</span>' if archive_title else ""
        # Optional "Try one of these instead" grid
        sug_html = ""
        if suggestions:
            items = "".join(
                f'<a class="kiwi-sug-card" href="{s.get("href", "#")}"><div class="kiwi-sug-title">{s.get("title", "")}</div></a>'
                for s in suggestions
            )
            sug_html = (
                '<div class="kiwi-sug-label">Try one of these instead</div>'
                f'<div class="kiwi-sug-grid">{items}</div>'
            )
        return f"""<!DOCTYPE html>
<html lang="en" class="{theme_class}">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>{css}</style>
    <style>
        .kiwi-empty-card {{
            margin: 80px auto;
            max-width: 560px;
            padding: 36px 32px;
            background: var(--kiwi-bg-elevated);
            border: 1px solid var(--kiwi-border);
            border-radius: 16px;
            box-shadow: var(--kiwi-shadow);
            text-align: center;
        }}
        .kiwi-empty-icon {{
            font-size: 48px;
            line-height: 1;
            margin-bottom: 16px;
            opacity: .55;
        }}
        .kiwi-empty-title {{
            font-family: var(--kiwi-sans);
            font-size: 1.5em;
            font-weight: 700;
            color: var(--kiwi-text);
            margin: 0 0 12px;
            letter-spacing: -0.02em;
        }}
        .kiwi-empty-reason {{
            font-family: var(--kiwi-sans);
            color: var(--kiwi-text-secondary);
            font-size: 0.95em;
            line-height: 1.55;
            margin: 0 0 16px;
        }}
        .kiwi-empty-hint {{
            font-family: var(--kiwi-sans);
            font-size: 0.85em;
            color: var(--kiwi-muted);
            font-style: italic;
        }}
        .kiwi-sug-label {{
            margin-top: 28px;
            margin-bottom: 12px;
            font-family: var(--kiwi-sans);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--kiwi-muted);
            text-align: left;
        }}
        .kiwi-sug-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
            text-align: left;
        }}
        .kiwi-sug-card {{
            display: block;
            padding: 12px 14px;
            background: var(--kiwi-bg);
            border: 1px solid var(--kiwi-border);
            border-radius: 8px;
            text-decoration: none;
            transition: border-color .12s, background .12s;
        }}
        .kiwi-sug-card:hover {{
            border-color: var(--kiwi-accent);
            background: var(--kiwi-card-bg);
        }}
        .kiwi-sug-title {{
            font-family: var(--kiwi-sans);
            font-size: 0.9em;
            color: var(--kiwi-text);
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="kiwi-wrapper">
        <div class="kiwi-article-header">
            <div class="kiwi-breadcrumb">
                {badge}<span class="kiwi-breadcrumb-sep">›</span>
                <span class="kiwi-breadcrumb-current">{title}</span>
            </div>
            <h1 class="kiwi-title">{title}</h1>
        </div>
        <div class="kiwi-empty-card">
            <div class="kiwi-empty-icon">📭</div>
            <div class="kiwi-empty-title">No content to display</div>
            <p class="kiwi-empty-reason">{reason}</p>
            <p class="kiwi-empty-hint">{hint}</p>
            {sug_html}
        </div>
    </div>
</body>
</html>"""

    # ------------------------------------------------------------------
    @staticmethod
    def _kiwi_css() -> str:
        """
        Reader stylesheet — modeled on Medium, Substack, and NYT article pages.

        Typography:
          • Body: serif (Charter/Georgia) for long-form readability
          • Headings: Inter (geometric sans) for hierarchy
          • Code: JetBrains Mono / SF Mono
          • Base: 18px / 1.75 line-height — generous, magazine-feel

        Layout:
          • 720px centered column (Medium/Substack standard)
          • Drop cap on first paragraph
          • Pull-quote blockquotes
          • Refined tables, code, lists, images
          • Sticky TOC + gradient progress bar

        ZIM's own CSS loads BEFORE this so wiki-specific elements still work;
        these rules layer modern presentation on top.
        """
        return """
:root {
    /* Typography */
    --kiwi-font-size: 18px;
    --kiwi-line-height: 1.75;
    --kiwi-column-width: 720px;
    --kiwi-serif: 'Charter', 'Iowan Old Style', 'Source Serif Pro', 'Georgia', 'Cambria', serif;
    --kiwi-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    --kiwi-mono: 'JetBrains Mono', 'SF Mono', 'Cascadia Code', 'Consolas', monospace;

    /* Light theme */
    --kiwi-bg: #ffffff;
    --kiwi-bg-elevated: #fafaf9;
    --kiwi-text: #1a1a1a;
    --kiwi-text-secondary: #404040;
    --kiwi-muted: #737373;
    --kiwi-border: #e7e5e1;
    --kiwi-border-strong: #d6d3cd;
    --kiwi-accent: #2563eb;
    --kiwi-accent-soft: #dbeafe;
    --kiwi-card-bg: #f7f5f0;
    --kiwi-selection: #fef3c7;
    --kiwi-shadow: 0 1px 3px rgba(0,0,0,.06);
    --kiwi-shadow-lg: 0 20px 48px rgba(0,0,0,.12);
}
html.kiwi-dark {
    --kiwi-bg: #0d1117;
    --kiwi-bg-elevated: #161b22;
    --kiwi-text: #e6edf3;
    --kiwi-text-secondary: #c9d1d9;
    --kiwi-muted: #7d8590;
    --kiwi-border: #21262d;
    --kiwi-border-strong: #30363d;
    --kiwi-accent: #58a6ff;
    --kiwi-accent-soft: #1f3a5f;
    --kiwi-card-bg: #161b22;
    --kiwi-selection: #3b3217;
    --kiwi-shadow: 0 1px 3px rgba(0,0,0,.4);
    --kiwi-shadow-lg: 0 20px 48px rgba(0,0,0,.5);
}
html.kiwi-sepia {
    --kiwi-bg: #faf4e8;
    --kiwi-bg-elevated: #f4ecd8;
    --kiwi-text: #3a2e22;
    --kiwi-text-secondary: #5b4636;
    --kiwi-muted: #856e54;
    --kiwi-border: #ddd0b0;
    --kiwi-border-strong: #c8b890;
    --kiwi-accent: #a0521f;
    --kiwi-accent-soft: #f0d8a0;
    --kiwi-card-bg: #f4ecd8;
    --kiwi-selection: #f0d8a0;
    --kiwi-shadow: 0 1px 3px rgba(91,70,54,.1);
    --kiwi-shadow-lg: 0 20px 48px rgba(91,70,54,.15);
}

html, body {
    margin: 0; padding: 0;
    scroll-behavior: smooth;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    font-family: var(--kiwi-serif);
    font-size: var(--kiwi-font-size);
    line-height: var(--kiwi-line-height);
    background-color: var(--kiwi-bg) !important;
    color: var(--kiwi-text) !important;
    overflow-x: hidden;
}

::selection { background: var(--kiwi-selection); color: var(--kiwi-text); }

/* ── Progress bar (gradient + glow) ────────────────────────── */
.kiwi-progress {
    position: fixed; top: 0; left: 0;
    height: 3px; width: 0%;
    background: linear-gradient(90deg, var(--kiwi-accent), #06b6d4);
    z-index: 9998;
    transition: width .15s ease-out;
    box-shadow: 0 0 12px var(--kiwi-accent);
}

/* ── Wrapper (centered narrow column, Medium-style) ───────── */
.kiwi-wrapper {
    max-width: var(--kiwi-column-width);
    margin: 0 auto;
    padding: 56px 32px 96px;
    transition: max-width .25s ease;
}
@media (max-width: 700px) {
    .kiwi-wrapper { padding: 28px 18px 60px; }
}

/* ── Article header (hero) ─────────────────────────────────── */
.kiwi-article-header {
    margin-bottom: 48px;
    padding-bottom: 32px;
    border-bottom: 1px solid var(--kiwi-border);
}
.kiwi-breadcrumb {
    font-family: var(--kiwi-sans);
    font-size: 12px;
    color: var(--kiwi-muted);
    margin-bottom: 18px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    font-weight: 500;
}
.kiwi-archive-badge {
    color: var(--kiwi-accent);
    font-weight: 700;
    letter-spacing: 0.03em;
}
.kiwi-breadcrumb-sep { color: var(--kiwi-border-strong); }
.kiwi-breadcrumb-current {
    color: var(--kiwi-text-secondary);
    font-weight: 500;
    text-transform: none;
    letter-spacing: 0;
}
.kiwi-title {
    font-family: var(--kiwi-sans);
    font-size: 2.75em;
    font-weight: 800;
    letter-spacing: -0.025em;
    line-height: 1.1;
    margin: 0 0 22px;
    color: var(--kiwi-text) !important;
}
@media (max-width: 700px) {
    .kiwi-title { font-size: 2.1em; }
}
.kiwi-meta {
    display: flex;
    gap: 22px;
    font-family: var(--kiwi-sans);
    font-size: 14px;
    color: var(--kiwi-muted);
}
.kiwi-meta-item { display: inline-flex; align-items: center; gap: 6px; }

/* Hide ZIM's own <h1> at the top — we render our own .kiwi-title */
.kiwi-content > h1:first-child { display: none; }
.kiwi-content > h1:first-of-type + p:first-of-type {
    /* If body starts with H1 (we hide) then P (becomes first), make it lead text */
    font-size: 1.18em;
    color: var(--kiwi-text);
    line-height: 1.55;
}

/* ── Body typography ───────────────────────────────────────── */
.kiwi-content {
    color: var(--kiwi-text);
}
.kiwi-content p {
    margin: 0 0 1.4em;
}

/* Drop cap on the very first paragraph of the body — magazine feel */
.kiwi-content > p:first-of-type::first-letter,
.kiwi-content > div > p:first-of-type::first-letter {
    font-family: var(--kiwi-sans);
    font-size: 4.4em;
    font-weight: 800;
    float: left;
    line-height: 0.82;
    margin: 6px 12px -2px 0;
    color: var(--kiwi-accent);
    letter-spacing: -0.05em;
}

/* Headings: sans-serif, tracked tight, balanced spacing */
.kiwi-content h1,
.kiwi-content h2,
.kiwi-content h3,
.kiwi-content h4,
.kiwi-content h5,
.kiwi-content h6 {
    font-family: var(--kiwi-sans);
    color: var(--kiwi-text);
    margin-top: 2em;
    margin-bottom: 0.55em;
    letter-spacing: -0.02em;
    line-height: 1.25;
    font-weight: 700;
    scroll-margin-top: 24px;
}
.kiwi-content h2 {
    font-size: 1.75em;
    padding-bottom: 0.35em;
    border-bottom: 1px solid var(--kiwi-border);
}
.kiwi-content h3 { font-size: 1.35em; }
.kiwi-content h4 { font-size: 1.12em; color: var(--kiwi-text-secondary); }
.kiwi-content h5 { font-size: 1em; text-transform: uppercase; letter-spacing: 0.06em; color: var(--kiwi-muted); }

/* Links with animated underline */
.kiwi-content a {
    color: var(--kiwi-accent);
    text-decoration: none;
}
.kiwi-content a[data-kiwi-internal] {
    background-image: linear-gradient(currentColor, currentColor);
    background-size: 0% 1px;
    background-position: 0 100%;
    background-repeat: no-repeat;
    transition: background-size .25s ease;
    padding-bottom: 1px;
}
.kiwi-content a[data-kiwi-internal]:hover {
    background-size: 100% 1px;
}

/* Lists */
.kiwi-content ul, .kiwi-content ol {
    padding-left: 1.6em;
    margin: 0 0 1.4em;
}
.kiwi-content li { margin-bottom: 0.45em; }
.kiwi-content li > ul, .kiwi-content li > ol { margin: 0.45em 0 0; }
.kiwi-content ul { list-style: disc; }
.kiwi-content ul ul { list-style: circle; }

/* Blockquote — pull-quote style */
.kiwi-content blockquote {
    margin: 32px 0;
    padding: 4px 28px;
    border-left: 3px solid var(--kiwi-accent);
    font-style: italic;
    font-size: 1.12em;
    color: var(--kiwi-text-secondary);
    line-height: 1.6;
}
.kiwi-content blockquote p { margin-bottom: 12px; }
.kiwi-content blockquote p:last-child { margin-bottom: 0; }

/* Code */
.kiwi-content pre {
    font-family: var(--kiwi-mono);
    background: var(--kiwi-card-bg);
    border: 1px solid var(--kiwi-border);
    border-radius: 10px;
    padding: 18px 22px;
    overflow-x: auto;
    font-size: 0.88em;
    line-height: 1.6;
    margin: 28px 0;
    -webkit-font-smoothing: auto;
}
.kiwi-content code { font-family: var(--kiwi-mono); }
.kiwi-content :not(pre) > code {
    background: var(--kiwi-card-bg);
    border: 1px solid var(--kiwi-border);
    padding: 2px 7px;
    border-radius: 5px;
    font-size: 0.88em;
    color: var(--kiwi-text);
}

/* Tables */
.kiwi-content table {
    border-collapse: collapse;
    width: 100%;
    margin: 30px 0;
    font-family: var(--kiwi-sans);
    font-size: 0.92em;
    border: 1px solid var(--kiwi-border);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: var(--kiwi-shadow);
}
.kiwi-content th {
    background: var(--kiwi-card-bg);
    color: var(--kiwi-text);
    text-align: left;
    padding: 14px 16px;
    font-weight: 600;
    border-bottom: 1px solid var(--kiwi-border);
    font-size: 0.9em;
    letter-spacing: 0.01em;
}
.kiwi-content td {
    padding: 14px 16px;
    border-bottom: 1px solid var(--kiwi-border);
    color: var(--kiwi-text);
}
.kiwi-content tr:last-child td { border-bottom: none; }
.kiwi-content tr:hover td { background: var(--kiwi-bg-elevated); }

/* Images */
.kiwi-content img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    box-shadow: var(--kiwi-shadow);
    margin: 22px 0;
    cursor: zoom-in;
    transition: transform .2s ease, box-shadow .2s ease;
}
.kiwi-content img:hover {
    transform: scale(1.005);
    box-shadow: 0 4px 16px rgba(0,0,0,.1);
}
.kiwi-content figure {
    margin: 36px 0;
    text-align: center;
}
.kiwi-content figure img { margin: 0 auto; }
.kiwi-content figcaption {
    font-family: var(--kiwi-sans);
    font-size: 13px;
    color: var(--kiwi-muted);
    margin-top: 10px;
    font-style: italic;
    line-height: 1.5;
}

/* HR — subtle, themed */
.kiwi-content hr {
    border: none;
    height: 1px;
    background: var(--kiwi-border);
    margin: 48px auto;
    max-width: 240px;
}

/* Definition lists */
.kiwi-content dt { font-weight: 700; margin-top: 12px; }
.kiwi-content dd { margin-left: 24px; margin-bottom: 12px; color: var(--kiwi-text-secondary); }

/* Tighten ZIM-rendered headings inside cards */
.kiwi-content .infobox, .kiwi-content table.infobox {
    font-family: var(--kiwi-sans);
    font-size: 0.88em;
    border-radius: 8px;
    overflow: hidden;
}

/* ── Sticky right-rail TOC (refined) ───────────────────────── */
.kiwi-toc {
    position: fixed;
    right: 24px;
    top: 24px;
    width: 240px;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
    padding: 20px;
    background: var(--kiwi-bg-elevated);
    border: 1px solid var(--kiwi-border);
    border-radius: 14px;
    font-family: var(--kiwi-sans);
    font-size: 13px;
    line-height: 1.5;
    z-index: 50;
    box-shadow: var(--kiwi-shadow);
}
.kiwi-toc[aria-hidden="true"] { display: none; }
@media (max-width: 1280px) { .kiwi-toc { display: none !important; } }
.kiwi-toc-header {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--kiwi-muted);
    margin-bottom: 14px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--kiwi-border);
}
.kiwi-toc-list { list-style: none; margin: 0; padding: 0; }
.kiwi-toc-item {
    display: block;
    padding: 6px 0 6px 14px;
    margin: 1px 0;
    color: var(--kiwi-muted);
    text-decoration: none;
    border-left: 2px solid transparent;
    cursor: pointer;
    line-height: 1.4;
    transition: color .15s ease, border-color .15s ease, padding .2s ease;
}
.kiwi-toc-item:hover { color: var(--kiwi-text); padding-left: 18px; }
.kiwi-toc-item.kiwi-toc-h3 { padding-left: 28px; font-size: 12px; opacity: 0.85; }
.kiwi-toc-item.kiwi-toc-h3:hover { padding-left: 32px; }
.kiwi-toc-item.kiwi-toc-active {
    color: var(--kiwi-accent) !important;
    border-left-color: var(--kiwi-accent);
    font-weight: 600;
}

/* ── Dark-mode overrides for common ZIM/Wikipedia patterns ─── */
html.kiwi-dark table, html.kiwi-dark .wikitable { border-color: var(--kiwi-border) !important; }
html.kiwi-dark th, html.kiwi-dark .wikitable th {
    background-color: var(--kiwi-card-bg) !important;
    color: var(--kiwi-text) !important;
    border-color: var(--kiwi-border) !important;
}
html.kiwi-dark td, html.kiwi-dark .wikitable td {
    color: var(--kiwi-text) !important;
    border-color: var(--kiwi-border) !important;
}
html.kiwi-dark tr:nth-child(even), html.kiwi-dark .wikitable tr:nth-child(even) {
    background-color: var(--kiwi-card-bg) !important;
}
html.kiwi-dark .infobox, html.kiwi-dark table.infobox,
html.kiwi-dark .infobox-full-data, html.kiwi-dark .mw-infobox {
    background-color: var(--kiwi-card-bg) !important;
    border-color: var(--kiwi-border) !important;
    color: var(--kiwi-text) !important;
}
html.kiwi-dark .infobox th, html.kiwi-dark .infobox td {
    border-color: var(--kiwi-border) !important;
    color: var(--kiwi-text) !important;
}
html.kiwi-dark #toc, html.kiwi-dark .toc,
html.kiwi-dark .navbox, html.kiwi-dark .navbox-title {
    background-color: var(--kiwi-card-bg) !important;
    border-color: var(--kiwi-border) !important;
    color: var(--kiwi-text) !important;
}
html.kiwi-dark pre, html.kiwi-dark code, html.kiwi-dark .mw-code {
    background-color: var(--kiwi-card-bg) !important;
    color: var(--kiwi-text) !important;
    border-color: var(--kiwi-border) !important;
}
html.kiwi-dark blockquote {
    border-left-color: var(--kiwi-accent) !important;
    background-color: var(--kiwi-card-bg) !important;
    color: var(--kiwi-text) !important;
}
html.kiwi-dark .hatnote, html.kiwi-dark .ambox, html.kiwi-dark .mbox-small {
    background-color: var(--kiwi-card-bg) !important;
    border-color: var(--kiwi-border) !important;
    color: var(--kiwi-muted) !important;
}
html.kiwi-dark img { opacity: .92; }
html.kiwi-dark img:hover { opacity: 1; }

/* Sepia overrides */
html.kiwi-sepia table th { background-color: var(--kiwi-card-bg) !important; }
html.kiwi-sepia .infobox, html.kiwi-sepia table.infobox {
    background-color: var(--kiwi-card-bg) !important;
    border-color: var(--kiwi-border) !important;
}

/* ── Lightbox (upgraded) ───────────────────────────────────── */
.kiwi-lightbox {
    display: none;
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.94);
    z-index: 99999;
    align-items: center;
    justify-content: center;
}
.kiwi-lightbox.open { display: flex; }
.kiwi-lb-img {
    max-width: 88%; max-height: 84%;
    object-fit: contain;
    border-radius: 4px;
    cursor: default;
    opacity: 1 !important;
}
.kiwi-lb-close, .kiwi-lb-prev, .kiwi-lb-next {
    position: absolute;
    background: rgba(255,255,255,.12);
    color: #fff;
    border: 1px solid rgba(255,255,255,.2);
    font-size: 28px;
    cursor: pointer;
    width: 48px; height: 48px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    transition: background .15s;
    font-family: system-ui;
}
.kiwi-lb-close:hover, .kiwi-lb-prev:hover, .kiwi-lb-next:hover {
    background: rgba(255,255,255,.25);
}
.kiwi-lb-close { top: 20px; right: 20px; }
.kiwi-lb-prev { left: 24px; top: 50%; transform: translateY(-50%); }
.kiwi-lb-next { right: 24px; top: 50%; transform: translateY(-50%); }
.kiwi-lb-counter {
    position: absolute; top: 24px; left: 24px;
    color: #fff;
    font-family: system-ui;
    font-size: 14px;
    background: rgba(0,0,0,.4);
    padding: 4px 10px;
    border-radius: 12px;
}
.kiwi-lb-caption {
    position: absolute; bottom: 24px; left: 50%;
    transform: translateX(-50%);
    color: #fff;
    font-family: system-ui;
    font-size: 14px;
    background: rgba(0,0,0,.5);
    padding: 8px 16px;
    border-radius: 6px;
    max-width: 80%;
    text-align: center;
}

/* ── Link preview popover (Wikipedia-style) ───────────────── */
.kiwi-preview {
    position: fixed;
    display: none;
    width: 340px;
    background: var(--kiwi-bg);
    border: 1px solid var(--kiwi-border-strong);
    border-radius: 12px;
    box-shadow: var(--kiwi-shadow-lg);
    padding: 16px 18px;
    z-index: 200;
    pointer-events: none;
    font-family: var(--kiwi-sans);
    font-size: 13.5px;
    line-height: 1.55;
    color: var(--kiwi-text);
    animation: kiwi-fade-in .15s ease-out;
}
@keyframes kiwi-fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
}
.kiwi-preview.show { display: block; }
.kiwi-preview-title {
    font-weight: 700;
    font-size: 15px;
    margin-bottom: 8px;
    color: var(--kiwi-text);
    letter-spacing: -0.01em;
}
.kiwi-preview-text {
    color: var(--kiwi-text-secondary);
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.kiwi-preview-source {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--kiwi-border);
    font-size: 11px;
    color: var(--kiwi-accent);
    text-transform: uppercase;
    letter-spacing: .07em;
    font-weight: 600;
}

/* ── Scroll-to-top button ──────────────────────────────────── */
.kiwi-scroll-top {
    position: fixed;
    bottom: 24px; right: 24px;
    width: 42px; height: 42px;
    border-radius: 50%;
    background: var(--kiwi-accent);
    color: #fff;
    border: none;
    cursor: pointer;
    font-size: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,.2);
    display: none;
    align-items: center; justify-content: center;
    z-index: 100;
    transition: transform .15s;
}
.kiwi-scroll-top:hover { transform: translateY(-2px); }
.kiwi-scroll-top.show { display: flex; }
"""

    # ------------------------------------------------------------------
    @staticmethod
    def _kiwi_js(archive_id: str, current_page_path: str, backend_url: str) -> str:
        """
        Client-side reader behaviour:
          • Intercepts every internal link → posts {type:'kiwi-navigate'} to parent.
            Modifier keys / middle-click are reported so the parent can open new tabs.
          • Reports scroll progress to parent via postMessage.
          • Listens for reader-prefs updates from parent (theme, font, width).
          • Builds the sticky TOC and tracks the active section.
          • Wikipedia-style hover link previews (debounced).
          • Image lightbox with arrow-key navigation and captions.
          • Scroll-to-top button visible after scrolling.
        """
        # Escape backslashes/quotes for safe template insertion
        archive_id_js = archive_id.replace("'", "\\'")
        backend_js = backend_url.replace("'", "\\'")
        current_page_js = current_page_path.replace("'", "\\'")

        return r"""
(function() {
    var ARCHIVE_ID = '""" + archive_id_js + r"""';
    var BACKEND = '""" + backend_js + r"""';
    var CURRENT_PATH = '""" + current_page_js + r"""';

    // ── Parse reader-mode prefs from URL params on first load ───────
    var url = new URL(window.location.href);
    var initFont = url.searchParams.get('font');
    var initWidth = url.searchParams.get('width');
    if (initFont) document.documentElement.style.setProperty('--kiwi-font-size', initFont + 'px');
    if (initWidth) {
        var widthMap = { narrow: '700px', normal: '920px', wide: '1200px' };
        document.documentElement.style.setProperty('--kiwi-column-width', widthMap[initWidth] || initWidth);
    }

    // ── Notify parent of new page so it can update history ──────────
    function postParent(msg) {
        try { window.parent.postMessage(msg, '*'); } catch (e) {}
    }
    postParent({ type: 'kiwi-page-loaded', archiveId: ARCHIVE_ID, path: CURRENT_PATH, title: document.title });

    // ── Listen for reader-pref updates from parent ──────────────────
    window.addEventListener('message', function(e) {
        if (!e.data || !e.data.type) return;
        var d = e.data;
        if (d.type === 'kiwi-set-theme') {
            document.documentElement.classList.remove('kiwi-dark', 'kiwi-light', 'kiwi-sepia');
            document.documentElement.classList.add('kiwi-' + d.theme);
        } else if (d.type === 'kiwi-set-font-size') {
            document.documentElement.style.setProperty('--kiwi-font-size', d.size + 'px');
        } else if (d.type === 'kiwi-set-column-width') {
            var widths = { narrow: '700px', normal: '920px', wide: '1200px' };
            document.documentElement.style.setProperty('--kiwi-column-width', widths[d.width] || '920px');
        } else if (d.type === 'kiwi-scroll-top') {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else if (d.type === 'kiwi-restore-scroll' && typeof d.percent === 'number') {
            // Restore scroll position from parent (back/forward through tab history)
            setTimeout(function() {
                var h = document.documentElement;
                var max = h.scrollHeight - h.clientHeight;
                if (max > 0) window.scrollTo(0, max * d.percent);
            }, 50);
        }
    });

    // ── Intercept all internal link clicks ──────────────────────────
    function isInternalLink(a) {
        if (!a || !a.href) return false;
        if (a.hasAttribute('data-kiwi-internal')) return true;
        return a.href.indexOf('/api/articles/') !== -1 && a.href.indexOf('/view/') !== -1;
    }
    function extractPath(href) {
        var m = href.match(/\/api\/articles\/([^/]+)\/view\/(.+)$/);
        if (!m) return null;
        return { archiveId: m[1], path: m[2] };
    }
    function onAnchorClick(e) {
        var anchor = e.target.closest && e.target.closest('a');
        if (!isInternalLink(anchor)) return;

        var info = extractPath(anchor.href);
        if (!info) return;

        // pure same-page hash anchor jump → let browser handle
        if (info.archiveId === ARCHIVE_ID && info.path.split('#')[0] === CURRENT_PATH.split('#')[0]) {
            return;  // browser scrolls to anchor naturally
        }

        e.preventDefault();
        // NEW DEFAULT: every link opens in a new tab (preserves the current
        // article and lets the user explore multiple topics at once).
        // Alt+click overrides to in-place navigation for power users who want
        // browser-style "follow the link in this tab" behaviour.
        var sameTab = e.altKey;
        postParent({
            type: 'kiwi-navigate',
            archiveId: info.archiveId,
            path: info.path,
            title: (anchor.innerText || '').trim().slice(0, 80) || 'Loading…',
            sameTab: sameTab,
            fromArchiveId: ARCHIVE_ID,
            fromPath: CURRENT_PATH,
            fromTitle: document.title,
        });
    }
    document.addEventListener('click', onAnchorClick);
    document.addEventListener('auxclick', function(e) {
        if (e.button === 1) onAnchorClick(e);  // middle-click opens new tab too
    });

    // ── Build sticky TOC from H2/H3 elements ─────────────────────────
    var content = document.querySelector('.kiwi-content');
    var headings = content ? content.querySelectorAll('h2, h3') : [];
    var tocList = document.getElementById('kiwi-toc-list');
    var tocEl = document.getElementById('kiwi-toc');
    var tocItems = [];
    if (headings.length >= 3 && tocList) {
        headings.forEach(function(h, i) {
            if (!h.id) h.id = 'kiwi-h-' + i;
            var li = document.createElement('li');
            var a = document.createElement('a');
            a.className = 'kiwi-toc-item' + (h.tagName === 'H3' ? ' kiwi-toc-h3' : '');
            a.href = '#' + h.id;
            a.textContent = (h.textContent || '').trim();
            a.onclick = function(e) {
                e.preventDefault();
                document.getElementById(h.id).scrollIntoView({ behavior: 'smooth', block: 'start' });
            };
            li.appendChild(a);
            tocList.appendChild(li);
            tocItems.push({ heading: h, link: a });
        });
        if (tocEl) tocEl.setAttribute('aria-hidden', 'false');

        // Active-section highlighting via IntersectionObserver
        var io = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    tocItems.forEach(function(item) {
                        item.link.classList.toggle('kiwi-toc-active', item.heading === entry.target);
                    });
                }
            });
        }, { rootMargin: '-15% 0px -70% 0px' });
        tocItems.forEach(function(item) { io.observe(item.heading); });
    }

    // ── Reading progress bar + scroll-to-top visibility ──────────────
    var progressEl = document.getElementById('kiwi-progress');
    var topBtn = document.getElementById('kiwi-scroll-top');
    function onScroll() {
        var h = document.documentElement;
        var max = h.scrollHeight - h.clientHeight;
        var pct = max > 0 ? (h.scrollTop / max) * 100 : 0;
        if (progressEl) progressEl.style.width = pct + '%';
        if (topBtn) topBtn.classList.toggle('show', h.scrollTop > 600);
        postParent({ type: 'kiwi-scroll', percent: pct });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    if (topBtn) topBtn.addEventListener('click', function() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    onScroll();

    // ── Lightbox (upgraded with arrows, counter, captions) ──────────
    var lb = document.getElementById('kiwi-lightbox');
    var lbImg = document.getElementById('kiwi-lb-img');
    var lbCap = document.getElementById('kiwi-lb-caption');
    var lbCnt = document.getElementById('kiwi-lb-counter');
    var lbClose = lb && lb.querySelector('.kiwi-lb-close');
    var lbPrev = lb && lb.querySelector('.kiwi-lb-prev');
    var lbNext = lb && lb.querySelector('.kiwi-lb-next');
    var lbImages = [];
    var lbIndex = 0;
    function findCaption(img) {
        var fig = img.closest('figure');
        if (fig) {
            var fc = fig.querySelector('figcaption');
            if (fc) return fc.textContent.trim();
        }
        return img.alt || '';
    }
    function showLb(i) {
        lbIndex = ((i % lbImages.length) + lbImages.length) % lbImages.length;
        var src = lbImages[lbIndex];
        lbImg.src = src.src;
        lbCap.textContent = src.caption;
        lbCap.style.display = src.caption ? '' : 'none';
        lbCnt.textContent = (lbIndex + 1) + ' / ' + lbImages.length;
        lb.classList.add('open');
    }
    function closeLb() { if (lb) lb.classList.remove('open'); }
    document.querySelectorAll('.kiwi-content img').forEach(function(img) {
        if ((img.naturalWidth || img.width) > 80) {
            img.addEventListener('click', function(e) {
                e.stopPropagation();
                // (Re)build the image list from current DOM so dynamically added images count
                lbImages = Array.prototype.map.call(
                    document.querySelectorAll('.kiwi-content img'),
                    function(im) { return { src: im.src, caption: findCaption(im) }; }
                );
                var idx = lbImages.findIndex(function(o) { return o.src === img.src; });
                showLb(idx === -1 ? 0 : idx);
            });
        }
    });
    if (lb) lb.addEventListener('click', function(e) { if (e.target === lb) closeLb(); });
    if (lbClose) lbClose.addEventListener('click', closeLb);
    if (lbPrev) lbPrev.addEventListener('click', function(e) { e.stopPropagation(); showLb(lbIndex - 1); });
    if (lbNext) lbNext.addEventListener('click', function(e) { e.stopPropagation(); showLb(lbIndex + 1); });
    document.addEventListener('keydown', function(e) {
        if (!lb || !lb.classList.contains('open')) return;
        if (e.key === 'Escape') closeLb();
        else if (e.key === 'ArrowLeft') showLb(lbIndex - 1);
        else if (e.key === 'ArrowRight') showLb(lbIndex + 1);
    });

    // ── Wikipedia-style link previews ────────────────────────────────
    var previewEl = document.getElementById('kiwi-preview');
    var previewTimer = null;
    var previewCache = {};
    function positionPreview(ev) {
        if (!previewEl) return;
        var x = ev.clientX + 14;
        var y = ev.clientY + 14;
        var maxX = window.innerWidth - 340;
        var maxY = window.innerHeight - 200;
        previewEl.style.left = Math.min(x, maxX) + 'px';
        previewEl.style.top = Math.min(y, maxY) + 'px';
    }
    function showPreview(data, ev) {
        if (!previewEl) return;
        positionPreview(ev);
        previewEl.innerHTML =
            '<div class="kiwi-preview-title">' + (data.title || 'Untitled') + '</div>' +
            '<div class="kiwi-preview-text">' + (data.snippet || '(no preview available)') + '</div>' +
            '<div class="kiwi-preview-source">' + (data.archive_title || '') + '</div>';
        previewEl.classList.add('show');
    }
    function hidePreview() {
        clearTimeout(previewTimer);
        if (previewEl) previewEl.classList.remove('show');
    }
    document.querySelectorAll('.kiwi-content a[data-kiwi-internal]').forEach(function(a) {
        a.addEventListener('mouseenter', function(e) {
            clearTimeout(previewTimer);
            previewTimer = setTimeout(function() {
                var info = extractPath(a.href);
                if (!info) return;
                var key = info.archiveId + '/' + info.path;
                if (previewCache[key]) { showPreview(previewCache[key], e); return; }
                fetch(BACKEND + '/api/articles/' + info.archiveId + '/preview/' + info.path)
                    .then(function(r) { return r.ok ? r.json() : null; })
                    .then(function(data) {
                        if (data) { previewCache[key] = data; showPreview(data, e); }
                    }).catch(function() {});
            }, 420);
        });
        a.addEventListener('mouseleave', hidePreview);
        a.addEventListener('mousemove', function(e) {
            if (previewEl && previewEl.classList.contains('show')) positionPreview(e);
        });
    });

    // ── Bubble Esc and slash-key events to parent (for command palette / focus) ──
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            postParent({ type: 'kiwi-key', key: 'cmd-k' });
        }
    });
})();
"""
