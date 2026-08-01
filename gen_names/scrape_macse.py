#!/usr/bin/env python3
"""Scrape the full family-name list from macse.hu into a plain text file.

The site lists surnames at
    https://macse.hu/familiae/CsaladNevekLista.php?ABID=A&b=<letter>
where <letter> is one of the initials in the page's letter navigation bar
(A-Z plus a few oddities like "." and Hebrew letters). Each letter shows at
most 250 names per page, further pages hang off a &st=<offset> parameter.

Usage:
    python3 scrape_macse.py                       # -> macse_csaladnevek.txt
    python3 scrape_macse.py -o names.txt --delay 1.0
    python3 scrape_macse.py --letters A B C       # only these initials
"""

import argparse
import html
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://macse.hu/familiae/"
LIST_URL = BASE + "CsaladNevekLista.php"
USER_AGENT = "Mozilla/5.0 (compatible; transznemu.hu name collector)"

# <a class='hivas' href='CsaladNevLista.php?...&csnev=...'><b>NAME</b></a>
NAME_RE = re.compile(r"csnev=[^']*'>\s*<b>(.*?)</b>", re.S)
# Letter navigation: single-quoted hrefs, which excludes the double-quoted
# language-switcher links pointing at de/, en/, sk/ copies of the same page.
LETTER_RE = re.compile(r"href='CsaladNevekLista\.php\?ABID=A&amp;b=([^'&]+)'")
# Pagination: &st=<offset> links at the bottom of a letter's first page.
OFFSET_RE = re.compile(r"href='CsaladNevekLista\.php\?[^']*&amp;st=(\d+)'")


def fetch(params, retries=3, delay=1.0):
    """GET the list page with the given query params, returning decoded HTML."""
    url = LIST_URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries:
                raise
            wait = delay * 2 ** attempt
            print(f"  ! {exc} — retrying in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)


def parse_names(page):
    """Pull the surnames out of one listing page, in document order."""
    return [html.unescape(m).strip() for m in NAME_RE.findall(page)]


def parse_letters(page):
    """Pull the initials offered by the letter navigation bar."""
    return [html.unescape(m) for m in LETTER_RE.findall(page)]


def parse_offsets(page):
    """Pull the &st= offsets of the remaining pages for this letter."""
    return sorted({int(m) for m in OFFSET_RE.findall(page)})


def sort_key(name):
    """Roughly Hungarian-friendly ordering: accents fold onto their base letter."""
    folded = unicodedata.normalize("NFD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return (folded.upper(), name)


def scrape_letter(letter, delay, abid="A"):
    """Return every name filed under one initial, following its pagination."""
    page = fetch({"ABID": abid, "b": letter})
    names = parse_names(page)
    offsets = parse_offsets(page)
    print(f"  {letter}: {len(names)} names (+{len(offsets)} more page(s))")

    for offset in offsets:
        time.sleep(delay)
        page = fetch({"ABID": abid, "b": letter, "st": offset})
        more = parse_names(page)
        print(f"  {letter} @{offset}: {len(more)} names")
        names.extend(more)

    return names


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default="macse_csaladnevek.txt",
                    help="output file (default: %(default)s)")
    ap.add_argument("--delay", type=float, default=0.5,
                    help="seconds to wait between requests (default: %(default)s)")
    ap.add_argument("--letters", nargs="+", metavar="L",
                    help="only scrape these initials instead of all of them")
    ap.add_argument("--abid", default="A",
                    help="family tree id used by the site (default: %(default)s = all trees)")
    args = ap.parse_args()

    # The seed page both gives us the "A" names and tells us which other
    # initials exist — the current letter is plain text, not a link, so add it.
    print("Fetching letter index…")
    seed = fetch({"ABID": args.abid, "b": "A"})
    letters = ["A"] + [l for l in parse_letters(seed) if l != "A"]
    if args.letters:
        wanted = set(args.letters)
        missing = wanted - set(letters)
        letters = [l for l in letters if l in wanted]
        if missing:
            print(f"! not offered by the site: {sorted(missing)}", file=sys.stderr)
    print(f"Letters: {' '.join(letters)}")

    names = set()
    for letter in letters:
        try:
            names.update(scrape_letter(letter, args.delay, args.abid))
        except Exception as exc:  # keep whatever we already collected
            print(f"! letter {letter} failed: {exc}", file=sys.stderr)
        time.sleep(args.delay)

    ordered = sorted(names, key=sort_key)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(ordered) + "\n")
    print(f"\n{len(ordered)} unique names written to {args.out}")


if __name__ == "__main__":
    main()
