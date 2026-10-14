"""
diagrams.py - use figures and diagrams from the slides (hackathon requirement 1d)

What it does
  1. Scans data/slides_01.pdf ... slides_05.pdf and ranks pages by how much
     graphics they contain (images + vector drawings). No Gemini calls.
  2. Sends the top pages (default 30) as images to Gemini, which describes the
     figure and transcribes formulas. Captions are saved to data/diagram_captions.json
     (safe to stop and re-run: finished pages are skipped).
  3. Appends each caption to the matching existing slide chunk in data/chunks.json,
     so the slide keeps its original citation/link. A backup is written first.

Run from the project folder, in this order:
    python diagrams.py --check      # shows chunk fields, finds the page field (0 calls)
    python diagrams.py --select     # prints the pages it would caption (0 calls)
    python diagrams.py              # captions pages with Gemini (about 30 calls)
    python diagrams.py --apply      # merges captions into chunks.json (0 calls)
    python embed_local.py           # rebuild embeddings, then restart the server
"""
import json
import os
import re
import shutil
import sys
import time

import pymupdf as fitz  # PyMuPDF (new import name; avoids the deprecation warning)

sys.stdout.reconfigure(encoding="utf-8")

DATA = "data"
CHUNKS = f"{DATA}/chunks.json"
CAPTIONS = f"{DATA}/diagram_captions.json"
PER_LECTURE = 5         # pages to caption per lecture (so every lecture is covered)
MIN_SCORE = 6           # ignore pages with almost no graphics
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
PAGE_KEYS = ("page", "slide", "slide_number", "page_number", "page_no", "slide_no")

PROMPT = """This is one lecture slide from an introductory machine learning course.
Describe ONLY what is visible, in 3 to 5 plain sentences, so that a student could answer questions
about the figure without seeing it:
- what kind of figure it is (plot, diagram, table, flowchart, geometric picture),
- axes, labels, legend, points, lines or regions and what they show,
- the main idea the figure illustrates.
Then write any formulas on the slide in plain text (for example: theta^T x + theta_0 = 0).
Do not add facts that are not on the slide. If the slide has no real figure, reply exactly NO_FIGURE."""


def load_env():
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"'))


def is_video(c):
    blob = " ".join(str(c.get(k, "")) for k in ("link", "url", "type", "kind", "source")).lower()
    return "youtu" in blob or "video" in blob or "transcript" in blob


def page_key(chunks):
    """Find which field holds the slide/page number in slide chunks."""
    slides = [c for c in chunks if not is_video(c)]
    for k in PAGE_KEYS:
        if slides and all(isinstance(c.get(k), int) for c in slides[:50]):
            return k
    # fall back: any int field other than lecture
    if slides:
        for k, v in slides[0].items():
            if isinstance(v, int) and k != "lecture":
                return k
    return None


def check():
    chunks = json.load(open(CHUNKS, encoding="utf-8"))
    slides = [c for c in chunks if not is_video(c)]
    print(f"Chunks: {len(chunks)} | detected slides: {len(slides)} | detected video: {len(chunks)-len(slides)}")
    print("   (README says 971 slides and 355 video windows)")
    if slides:
        ex = dict(slides[0])
        ex["text"] = ex.get("text", "")[:80] + "..."
        print("Example slide chunk:", json.dumps(ex, ensure_ascii=False, indent=2))
    print("Page field detected:", page_key(chunks))
    for i in range(1, 6):
        p = f"{DATA}/slides_0{i}.pdf"
        print(p, "found" if os.path.exists(p) else "MISSING")


def rank_pages():
    """Pick the best graphics pages of EACH lecture. Consecutive pages with graphics are
    usually one slide being built up step by step, so only one page per such run is kept."""
    ranked = []
    for lec in range(1, 6):
        path = f"{DATA}/slides_0{lec}.pdf"
        if not os.path.exists(path):
            print("missing", path)
            continue
        doc = fitz.open(path)
        cand = []
        for i, page in enumerate(doc):
            score = len(page.get_images(full=True)) * 20 + len(page.get_drawings())
            if score >= MIN_SCORE:
                cand.append((score, i + 1))                 # page numbers are 1-based
        cand.sort(key=lambda x: x[1])
        runs = []
        for sc, pg in cand:
            if runs and pg - runs[-1][-1][1] <= 1:
                runs[-1].append((sc, pg))
            else:
                runs.append([(sc, pg)])
        best = [max(run, key=lambda x: (x[0], x[1])) for run in runs]   # best page of each run
        best.sort(reverse=True)
        ranked += [(sc, lec, pg) for sc, pg in best[:PER_LECTURE]]
    return ranked


def select():
    pages = rank_pages()
    print(f"Selected {len(pages)} pages (score, lecture, page):")
    for s, lec, p in sorted(pages, key=lambda x: (x[1], x[2])):
        print(f"  lecture {lec}, page {p}  (graphics score {s})")


_client = None


def caption_image(png_bytes, retries=4):
    global _client
    key = os.environ.get("GOOGLE_API_KEY") or os.environ["GEMINI_API_KEY"]
    for attempt in range(retries):
        try:
            try:
                from google import genai
                from google.genai import types
                if _client is None:
                    _client = genai.Client(api_key=key)
                r = _client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[types.Part.from_bytes(data=png_bytes, mime_type="image/png"), PROMPT])
                return r.text.strip()
            except ImportError:
                import google.generativeai as old
                old.configure(api_key=key)
                r = old.GenerativeModel(GEMINI_MODEL).generate_content(
                    [{"mime_type": "image/png", "data": png_bytes}, PROMPT])
                return r.text.strip()
        except Exception as e:
            wait = 8 * (attempt + 1)
            print(f"   Gemini error ({str(e)[:90]}); retry in {wait}s")
            time.sleep(wait)
    return None


def run_captions():
    load_env()
    done = json.load(open(CAPTIONS, encoding="utf-8")) if os.path.exists(CAPTIONS) else {}
    pages = rank_pages()
    print(f"{len(pages)} pages selected, {len(done)} already captioned")
    for n, (score, lec, p) in enumerate(sorted(pages, key=lambda x: (x[1], x[2])), 1):
        key = f"{lec}:{p}"
        if key in done:
            continue
        print(f"[{n}/{len(pages)}] lecture {lec}, page {p}")
        doc = fitz.open(f"{DATA}/slides_0{lec}.pdf")
        png = doc[p - 1].get_pixmap(matrix=fitz.Matrix(1.6, 1.6)).tobytes("png")
        cap = caption_image(png)
        if cap is None:
            print("   skipped (Gemini failed)")
            continue
        done[key] = {"lecture": lec, "page": p, "caption": cap}
        json.dump(done, open(CAPTIONS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        time.sleep(2)
    usable = sum(1 for v in done.values() if not v["caption"].startswith("NO_FIGURE"))
    print(f"Done. {len(done)} captions saved ({usable} with a real figure) -> {CAPTIONS}")
    print("Next: python diagrams.py --apply")


def apply():
    chunks = json.load(open(CHUNKS, encoding="utf-8"))
    caps = json.load(open(CAPTIONS, encoding="utf-8"))
    pk = page_key(chunks)
    if not pk:
        print("Could not find the page field in slide chunks. Run --check and send me the output.")
        return
    shutil.copy(CHUNKS, f"{DATA}/chunks.backup.json")
    applied, created, missing = 0, 0, []
    for v in caps.values():
        if v["caption"].startswith("NO_FIGURE"):
            continue
        target = [c for c in chunks if not is_video(c)
                  and c.get("lecture") == v["lecture"] and c.get(pk) == v["page"]]
        if not target:
            # figure-only slide with no extracted text: create a new slide chunk in the same format
            chunks.append({"type": "slide", "lecture": v["lecture"], pk: v["page"],
                           "text": "[Figure on this slide: " + v["caption"].replace("\n", " ") + "]",
                           "source": f"Lecture {v['lecture']}, slide {v['page']}",
                           "has_figure_caption": True})
            created += 1
            continue
        c = target[0]
        if "[Figure on this slide:" in c["text"]:
            continue                                  # already applied
        c["text"] = c["text"].rstrip() + "\n[Figure on this slide: " + v["caption"].replace("\n", " ") + "]"
        c["has_figure_caption"] = True
        applied += 1
    json.dump(chunks, open(CHUNKS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Added figure captions to {applied} existing slide chunks and created {created} new chunks (backup: {DATA}/chunks.backup.json)")
    if missing:
        print("No matching chunk for:", ", ".join(missing))
    print("Next: python embed_local.py   then restart the server")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    elif "--select" in sys.argv:
        select()
    elif "--apply" in sys.argv:
        apply()
    else:
        run_captions()
