"""Sestavení HTML přehledu pro e-mail."""
import datetime as dt
import html

BADGE = {
    "high":   ("KLÍČOVÉ",  "#c0392b"),
    "medium": ("Střední",  "#d68910"),
    "low":    ("Nízká",    "#7f8c8d"),
}


def _card(r: dict) -> str:
    label, color = BADGE.get(r["importance"], ("?", "#555"))
    title = html.escape(r.get("title", ""))
    summary = html.escape(r.get("summary_cs", ""))
    category = html.escape(r.get("category", "—"))
    source = html.escape(r.get("source", ""))
    url = html.escape(r.get("url", ""), quote=True)
    lang = html.escape((r.get("lang", "") or "").upper())
    meta = " · ".join(x for x in [source, lang, category] if x)
    return f"""
    <div style="border-left:4px solid {color};padding:10px 14px;margin:10px 0;background:#fafafa;">
      <span style="display:inline-block;font-size:11px;font-weight:700;color:#fff;
                   background:{color};border-radius:3px;padding:2px 7px;">{label}</span>
      <div style="font-size:15px;font-weight:600;margin:6px 0 4px;">
        <a href="{url}" style="color:#1a1a1a;text-decoration:none;">{title}</a>
      </div>
      <div style="font-size:13px;color:#333;line-height:1.4;">{summary}</div>
      <div style="font-size:11px;color:#888;margin-top:5px;">{meta} · <a href="{url}" style="color:#2980b9;">zdroj</a></div>
    </div>"""


def render_html(results: list) -> str:
    now = dt.datetime.now().strftime("%d. %m. %Y %H:%M")
    n_high = sum(1 for r in results if r["importance"] == "high")
    cards = "".join(_card(r) for r in results) or \
        '<p style="color:#888;">Za sledované období nebyly nalezeny žádné relevantní zprávy.</p>'
    return f"""<!DOCTYPE html><html><body style="margin:0;background:#fff;
        font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
      <div style="max-width:640px;margin:0 auto;padding:18px;">
        <h1 style="font-size:19px;margin:0 0 2px;">Romové ve světě – přehled zpráv</h1>
        <div style="font-size:12px;color:#888;margin-bottom:14px;">
          {now} · {len(results)} zpráv, z toho {n_high} klíčových
        </div>
        {cards}
        <div style="font-size:11px;color:#aaa;margin-top:20px;border-top:1px solid #eee;padding-top:10px;">
          Automatický monitoring · Google News + GDELT · třídění Claude
        </div>
      </div>
    </body></html>"""
