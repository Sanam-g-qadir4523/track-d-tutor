from youtube_transcript_api import YouTubeTranscriptApi

api = YouTubeTranscriptApi()
transcript = api.fetch("0xaLT4Svzgo")  # Lecture 1

lines = list(transcript)
for s in lines[:10]:
    print(round(s.start), "sec:", s.text)
print("Total lines:", len(lines))