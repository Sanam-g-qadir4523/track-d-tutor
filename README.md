# Course Companion: a source-grounded study companion

Submission for the Multimodal AI Hackathon 2026, **Track D: Personalized Tutoring & Adaptive Learning**.

Course Companion turns lecture slides and lecture videos into one knowledge base in which every passage keeps its origin (slide number or video timestamp). It answers questions from that material with clickable citations, refuses questions the material does not cover, writes verified practice questions, and tracks what the student knows topic by topic.

Demo course: **MIT 6.036 Introduction to Machine Learning (Fall 2020), Lectures 1 to 5.**
The course material belongs to MIT and Prof. Tamara Broderick. It is not stored in this repository (see "Rebuilding the knowledge base").

A recorded walkthrough of the running system is linked in the Devpost submission, because the app runs on a local machine and cannot be opened from this page.

## What it does

| Area | What is built |
|---|---|
| Multimodal ingestion | Slide PDFs are read page by page. Videos are ingested from the YouTube link alone: the transcript is fetched automatically and cut into 60 second windows with start times. No manual copying. |
| Source links | Every chunk stores its origin. A citation opens the exact video second or the exact slide page. |
| Grounded tutor | Answers use only retrieved excerpts, with numbered citations. Off-course questions are refused. Answers can be given in English or Urdu. |
| Adaptive quiz | Multiple-choice questions written from lecture passages, each tagged with topic, difficulty and source. A second model call checks the answer key. Near-duplicate questions are rejected. |
| Learner model | Per-topic mastery estimated with Bayesian knowledge tracing, updated after every answer. A new student starts with a diagnostic pass over untested topics, then the quiz targets the weakest topic. |
| Web app | React interface with Overview, Ask, Practice and Progress screens, dark and light mode, and a lecture path in the sidebar. |

Numbers: 5 lectures, 971 slide pages, 355 video windows, 1,320 searchable chunks.

## Architecture

```
 Slide PDFs --PyMuPDF--+
                       +--> chunks.json (text + lecture + slide/timestamp + link)
 YouTube link --transcript API--+            |
                                             v
                         fastembed (BAAI/bge-small-en-v1.5, runs locally, 384 dims)
                                             |
 React app  <--HTTP-->  FastAPI server  --> retrieval: cosine similarity,
 (Vite)                 (server.py)            top 4 video windows + top 3 slides
                             |
                             +--> Gemini (gemini-3.5-flash-lite): grounded answer, quiz writing, answer check
                             +--> data/answers.json --> BKT --> mastery per topic
```

Files: `ingest.py` builds the chunks, `embed_local.py` builds the vectors, `server.py` is the API, `frontend/` is the React app, `eval.py` runs the evaluation, `ask.py`, `quiz.py` and `learner.py` are the original command-line versions.

## Grounding method

1. The question is embedded and compared with every chunk. The best 4 video windows and best 3 slides are kept, so explanations come from the spoken lecture and page references come from the slides.
2. **Refusal has two layers.** If the best match score is below 0.60 the question is refused without calling the language model. Otherwise the model is told to answer only from the numbered excerpts and to reply `NOT_IN_MATERIAL` when they do not contain the answer.
3. Each claim carries its excerpt number. In the interface the number is a link to the exact slide or video second.

## Learner model

Bayesian knowledge tracing per topic (one topic per lecture). Starting probability 0.30, learning rate 0.15, guess 0.25, slip 0.10. **These four values were chosen by hand, not fitted to data**, so mastery numbers are estimates. After each answer the posterior is updated, then the learning step is applied. Status bands: below 0.40 weak, below 0.75 getting there, otherwise strong.

Question selection: topics with no answers come first (diagnostic). After that, the topic with the lowest mastery is chosen. Difficulty follows mastery: easy below 0.40, medium below 0.75, hard above.

## Evaluation

`eval.py` runs without any language model calls. Test set: 12 in-course questions with the expected lecture and a keyword that should appear in a retrieved passage, and 8 off-topic questions.

| Metric | Result |
|---|---|
| Retrieval hit rate (expected lecture and keyword among the 7 passages) | 92% (11 of 12) |
| Best passage is from the expected lecture | 83% |
| In-course questions allowed through at threshold 0.60 | 100% |
| Off-topic questions refused by the score check at threshold 0.60 | 100% (8 of 8) |

Threshold sweep (in-course allowed / off-topic refused): 0.30 gave 100% / 0%, 0.50 gave 100% / 62%, 0.55 and above gave 100% / 100%.

**What this does and does not show**

- At the first threshold (0.30) the score check refused 0 of 8 off-topic questions. Refusals at that point depended on the language model alone. Seeing this in the sweep is why the threshold was raised to 0.60.
- The test set is small and was written after seeing the system's behaviour, and the threshold was chosen on the same questions. The 100% figures are development-set results and will not hold exactly on new questions.
- Passage matching uses a lecture number plus one keyword, so it can miss a correct passage that words the idea differently.

## Personalization check with simulated students

`sim.py` simulates 300 students for each of three profiles (beginner, mixed, advanced), 30 questions each across 5 sessions. It compares the quiz's adaptive rule (untested topics first, then lowest estimated mastery) with picking a random topic. It does not use real questions or the language model. Students answer with a probability set by their true knowledge and learn a little after each question; **both the learning rate (0.08 per question) and the student profiles are assumptions**, not measurements.

| Profile | Policy | Mean knowledge gain | Gain on weakest topic | Mastery tracking error |
|---|---|---|---|---|
| Beginner | adaptive | 0.300 | 0.359 | 0.345 |
| Beginner | random | 0.308 | 0.353 | 0.261 |
| Mixed | adaptive | 0.215 | 0.352 | 0.260 |
| Mixed | random | 0.209 | 0.295 | 0.232 |
| Advanced | adaptive | 0.135 | 0.195 | 0.189 |
| Advanced | random | 0.136 | 0.185 | 0.189 |

**Reading the result honestly:** the adaptive rule did not raise overall knowledge gain in this simulation; the two policies are within noise on that measure. Its clearest benefit is on the topic a student starts weakest in, for mixed students (0.352 against 0.295). For beginner and mixed students the mastery estimate tracked true knowledge less closely under the adaptive rule than under random choice, which points at the hand-set tracing parameters. This is a check of the selection rule in a toy setting, not evidence that real students learn faster. Question repetition is 0 here by construction (each question comes from a different source passage). Repetition of near-identical wording was not measured.

## Known limitations

- **No formal answer-quality metrics yet.** Faithfulness, answer relevancy and context recall were not measured with RAGAS or a similar framework. Only retrieval and refusal were measured.
- **Personalization has only been checked in a toy simulation** (see above), not with real students, and the rate of near-duplicate questions has not been measured. The duplicate check itself (embedding similarity above 0.88 is rejected) is implemented.
- **Slide formulas and diagrams.** Text extraction turns many formulas into broken symbols, and figures are not read, so the requirement to use information from images and diagrams is not met.
- **No textbook** was ingested. Only slides and videos.
- Quiz answer keys are checked by the same model that wrote the question, which catches some errors but not all. Some answer options are awkwardly worded.
- The quiz can stay on one weak topic for several questions in a row.
- Topic tags are one topic per lecture, not concept-level tags, and the course path follows lecture order rather than a mined prerequisite graph.
- Urdu answers are written by the language model and their quality has not been reviewed by a fluent reader.
- The free Gemini tier has request limits, so heavy use can return a temporary error.

## Running it

Requirements: Python 3.13, Node 20, a Gemini API key from Google AI Studio.

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Create a file named `.env` containing `GEMINI_API_KEY=your_key`. Never commit it.

## Rebuilding the knowledge base

The course material is not included in this repository. To rebuild it:

1. Download the five slide PDFs from Prof. Broderick's 6.036 Fall 2020 page (https://tamarabroderick.com/ml.html) into `data/` as `slides_01.pdf` to `slides_05.pdf`.
2. Run `python ingest.py` (fetches the five video transcripts automatically, builds `data/chunks.json`).
3. Run `python embed_local.py` (builds `data/embeddings.npy`).
4. Start the backend with `uvicorn server:app --port 8000` and, in a second terminal, the interface with `cd frontend && npm run dev`. Then open http://127.0.0.1:5173 in a browser. This address only works on the computer where the app is running, so it will not open from GitHub. On Windows, `start.bat` starts both and opens the page.
5. Optional: `python eval.py` reproduces the evaluation table.
