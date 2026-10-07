import json
import os
import pymupdf
from youtube_transcript_api import YouTubeTranscriptApi

VIDEOS = {
    1: "0xaLT4Svzgo",
    2: "A3obZhw7Jc4",
    3: "WZVNvfMdk-E",
    4: "abB3fwfPy14",
    5: "OpvrwhWEUmY",
}

api = YouTubeTranscriptApi()
chunks = []


def clean(text):
    lines = []
    for line in (text or "").splitlines():
        if "latexit" in line or len(line) > 200:
            continue
        lines.append(line.strip())
    return "\n".join(l for l in lines if l).strip()


def stamp(sec):
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


def add_video_chunk(n, vid, start, texts):
    chunks.append({
        "type": "video",
        "lecture": n,
        "start_sec": int(start),
        "text": " ".join(texts),
        "source": f"Lecture {n}, video {stamp(start)}",
        "url": f"https://youtu.be/{vid}?t={int(start)}",
    })


for n, vid in VIDEOS.items():
    # 1) Slides
    path = f"data/slides_0{n}.pdf"
    if os.path.exists(path):
        try:
            doc = pymupdf.open(path)
            total = len(doc)
            skipped = []
            for i in range(total):
                try:
                    text = clean(doc[i].get_text())
                except Exception:
                    skipped.append(i + 1)
                    continue
                if len(text) > 20:
                    chunks.append({
                        "type": "slide",
                        "lecture": n,
                        "slide": i + 1,
                        "text": text,
                        "source": f"Lecture {n}, slide {i + 1}",
                    })
            print(f"Lecture {n}: slides read ({total} pages, {len(skipped)} skipped: {skipped})")
        except Exception as e:
            print(f"Lecture {n}: PDF failed: {e}")
    else:
        print(f"Lecture {n}: {path} NOT FOUND")

    # 2) Video transcript
    try:
        lines = list(api.fetch(vid))
    except Exception as e:
        print(f"Lecture {n}: transcript failed: {e}")
        continue
    window, start = [], None
    for s in lines:
        if start is None:
            start = s.start
        window.append(s.text.replace("\n", " "))
        if s.start - start >= 60:
            add_video_chunk(n, vid, start, window)
            window, start = [], None
    if window:
        add_video_chunk(n, vid, start, window)
    print(f"Lecture {n}: transcript read ({len(lines)} lines)")

with open("data/chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

slides = sum(1 for c in chunks if c["type"] == "slide")
videos = sum(1 for c in chunks if c["type"] == "video")
print(f"DONE. Total chunks: {len(chunks)} (slides: {slides}, video: {videos})")