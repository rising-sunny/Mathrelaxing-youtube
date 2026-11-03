"""Genera un calendario de 30 dias (familia `expression`) con el formato de calendar.json.

Toma el calendar.json actual como plantilla: copia la politica, el bloque de audio
y los bloques por plataforma de metadata; reemplaza recetas, textos y fechas.

  python build_expression_calendar.py --template calendar.json --start 2026-10-28 --out calendar.expressions.json
"""
import argparse
import copy
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from expressions import EXPRESSIONS

TZ = ZoneInfo("America/Santiago")
PALETTES = [
    ["#03040A", "#28B9D8", "#FFC95C"],
    ["#05030A", "#B46CFF", "#5CF2FF"],
    ["#020806", "#3DE89B", "#F5F17A"],
    ["#0A0405", "#FF6B6B", "#FFD36B"],
    ["#03060C", "#5C8DFF", "#FF7AD9"],
    ["#060606", "#F2A65A", "#7AE7FF"],
]
YT_TAGS = "#Shorts #MathRelaxing #MathArt"
SOCIAL_TAGS = "#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"


def build(template, start, duration):
    tpl_item = template["items"][0]
    items = []
    for i, ex in enumerate(EXPRESSIONS):
        day = start + timedelta(days=i)
        publish = datetime.combine(day, time(18, 0), TZ)
        item = copy.deepcopy(tpl_item)
        audio = copy.deepcopy(tpl_item["recipe"].get("audio", {}))
        audio.update(seed=71000 + i, implementation_status="expression_renderer_synth")
        body = (f"{ex['title']}. {ex['question']}\n\n{ex['desc']}. "
                "Original, procedurally generated melodic ambient music.\n\n"
                "Follow @MathRelaxing for more mathematical patterns.")
        item.update(
            id=f"mrx-{i + 1:02d}-{day.isoformat()}",
            day=i + 1,
            publish_at=publish.isoformat(),
            timezone="America/Santiago",
            render_not_before=datetime.combine(day - timedelta(days=1), time(6, 0), TZ).isoformat(),
            status="planned_not_scheduled",
            family="expression",
            recipe={
                "expression_id": ex["id"],
                "expression": " ; ".join(ex["label"]),
                "kind": ex["kind"],
                "parameters": {"name": ex["a_name"], "range": list(ex["a"]), "pingpong": bool(ex.get("pingpong"))},
                "seed": int(day.strftime("%Y%m%d")),
                "generator_reference": "expression_renderer.py",
                "duration_seconds": duration,
                "fps": 30,
                "width": 1080,
                "height": 1920,
                "palette": PALETTES[i % len(PALETTES)],
                "audio": audio,
                "overlay": {"language": "en", "hook": ex["hook"], "subtitle": ex["desc"],
                            "closing": "SUBSCRIBE FOR MORE MATH", "handle": "@MathRelaxing"},
            },
        )
        meta = item["metadata"]
        meta.update(
            title=f"{ex['title']} | Math Art",
            youtube_description=f"{body}\n\n{YT_TAGS}",
            facebook_caption=f"{body}\n\n{SOCIAL_TAGS}",
            instagram_caption=f"{body}\n\n{SOCIAL_TAGS}",
        )
        items.append(item)

    cal = {k: copy.deepcopy(v) for k, v in template.items() if k != "items"}
    cal.update(start_date=items[0]["publish_at"][:10], end_date=items[-1]["publish_at"][:10],
               approval="expression calendar; install after VPS smoke test")
    cal["items"] = items
    return cal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", type=Path, required=True)
    ap.add_argument("--start", type=date.fromisoformat, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--duration", type=int, default=16)
    a = ap.parse_args()
    cal = build(json.loads(a.template.read_text()), a.start, a.duration)
    a.out.write_text(json.dumps(cal, indent=2, ensure_ascii=False))
    copied = {k: v for k, v in cal["items"][0]["metadata"].items()
              if k not in ("language", "title", "youtube_description", "facebook_caption", "instagram_caption")}
    print(f"{len(cal['items'])} dias: {cal['start_date']} -> {cal['end_date']}  ({a.out})")
    print("Bloques de metadata copiados de la plantilla (revisar):")
    print(json.dumps(copied, indent=1, ensure_ascii=False))
    for e in cal["items"]:
        print(e["publish_at"], e["recipe"]["expression_id"], "|", e["metadata"]["title"])


if __name__ == "__main__":
    main()
