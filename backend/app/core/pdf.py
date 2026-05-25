"""Markdown -> styled HTML -> PDF via WeasyPrint.

The print CSS aims for a clean, professional SOP document: letter-size paper,
1in margins, system fonts, hierarchical headings, page breaks before each
top-level section, and a page number footer.
"""
from datetime import date

PRINT_CSS = """
@page {
  size: Letter;
  margin: 1in 1in 1.1in 1in;
  @bottom-center {
    content: "Page " counter(page) " of " counter(pages);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 9pt;
    color: #888;
  }
}

@page:first {
  margin-top: 1.2in;
}

* {
  box-sizing: border-box;
}

html, body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
  font-size: 11pt;
  line-height: 1.55;
  color: #1a1a1a;
}

.cover-eyebrow {
  font-size: 8.5pt;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: #888;
  margin-bottom: 4pt;
}

.cover-meta {
  font-size: 9pt;
  color: #888;
  margin-top: 6pt;
  border-top: 1px solid #e0e0e0;
  padding-top: 8pt;
}

h1 {
  font-size: 22pt;
  font-weight: 700;
  margin: 0 0 4pt 0;
  line-height: 1.2;
}

h2 {
  font-size: 14pt;
  font-weight: 700;
  margin: 22pt 0 8pt 0;
  page-break-after: avoid;
  break-after: avoid;
}

h3 {
  font-size: 11.5pt;
  font-weight: 700;
  margin: 16pt 0 4pt 0;
  page-break-after: avoid;
  break-after: avoid;
  page-break-inside: avoid;
}

/* Major sections start on a new-ish page when possible. */
h2 {
  page-break-before: auto;
}

p {
  margin: 0 0 8pt 0;
  orphans: 3;
  widows: 3;
}

ul, ol {
  margin: 0 0 10pt 0;
  padding-left: 1.4em;
}

li {
  margin-bottom: 3pt;
}

strong {
  font-weight: 700;
}

em {
  font-style: italic;
}

code {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 9.5pt;
  background: #f4f4f4;
  padding: 1pt 4pt;
  border-radius: 3pt;
}

pre {
  background: #f4f4f4;
  border: 1px solid #e8e8e8;
  border-radius: 4pt;
  padding: 10pt 12pt;
  font-size: 9.5pt;
  page-break-inside: avoid;
  white-space: pre-wrap;
}

blockquote {
  margin: 10pt 0;
  padding: 8pt 12pt;
  border-left: 3pt solid #888;
  background: #fafafa;
  color: #555;
  page-break-inside: avoid;
}

/* TODO callouts the SOP renderer emits. */
blockquote strong:first-child {
  color: #b85c00;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 10pt 0;
  page-break-inside: avoid;
}

th, td {
  text-align: left;
  padding: 6pt 8pt;
  border-bottom: 1px solid #e0e0e0;
  font-size: 10pt;
}

th {
  font-weight: 700;
  border-bottom: 1.5px solid #888;
}

a {
  color: #1a4480;
  text-decoration: none;
}

hr {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 16pt 0;
}

/* Try to keep each step block (### Step N) together. */
.sop-content h3 + p,
.sop-content h3 + ul,
.sop-content h3 + ol {
  page-break-before: avoid;
}
"""


def markdown_to_pdf_bytes(
    markdown_text: str,
    title: str,
    unit: str,
) -> bytes:
    """Convert SOP markdown to a styled PDF and return the raw bytes.

    `markdown` and `weasyprint` are imported lazily so the module loads in
    environments where the WeasyPrint native deps (cairo/pango) aren't installed.
    The Dockerfile installs them for production; local dev without them only
    breaks if you actually hit this endpoint.
    """
    import markdown as md_lib  # noqa: PLC0415
    from weasyprint import HTML  # noqa: PLC0415

    html_body = md_lib.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "tables", "smarty"],
    )

    generated_on = date.today().isoformat()
    full_html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_escape(title)}</title>
<style>{PRINT_CSS}</style>
</head>
<body>
<div class="cover-eyebrow">Standard Operating Procedure</div>
<div class="cover-meta">{_escape(unit)} &nbsp;·&nbsp; Generated {generated_on}</div>
<div class="sop-content">
{html_body}
</div>
</body>
</html>
"""

    return HTML(string=full_html).write_pdf()


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
