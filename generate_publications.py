#!/usr/bin/env python3

from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BIB_PATH = ROOT / "mypapers.bib"
OUTPUT_PATH = ROOT / "publications.html"
OUTPUT_EN_PATH = ROOT / "en" / "publications.html"
OUTPUT_ES_PATH = ROOT / "es" / "publications.html"
MY_DISPLAY_NAME = "Luis E. Salazar Manzano"

MONTH_ORDER = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

JOURNAL_MAP = {
    r"\apjl": "The Astrophysical Journal Letters",
    r"\apjs": "The Astrophysical Journal Supplement Series",
    r"\apj": "The Astrophysical Journal",
    r"\aj": "The Astronomical Journal",
    r"\mnras": "Monthly Notices of the Royal Astronomical Society",
    r"\pasp": "Publications of the Astronomical Society of the Pacific",
    r"\psj": "The Planetary Science Journal",
}

LATEX_ACCENTS = {
    "'": "",
    '"': "",
    "`": "",
    "^": "",
    "~": "",
    ".": "",
    "=": "",
    "u": "",
    "v": "",
    "H": "",
    "c": "",
    "k": "",
    "r": "",
    "b": "",
}

LATEX_ACCENT_CHARS = {
    ("~", "n"): "ñ",
    ("~", "N"): "Ñ",
}


def split_entries(text: str) -> list[str]:
    entries: list[str] = []
    current: list[str] = []
    depth = 0

    for line in text.splitlines():
        if line.strip().startswith("@") and not current:
            current = [line]
            depth = line.count("{") - line.count("}")
            continue
        if current:
            current.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                entries.append("\n".join(current))
                current = []
                depth = 0
    return entries


def split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    brace_depth = 0
    quote_depth = 0

    for char in value:
        if char == "{" and quote_depth == 0:
            brace_depth += 1
        elif char == "}" and quote_depth == 0 and brace_depth > 0:
            brace_depth -= 1
        elif char == '"':
            quote_depth = 1 - quote_depth
        elif char == "," and brace_depth == 0 and quote_depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def parse_entry(entry_text: str) -> dict[str, str]:
    header, body = entry_text.split("\n", 1)
    entry_type = header[1:header.index("{")].strip()
    key = header[header.index("{") + 1 : header.rindex(",")].strip()
    body = body.rsplit("}", 1)[0]

    fields: dict[str, str] = {"ENTRYTYPE": entry_type, "ID": key}
    for field in split_top_level(body):
        if "=" not in field:
            continue
        name, raw_value = field.split("=", 1)
        fields[name.strip().lower()] = clean_value(raw_value.strip())
    return fields


def clean_value(value: str) -> str:
    value = value.rstrip(",").strip()
    if (value.startswith("{") and value.endswith("}")) or (
        value.startswith('"') and value.endswith('"')
    ):
        value = value[1:-1].strip()
    value = value.replace("\n", " ").replace("\t", " ")
    value = re.sub(r"\s+", " ", value)
    return decode_latex(value)


def decode_latex(value: str) -> str:
    value = re.sub(r"\$_\{([^}]+)\}\$", r"\1", value)
    value = re.sub(
        r"\\([\'\"`\^~\.=uvHckrb])\{?([A-Za-z])\}?",
        lambda match: LATEX_ACCENT_CHARS.get(
            (match.group(1), match.group(2)),
            LATEX_ACCENTS.get(match.group(1), "") + match.group(2),
        ),
        value,
    )
    value = value.replace(r"\_", "_")
    for latex, replacement in JOURNAL_MAP.items():
        value = value.replace(latex, replacement)
    value = value.replace(r"\&", "&")
    value = re.sub(r"\\[A-Za-z]+", "", value)
    value = value.replace("\\", "")
    value = re.sub(r"[{}$]", "", value)
    return value.strip()


def escape_text(value: str) -> str:
    return html.escape(value, quote=False)


def normalize_author(author: str) -> str:
    author = author.strip()
    if "," in author:
        last, first = [part.strip() for part in author.split(",", 1)]
        return f"{first} {last}".strip()
    return author


def author_tokens(author: str) -> set[str]:
    normalized = normalize_author(author).lower()
    normalized = re.sub(r"[^a-z\s-]", " ", normalized)
    normalized = normalized.replace("-", " ")
    return {token for token in normalized.split() if token}


def is_my_author(author: str) -> bool:
    tokens = author_tokens(author)
    return "luis" in tokens and "manzano" in tokens


def highlight_author(author: str) -> str:
    if is_my_author(author):
        return f"<strong>{escape_text(MY_DISPLAY_NAME)}</strong>"
    return escape_text(author)


def format_authors(author_field: str) -> str:
    authors = [normalize_author(author) for author in author_field.split(" and ")]
    my_index = next((index for index, author in enumerate(authors) if is_my_author(author)), None)

    if my_index is not None and my_index >= 3 and len(authors) > 4:
        first_three = ", ".join(highlight_author(author) for author in authors[:3])
        my_name = highlight_author(authors[my_index])
        return f"{first_three}, ... (including {my_name})"

    formatted: list[str] = []
    for author in authors:
        formatted.append(highlight_author(author))
    return ", ".join(formatted)


def sort_key(entry: dict[str, str]) -> tuple[int, int, str]:
    year = int(entry.get("year", "0"))
    month = MONTH_ORDER.get(entry.get("month", "").lower(), 0)
    return (year, month, entry.get("title", ""))


def build_links(entry: dict[str, str]) -> str:
    links: list[str] = []
    doi = entry.get("doi")
    eprint = entry.get("eprint")
    adsurl = entry.get("adsurl")

    if doi:
        safe_doi = escape_text(doi)
        links.append(f'<a href="https://doi.org/{safe_doi}">DOI</a>')
    if eprint:
        safe_eprint = escape_text(eprint)
        links.append(f'<a href="https://arxiv.org/abs/{safe_eprint}">arXiv</a>')
    if adsurl:
        links.append(f'<a href="{escape_text(adsurl)}">ADS</a>')

    if not links:
        return ""
    return " [" + " | ".join(links) + "]"


def format_citation(entry: dict[str, str]) -> str:
    authors = format_authors(entry.get("author", ""))
    title = escape_text(entry.get("title", ""))
    year = escape_text(entry.get("year", ""))
    journal = escape_text(entry.get("journal", ""))
    volume = escape_text(entry.get("volume", ""))
    number = escape_text(entry.get("number", ""))
    pages = escape_text(entry.get("pages") or entry.get("eid", ""))

    details: list[str] = []
    if journal:
        details.append(journal)
    if volume:
        details.append(volume)
    if number:
        details.append(f"({number})")
    if pages:
        details.append(pages)

    details_text = ", ".join(details)
    links = build_links(entry)
    if details_text:
        return f"{authors} ({year}). <i>{title}</i>. {details_text}.{links}"
    return f"{authors} ({year}). <i>{title}</i>.{links}"


def split_sections(entries: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    first_author: list[dict[str, str]] = []
    coauthor: list[dict[str, str]] = []

    for entry in entries:
        authors = [normalize_author(author) for author in entry.get("author", "").split(" and ") if author.strip()]
        if authors and is_my_author(authors[0]):
            first_author.append(entry)
        else:
            coauthor.append(entry)

    return first_author, coauthor


def build_page(entries: list[dict[str, str]], language: str) -> str:
    first_author_entries, coauthor_entries = split_sections(entries)
    first_author_items = "\n".join(
        f"              <li>{format_citation(entry)}</li>" for entry in first_author_entries
    )
    coauthor_items = "\n".join(
        f"              <li>{format_citation(entry)}</li>" for entry in coauthor_entries
    )

    if language == "es":
        html_lang = "es"
        home_label = "Inicio"
        research_label = "Investigacion"
        publications_label = "Publicaciones"
        outreach_label = "Servicio/Divulgacion"
        telescopes_label = "Telescopios"
        section_title = "Publicaciones"
        first_author_title = "Artículos como primer autor"
        coauthor_title = "Artículos como coautor"
        en_href = "../en/publications.html"
        es_href = "publications.html"
        css_href = "../css/style.css"
    else:
        html_lang = "en"
        home_label = "Home"
        research_label = "Research"
        publications_label = "Publications"
        outreach_label = "Service/Outreach"
        telescopes_label = "Telescopes"
        section_title = "Publications"
        first_author_title = "First-author Papers"
        coauthor_title = "Coauthor Papers"
        en_href = "publications.html"
        es_href = "../es/publications.html"
        css_href = "../css/style.css"

    return f"""<!doctype html>
<html lang="{html_lang}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Luis Salazar Manzano</title>

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.6/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="{css_href}" rel="stylesheet">
  </head>

  <body>

    <nav class="navbar fixed-top navbar-expand-md">
      <div class="container">
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">Menu</button>
        <div class="collapse navbar-collapse justify-content-center" id="navbarSupportedContent">
          <ul class="navbar-nav">
                        <a class="nav-link" href="index.html">{home_label}</a>
                        <a class="nav-link" href="research.html">{research_label}</a>
                        <a class="nav-link active" aria-current="page" href="publications.html">{publications_label}</a>
                        <a class="nav-link" href="outreach.html">{outreach_label}</a>
                        <a class="nav-link" href="telescopes.html">{telescopes_label}</a>
          </ul>
        </div>
                <div class="language-switch" aria-label="Language switcher">
                    <a class="lang-link{' active' if language == 'en' else ''}"{' aria-current="page"' if language == 'en' else ''} href="{en_href}">EN</a>
                    <a class="lang-link{' active' if language == 'es' else ''}"{' aria-current="page"' if language == 'es' else ''} href="{es_href}">ES</a>
                </div>
      </div>
    </nav>

    <div id="publications" class="first_section">
      <div class="container">
        <div class="row">
          <div class="col-lg-8 offset-lg-2">
                        <h2>{section_title}</h2>
                        <h3>{first_author_title}</h3>
            <ol>
{first_author_items}
            </ol>
                        <h3>{coauthor_title}</h3>
            <ol>
{coauthor_items}
            </ol>
          </div>
        </div>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.6/dist/js/bootstrap.bundle.min.js"></script>

  </body>
</html>
"""


def main() -> None:
    entries = [parse_entry(entry) for entry in split_entries(BIB_PATH.read_text())]
    entries.sort(key=sort_key, reverse=True)
    OUTPUT_PATH.write_text(build_page(entries, "en"))
    OUTPUT_EN_PATH.write_text(build_page(entries, "en"))
    OUTPUT_ES_PATH.write_text(build_page(entries, "es"))
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {OUTPUT_EN_PATH}")
    print(f"Wrote {OUTPUT_ES_PATH}")


if __name__ == "__main__":
    main()
