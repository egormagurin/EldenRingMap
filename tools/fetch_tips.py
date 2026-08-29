"""Fetch route descriptions for your markers from the Fextralife interactive map.

    python tools/fetch_tips.py              -> data/tips.json

The markers this project builds say *what* a thing is and *where* it is. They
cannot say how to get to it - that is not in the game files, it is something
people write. The Fextralife wiki's interactive map has such a description for
about 4,800 of its markers, so this matches those markers against ours and keeps
the text.

READ THIS BEFORE RUNNING IT
---------------------------
The descriptions are Fextralife/Valnet's, not yours and not the game's, and
Valnet's robots.txt prohibits automated retrieval of their content without
written permission. This script therefore:

  * runs only when you run it - it is not part of Setup.bat,
  * fetches four static files, once, and caches them,
  * writes to data/tips.json, which is gitignored like every other generated
    file here.

Do not commit data/tips.json, do not publish it, and do not ship it with a fork.
Everything else in data/ comes from your own copy of the game and is yours to
regenerate; this one file is someone else's writing sitting on your disk for
your own use. If you want it in a public build, ask Valnet first.

    python tools/fetch_tips.py --maps Overland      # just the Lands Between
    python tools/fetch_tips.py --refresh            # re-download, ignore cache
    python tools/fetch_tips.py --report             # per-map matching detail
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict

reconfigure = getattr(sys.stdout, "reconfigure", None)
if reconfigure:
    reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "cache", "tips")

CDN = "https://static0.fextralifeimages.com/file/eldenring/{}.js"
WIKI = "https://eldenring.wiki.fextralife.com"
SOURCE = "Fextralife Elden Ring wiki interactive map"
CREDIT = "Fextralife"

# Their map tabs -> the master image ours land on. They have no DLC-underground
# map, so M11 gets nothing.
MAPS = {
    "Overland":      ("vm6a67b6fa9240c157fd42bc83", "M00"),
    "Underground":   ("vm6a67bad89240c157fd42bcf2", "M01"),
    "RealmOfShadow": ("vm6a67bd0d9240c157fd42be01", "M10"),
    "AshenCapital":  ("vm6a67bcf49240c157fd42bdc6", "M00"),
}

FIT_RADIUS = 150.0      # px, how far a name match may sit from its prediction
MIN_ANCHORS = 8         # below this the affine is not worth trusting


# ------------------------------------------------------------------- fetching

def fetch(map_id, refresh=False):
    """The map's definition file, cached under cache/tips/."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, map_id + ".js")
    if os.path.exists(path) and not refresh:
        return open(path, encoding="utf-8").read()
    url = CDN.format(map_id)
    req = urllib.request.Request(url, headers={"User-Agent": "elden-ring-live-map"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# -------------------------------------------------------------------- parsing

# The file is a JS object literal, not JSON: single-quoted strings with
# backslash escapes, and the prose is full of apostrophes. A regex that stops at
# the first quote truncates every description containing one, so scan properly.
def read_string(text, i):
    """text[i] is the opening quote -> (value, index just past the closer)."""
    out = []
    i += 1
    while i < len(text):
        c = text[i]
        if c == "\\":
            nxt = text[i + 1] if i + 1 < len(text) else ""
            out.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
            i += 2
            continue
        if c == "'":
            return "".join(out), i + 1
        out.append(c)
        i += 1
    return "".join(out), i


FIELD_RE = re.compile(r"(\w+)\s*:\s*")


def parse_markers(text):
    """-> [{uid, x, y, title, description, link, tooltip}] for every marker."""
    markers = []
    for m in re.finditer(r"\n\t\t\{\n\t\t\tuid: '", text):
        start = m.start()
        end = text.find("\n\t\t},", start)
        if end == -1:
            end = text.find("\n\t\t}", start)
        chunk = text[start:end if end != -1 else len(text)]

        rec, depth_popup = {}, False
        i = 0
        while True:
            f = FIELD_RE.search(chunk, i)
            if not f:
                break
            key, i = f.group(1), f.end()
            if i < len(chunk) and chunk[i] == "'":
                val, i = read_string(chunk, i)
                # `title`/`description`/`link` only mean anything inside `popup`
                if key in ("title", "description", "link"):
                    if depth_popup:
                        rec.setdefault(key, val)
                else:
                    rec.setdefault(key, val)
            elif key == "popup":
                depth_popup = True
            else:
                num = re.match(r"(-?[\d.]+)", chunk[i:])
                if num and key in ("x", "y"):
                    rec[key] = float(num.group(1))
        if "x" in rec and "y" in rec:
            markers.append(rec)
    return markers


# ------------------------------------------------------------------- matching

RELATIVE_HREF = re.compile(r"""(href\s*=\s*["'])(/[^"']*)""")


def absolute_links(html):
    """Their descriptions link to their own wiki, sometimes by relative path.

    A bare "/Red-Feathered+Branchsword" resolves against their site, not the map
    running on localhost, so it has to be made absolute here. Everything else
    about the text is left exactly as fetched - the renderer decides what of it
    is safe to draw, not this.
    """
    return RELATIVE_HREF.sub(lambda m: m.group(1) + WIKI + m.group(2), html)


PAREN = re.compile(r"\s*\([^)]*\)")
SUFFIX = re.compile(r"\s+-\s+.*$")           # "Smithing Stone [7] - 3x Castle Sol"
COUNT = re.compile(r"\s+x\s*\d+\s*$", re.I)  # "Ember of Messmer x2"
LEAD_COUNT = re.compile(r"^\d+x\s+", re.I)
NONWORD = re.compile(r"[^a-z0-9\[\]+]+")


def norm(name):
    """Their marker names carry location and count decoration; ours do not."""
    if not name:
        return ""
    s = name.split(":")[0] if ": " in name and name.count(":") == 1 else name
    s = SUFFIX.sub("", s)
    s = PAREN.sub("", s)
    s = COUNT.sub("", s)
    s = LEAD_COUNT.sub("", s)
    return NONWORD.sub(" ", s.lower()).strip()


def variants(*names):
    """Every spelling a marker might be found under.

    A boss we name for all its phases - "Godfrey, First Elden Lord / Hoarah
    Loux, Warrior" - is two markers on their map, one per name.
    """
    out = set()
    for n in names:
        if not n:
            continue
        out.add(norm(n))
        if " / " in n:
            out.update(norm(p) for p in n.split(" / "))
    return {v for v in out if v}


def fit_axis(pairs, src, dst):
    """Least-squares y = m*x + c over (src, dst) pairs."""
    n = len(pairs)
    sx = sum(p[src] for p in pairs)
    sy = sum(p[dst] for p in pairs)
    sxx = sum(p[src] * p[src] for p in pairs)
    sxy = sum(p[src] * p[dst] for p in pairs)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None
    m = (n * sxy - sx * sy) / denom
    return m, (sy - m * sx) / n


def fit_affine(theirs, ours):
    """Their normalised x/y -> our master pixels, from uniquely-named anchors.

    Fitted rather than assumed: their base image is the same map art we tile,
    but cropped and scaled differently per tab, and nobody publishes the numbers.
    Anchors are names that occur exactly once on each side, which in practice
    means graces and bosses - the decorated item names are not unique.
    """
    ours_by_name = defaultdict(list)
    for o in ours:
        ours_by_name[norm(o["names"]["en"])].append(o)
    theirs_by_name = defaultdict(list)
    for t in theirs:
        theirs_by_name[norm(t.get("tooltip") or t.get("title"))].append(t)

    pairs = [{"x": t[0]["x"], "y": t[0]["y"], "px": o[0]["px"], "py": o[0]["py"]}
             for name, t in theirs_by_name.items()
             for o in [ours_by_name.get(name, [])]
             if name and len(t) == 1 and len(o) == 1]
    if len(pairs) < MIN_ANCHORS:
        return None, len(pairs), 0.0

    # One robust refit: hand-placed markers scatter, and a few are plain wrong.
    for _ in range(2):
        fx, fy = fit_axis(pairs, "x", "px"), fit_axis(pairs, "y", "py")
        if not fx or not fy:
            return None, len(pairs), 0.0
        errs = [((fx[0] * p["x"] + fx[1] - p["px"]) ** 2 +
                 (fy[0] * p["y"] + fy[1] - p["py"]) ** 2) ** .5 for p in pairs]
        cut = sorted(errs)[int(len(errs) * 0.9)] if len(errs) > 12 else max(errs)
        keep = [p for p, e in zip(pairs, errs) if e <= max(cut, 1.0)]
        if len(keep) < MIN_ANCHORS or len(keep) == len(pairs):
            break
        pairs = keep
    rms = (sum(e * e for e in errs) / len(errs)) ** .5
    return (fx, fy), len(pairs), rms


def match(theirs, ours, affine, radius):
    """-> {our marker id: their marker}, by name then by distance.

    Assignment is global rather than per-marker: build every same-name pair
    inside `radius`, sort by distance, and take them nearest-first with each
    side used once. Walking our markers in order and letting each grab its
    nearest instead loses about a third of the repeated items - there are 226
    "Golden Rune [1]"s, and whoever asks first takes a marker that belonged to
    someone else.
    """
    (mx, cx), (my, cy) = affine
    by_name = defaultdict(list)
    for t in theirs:
        if not (t.get("description") or "").strip():
            continue
        t["_px"], t["_py"] = mx * t["x"] + cx, my * t["y"] + cy
        for n in variants(t.get("tooltip"), t.get("title")):
            by_name[n].append(t)

    pairs = []
    for o in ours:
        seen = set()
        for n in variants(o["names"]["en"]):
            for t in by_name.get(n, ()):
                if id(t) in seen:            # indexed under two spellings
                    continue
                seen.add(id(t))
                d = ((t["_px"] - o["px"]) ** 2 + (t["_py"] - o["py"]) ** 2) ** .5
                if d <= radius:
                    pairs.append((d, o["id"], o, t))
    pairs.sort(key=lambda p: p[0])

    out, used_ours, used_theirs = {}, set(), set()
    for _, oid, o, t in pairs:
        if oid in used_ours or id(t) in used_theirs:
            continue
        used_ours.add(oid)
        used_theirs.add(id(t))
        out[oid] = t
    return out


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", default=",".join(MAPS),
                    help="which of their map tabs to read (default: all)")
    ap.add_argument("--out", default=os.path.join(DATA, "tips.json"))
    ap.add_argument("--refresh", action="store_true", help="re-download, ignore the cache")
    ap.add_argument("--report", action="store_true", help="per-map matching detail")
    args = ap.parse_args()

    ours = []
    for f in ("markers.json", "items.json"):
        p = os.path.join(DATA, f)
        if os.path.exists(p):
            ours += json.load(open(p, encoding="utf-8"))["markers"]
    if not ours:
        sys.exit("no markers found - run tools/build_markers.py first")
    by_master = defaultdict(list)
    for m in ours:
        if m.get("px") is not None:
            by_master[m["master"]].append(m)
    print(f"our markers: {len(ours)} "
          + ", ".join(f"{k}={len(v)}" for k, v in sorted(by_master.items())))

    print(f"\nreading the {SOURCE}")
    print("  (their content, not the game's - see the header of this file)")

    tips, stats = {}, []
    for name in [s.strip() for s in args.maps.split(",") if s.strip()]:
        if name not in MAPS:
            sys.exit(f"unknown map {name!r} - pick from {', '.join(MAPS)}")
        map_id, master = MAPS[name]
        t0 = time.time()
        text = fetch(map_id, args.refresh)
        theirs = parse_markers(text)
        described = [t for t in theirs if (t.get("description") or "").strip()]

        affine, anchors, rms = fit_affine(theirs, by_master.get(master, []))
        if affine is None:
            print(f"  {name:<14} {len(theirs):>5} markers   no usable fit "
                  f"({anchors} anchors) - skipped")
            stats.append((name, len(theirs), len(described), 0, anchors, rms))
            continue

        # Their markers are hand-placed, so allow a few times the fit's own
        # scatter before calling a same-named marker a different thing.
        radius = max(FIT_RADIUS, 6.0 * rms)
        hits = match(theirs, by_master.get(master, []), affine, radius)
        for our_id, t in hits.items():
            tips[our_id] = {"text": absolute_links(t["description"]), "credit": CREDIT}
            if t.get("link"):
                tips[our_id]["link"] = t["link"]
        pct = 100.0 * len(hits) / max(len(described), 1)
        print(f"  {name:<14} {len(theirs):>5} markers, {len(described):>4} described"
              f"  ->  {len(hits):>4} matched ({pct:4.1f}%)"
              f"   [{anchors} anchors, {rms:.0f}px rms, r={radius:.0f}, "
              f"{time.time() - t0:.1f}s]")
        if args.report:
            print(f"      px = {affine[0][0]:.2f}*x + {affine[0][1]:.1f}   "
                  f"py = {affine[1][0]:.2f}*y + {affine[1][1]:.1f}")
        stats.append((name, len(theirs), len(described), len(hits), anchors, rms))

    doc = {
        "source": SOURCE,
        "credit": CREDIT,
        "note": ("Third-party content, fetched locally for personal use. "
                 "Not redistributable - do not commit or publish this file."),
        "fetchedAt": time.strftime("%Y-%m-%d"),
        "tips": tips,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print(f"\n-> {args.out}  ({len(tips)} tips, {os.path.getsize(args.out):,} bytes)")
    covered = defaultdict(int)
    for m in ours:
        if m["id"] in tips:
            covered[m["master"]] += 1
    print(f"   {len(tips)}/{len(ours)} of your markers now carry a route description "
          f"({100.0 * len(tips) / len(ours):.0f}%)")
    print("   " + ", ".join(f"{k} {covered[k]}/{len(by_master[k])}"
                            for k in sorted(by_master)))
    print("   gitignored, and it stays that way - it is not yours to redistribute")


if __name__ == "__main__":
    main()
