#!/usr/bin/env python3
"""
generate-indexes.py — Scant alle reismappen en dagpagina's,
regenereert de reis-indexen en de root-index.

Verwacht structuur:
  reiz-online/
  ├── index.html               (root — wordt bijgewerkt tussen markers)
  ├── istanbul-2026/
  │   ├── index.html            (reis-index — wordt bijgewerkt tussen markers)
  │   ├── dag-01.html
  │   ├── dag-02.html
  │   └── meta.json             (optioneel: reis-metadata)
  └── bali-2026/
      └── ...

meta.json voorbeeld:
{
  "title": "Istanbul",
  "subtitle": "twee werelden, één stad",
  "dates": "8 – 19 oktober 2026",
  "period": "oktober 2026",
  "description": "Tien dagen aan de Bosporus.",
  "cover": "fotos/cover.jpg"
}

Dagpagina's worden gescand op <title> en <meta name="description"> tags
voor titels en beschrijvingen.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def extract_html_meta(html_path: Path) -> dict:
    """Haal title en description uit een HTML-bestand."""
    text = html_path.read_text(encoding="utf-8")
    title_m = re.search(r"<title>(.*?)</title>", text, re.DOTALL)
    desc_m = re.search(r'<meta\s+name="description"\s+content="(.*?)"', text, re.DOTALL)
    # Zoek ook naar een data-date attribuut op body of main
    date_m = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', text)
    # Zoek naar een data-summary attribuut
    summary_m = re.search(r'data-summary="(.*?)"', text)
    return {
        "title": title_m.group(1).strip() if title_m else html_path.stem,
        "description": desc_m.group(1).strip() if desc_m else "",
        "date": date_m.group(1) if date_m else "",
        "summary": summary_m.group(1) if summary_m else "",
    }


def find_trips(root: Path) -> list[dict]:
    """Vind alle reismappen (mappen met minstens een index.html of dag-*.html)."""
    trips = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "scripts":
            continue
        day_files = sorted(d.glob("dag-*.html"))
        index_file = d / "index.html"
        meta_file = d / "meta.json"

        if not index_file.exists() and not day_files:
            continue

        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        # Fallback metadata uit mapnaam (bijv. istanbul-2026)
        parts = d.name.rsplit("-", 1)
        fallback_title = parts[0].replace("-", " ").title() if parts else d.name.title()
        fallback_year = parts[1] if len(parts) > 1 and parts[1].isdigit() else ""

        trips.append({
            "dir": d.name,
            "title": meta.get("title", fallback_title),
            "subtitle": meta.get("subtitle", ""),
            "dates": meta.get("dates", fallback_year),
            "period": meta.get("period", fallback_year),
            "description": meta.get("description", ""),
            "cover": meta.get("cover", ""),
            "days": day_files,
            "has_index": index_file.exists(),
        })

    return trips


def generate_day_card(day_file: Path, day_num: int) -> str:
    """Genereer HTML voor één dagkaart in een reis-index."""
    meta = extract_html_meta(day_file)
    title = meta["summary"] or meta["title"] or f"Dag {day_num}"
    # Verwijder " — reiz.online" suffix uit titel
    title = re.sub(r"\s*[—–-]\s*reiz\.online$", "", title)
    date_str = meta["date"]
    desc = meta["description"]

    return f"""      <a class="day-card" href="{day_file.name}">
        <div class="day-number">{day_num}</div>
        <div class="day-info">
          <h2>{title}</h2>
          {f'<div class="day-date">{date_str}</div>' if date_str else ''}
          {f'<p>{desc}</p>' if desc else ''}
        </div>
      </a>"""


def update_trip_index(trip: dict, root: Path):
    """Update de reis-index met de gevonden dagpagina's."""
    index_path = root / trip["dir"] / "index.html"
    if not index_path.exists():
        return

    content = index_path.read_text(encoding="utf-8")

    if not trip["days"]:
        return  # Niets te updaten

    # Genereer dag-cards
    cards = []
    for i, day_file in enumerate(trip["days"], 1):
        cards.append(generate_day_card(day_file, i))

    replacement = "<!-- AUTO-DAYS-START -->\n" + "\n".join(cards) + "\n      <!-- AUTO-DAYS-END -->"

    new_content = re.sub(
        r"<!-- AUTO-DAYS-START -->.*?<!-- AUTO-DAYS-END -->",
        replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        index_path.write_text(new_content, encoding="utf-8")
        print(f"  Updated: {trip['dir']}/index.html ({len(trip['days'])} dagen)")


def generate_trip_card(trip: dict) -> str:
    """Genereer HTML voor één reiskaart in de root-index."""
    day_count = len(trip["days"])
    day_text = f"{day_count} {'dag' if day_count == 1 else 'dagen'}" if day_count else ""

    if trip["cover"]:
        image_html = f'<img class="trip-card-image" src="{trip["dir"]}/{trip["cover"]}" alt="{trip["title"]}">'
    else:
        image_html = f'<div class="trip-card-image-placeholder">{trip["title"]}</div>'

    desc = trip["description"]
    if not desc and day_text:
        desc = day_text

    return f"""      <a class="trip-card" href="{trip['dir']}/">
        {image_html}
        <div class="trip-card-body">
          <h2>{trip['title']}</h2>
          <div class="trip-card-meta">{trip['period']}</div>
          {f'<p>{desc}</p>' if desc else ''}
        </div>
      </a>"""


def update_root_index(trips: list[dict], root: Path):
    """Update de root-index met alle gevonden reizen."""
    index_path = root / "index.html"
    if not index_path.exists():
        print("Geen root index.html gevonden — overgeslagen.")
        return

    content = index_path.read_text(encoding="utf-8")

    cards = [generate_trip_card(t) for t in trips]

    if not cards:
        inner = '      <div class="empty-state">Nog geen reizen gepubliceerd.</div>'
    else:
        inner = "\n".join(cards)

    replacement = "<!-- AUTO-INDEX-START -->\n" + inner + "\n      <!-- AUTO-INDEX-END -->"

    new_content = re.sub(
        r"<!-- AUTO-INDEX-START -->.*?<!-- AUTO-INDEX-END -->",
        replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        index_path.write_text(new_content, encoding="utf-8")
        print(f"Updated: index.html ({len(trips)} reizen)")


def main():
    print("=== reiz.online index generator ===\n")

    trips = find_trips(ROOT)
    print(f"Gevonden: {len(trips)} reis(en)\n")

    for trip in trips:
        print(f"  {trip['title']} ({trip['dir']}): {len(trip['days'])} dagpagina's")
        update_trip_index(trip, ROOT)

    print()
    update_root_index(trips, ROOT)
    print("\nKlaar.")


if __name__ == "__main__":
    main()
