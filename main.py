"""Hlavní běh: sběr -> analýza -> přehled -> e-mail.

Spuštění lokálně:  python main.py
Na GitHub Actions:  běží automaticky podle cronu v .github/workflows/digest.yml
"""
import datetime as dt

import fetch
import analyze
import render
import notify


def run() -> None:
    print("1/4 Sbírám kandidátské články…")
    items = fetch.collect()
    print(f"     kandidátů: {len(items)}")
    if not items:
        print("Žádní kandidáti, končím.")
        return

    print("2/4 Analyzuji a třídím přes Claude…")
    results = analyze.analyze(items)
    print(f"     relevantních: {len(results)}")

    print("3/4 Sestavuji přehled…")
    html_body = render.render_html(results)

    print("4/4 Odesílám…")
    n_high = sum(1 for r in results if r["importance"] == "high")
    subject = (f"Romové ve světě: {len(results)} zpráv "
               f"({n_high} klíčových) – {dt.datetime.now():%d.%m. %H:%M}")
    notify.send(subject, html_body)
    print("Hotovo.")


if __name__ == "__main__":
    run()
