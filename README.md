# Course Companion: a source-grounded study companion

Submission for the Multimodal AI Hackathon 2026, **Track D: Personalized Tutoring & Adaptive Learning**.

Course Companion turns lecture slides and lecture videos into one knowledge base in which every passage keeps its origin (slide number or video timestamp). It answers questions from that material with clickable citations, refuses or flags questions the material does not cover, writes verified practice questions, tracks what the student knows topic by topic, and produces a post-quiz report of weak topics and likely misconceptions.

Demo course: **MIT 6.036 Introduction to Machine Learning (Fall 2020), Lectures 1 to 5.**
The course material belongs to MIT and Prof. Tamara Broderick. It is not stored in this repository (see "Rebuilding the knowledge base").

A recorded walkthrough of the running system is linked in the Devpost submission, because the app runs on a local machine and cannot be opened from this page.

## What it does

| Area | What is built |
|---|---|
| Multimodal ingestion | Slide PDFs are read page by page. Videos are ingested from the YouTube link alone: the transcript is fetched automatically and cut into 60 second windows with start times. No manual copying. |
| Figures and diagrams | The slides with the most graphics are sent as images to Gemini, which describes the figure and transcribes formulas. The description is stored with the slide, so the tutor can answer from figures too (see "Figures and diagrams"). |
| Source links | Every chunk stores its origin. A citation opens the exact video second or the exact slide page. |
| Grounded tutor | Answers use only retrieved excerpts, with numbered citations. Off-course questions are refused. If the excerpts cover only part of a question, the tutor answers that part and says what is not covered. Answers can be given in English or Urdu. |
| Adaptive quiz | Multiple-choice questions written from lecture passages, each tagged with topic, difficulty and source. A second model call checks the answer key. Near-duplicate questions are rejected. |
| Learner model | Per-topic mastery estimated with Bayesian knowledge tracing, updated after every answer. A new student starts with a diagnostic pass over untested topics, then the quiz targets the weakest topic. |
| Post-quiz report | A report page lists mastery per topic, the weak topics, every wrong answer with the correct answer, the explanation and a link to the source slide, and a likely misconception per weak topic. |
| Web app | React interface with Overview, Ask, Practice and Progress screens, dark and light mode, and a lecture path in the sidebar. The report is served by the backend at `/report`. |

Numbers: 5 lectures, 971 slide pages, 355 video windows, 1,320 searchable chunks (965 slide chunks, 355 video chunks).

## Architecture

```
 Slide PDFs --PyMuPDF--+                       +--> chunks.json (text + lecture + slide/timestamp + link)
 YouTube link --transcript API--+              |
 Slide images --Gemini vision (diagrams.py)----+  (figure descriptions added to slide chunks)
                                               v
                         fastembed (BAAI/bge-small-en-v1.5, runs locally, 384 dims)
                                               |
 React app  <--HTTP-->  FastAPI server  --> retrieval: cosine similarity,
 (Vite)                 (server.py)            top 4 video windows + top 3 slides
                             |
                             +--> Gemini (gemini-3.5-flash-lite): grounded answer, quiz writing, answer check, misconception summary
                             +--> data/answers.json --> BKT --> mastery per topic --> /api/report
```

Files: `ingest.py` builds the chunks, `diagrams.py` adds figure descriptions, `embed_local.py` builds the vectors, `server.py` is the API, `report.html` is the report page, `frontend/` is the React app, `eval.py` evaluates retrieval and refusal, `eval_judge.py` evaluates answer quality with an LLM judge, `sim.py` runs simulated students, `ask.py`, `quiz.py` and `learner.py` are the original command-line versions.

## Grounding method

1. The question is embedded and compared with every chunk. The best 4 video windows and best 3 slides are kept, so explanations come from the spoken lecture and page references come from the slides.
2. **Refusal has two layers.** If the best match score is below 0.60 the question is refused without calling the language model. Otherwise the model is told to answer from the numbered excerpts, to say what the excerpts do not cover when they answer only part of the question, and to reply `NOT_IN_MATERIAL` only when the excerpts contain nothing relevant. The API tells the interface which layer refused (`low_score` or `model_declined`).
3. Each claim carries its excerpt number. In the interface the number is a link to the exact slide or video second.

An earlier, stricter prompt made the model refuse an in-course question whose excerpts used different words (a question about the "decision boundary" while the slides talk about the normal vector of a hyperplane). The prompt was loosened for this reason. The score threshold alone did not catch the case, because the retrieval score was high (0.80).

## Figures and diagrams

`diagrams.py` ranks slide pages by how much graphics they contain (embedded images and vector drawings), keeps one page per run of consecutive "build" slides, takes the top pages of each lecture, renders them as images and asks Gemini to describe the figure (axes, labels, what it shows) and to write formulas in plain text. The description is appended to the existing slide chunk as `[Figure on this slide: ...]`, so the slide keeps its citation and link, and embeddings are rebuilt.

Result: 46 pages were examined, **29 contained a real figure** and were added to the knowledge base; 17 were marked as having no figure and skipped.

Limits: this covers a selection of the most graphics-heavy slides, not all 971. The selection is a heuristic, and the descriptions were not checked one by one by a person. Textbook figures are not covered because no textbook was ingested.

## Learner model

Bayesian knowledge tracing per topic (one topic per lecture). Starting probability 0.30, learning rate 0.15, guess 0.25, slip 0.10. **These four values were chosen by hand, not fitted to data**, so mastery numbers are estimates. After each answer the posterior is updated, then the learning step is applied. Status bands: below 0.40 weak, below 0.75 getting there, otherwise strong.

Question selection: topics with no answers come first (diagnostic). After that, the topic with the lowest mastery is chosen. Difficulty follows mastery: easy below 0.40, medium below 0.75, hard above.

## Post-quiz report

`/report` (also `/api/report`) reads the stored answers. For each topic it shows the mastery estimate and status. For the weak and "getting there" topics it lists the most recent wrong answers with the option the student chose, the correct answer, the explanation and a link to the source. One extra model call turns the wrong answers into a **likely** misconception per topic. This summary is generated by the language model from a handful of wrong answers, so it is a hint and not a diagnosis. The result is cached until a new answer arrives. Answers saved before the report was added do not contain the question text and appear without it.

## Evaluation

### Retrieval and refusal (`eval.py`, no model calls)

Test set: 12 in-course questions with the expected lecture and a keyword that should appear in a retrieved passage, and 8 off-topic questions.

| Metric | Result |
|---|---|
| Retrieval hit rate (expected lecture and keyword among the 7 passages) | 92% (11 of 12) |
| Best passage is from the expected lecture | 83% |
| In-course questions allowed through at threshold 0.60 | 100% |
| Off-topic questions refused by the score check at threshold 0.60 | 100% (8 of 8) |

Threshold sweep (in-course allowed / off-topic refused): 0.30 gave 100% / 0%, 0.50 gave 100% / 62%, 0.55 and above gave 100% / 100%. The best-match scores of the off-topic questions were 0.41 to 0.54, and the figure captions added later did not push any of them over the threshold.

### Answer quality (`eval_judge.py`)

This is an **LLM-as-judge**, not RAGAS or DeepEval. For 10 of the in-course questions the system writes an answer from the retrieved excerpts, and Gemini then splits the answer into claims and checks each claim against the excerpts (faithfulness), and rates from 1 to 5 how directly the answer addresses the question (answer relevancy, scaled to 0 to 1). Context precision and recall are computed without a model.

| Metric | Result |
|---|---|
| Faithfulness (LLM judge) | 1.00 on the 9 answered questions |
| Answer relevancy (LLM judge, 0 to 1) | 1.00 on the 9 answered questions |
| Questions refused by the model although the material covers them | 1 of 10 |
| Context precision, share of the 7 passages from the expected lecture | 0.75 |
| Context precision, strict (right lecture and keyword present) | 0.52 |
| Context recall, proxy (right lecture and keyword among the passages) | 0.92 |

**How to read these numbers**
- The judge is the same model family that wrote the answers, so it tends to approve its own output. A score of 1.00 means the judge found no unsupported claim, not that the answers are perfect. No deliberately wrong answers were used to test whether the judge catches errors.
- The answer prompt in `eval_judge.py` is close to, but not identical to, the one in `server.py`.
- Precision and recall are proxies built from one expected lecture and one keyword per question, so a correct passage worded differently counts as a miss.
- The test set is small and was written after seeing the system's behaviour. The threshold was chosen on the same questions, so the 100% refusal figures are development-set results and will not hold exactly on new questions.
- At the first threshold (0.30) the score check refused 0 of 8 off-topic questions, so refusals then depended on the language model alone. Seeing this in the sweep is why the threshold was raised to 0.60.

### Personalization check with simulated students (`sim.py`)

`sim.py` simulates 300 students for each of three profiles (beginner, mixed, advanced), 30 questions each across 5 sessions. It compares the quiz's adaptive rule (untested topics first, then lowest estimated mastery) with picking a random topic. It does not use real questions or the language model. Students answer with a probability set by their true knowledge and learn a little after each question; both the learning rate (0.08 per question) and the student profiles are assumptions, not measurements.

| Profile | Policy | Mean knowledge gain | Gain on weakest topic | Mastery tracking error |
|---|---|---|---|---|
| Beginner | adaptive | 0.300 | 0.359 | 0.345 |
| Beginner | random | 0.308 | 0.353 | 0.261 |
| Mixed | adaptive | 0.215 | 0.352 | 0.260 |
| Mixed | random | 0.209 | 0.295 | 0.232 |
| Advanced | adaptive | 0.135 | 0.195 | 0.189 |
| Advanced | random | 0.136 | 0.185 | 0.189 |

Reading the result honestly: the adaptive rule did not raise overall knowledge gain in this simulation; the two policies are within noise on that measure. Its clearest benefit is on the topic a student starts weakest in, for mixed students (0.352 against 0.295). For beginner and mixed students the mastery estimate tracked true knowledge less closely under the adaptive rule than under random choice, which points at the hand-set tracing parameters. This is a check of the selection rule in a toy setting, not evidence that real students learn faster. Question repetition is 0 here by construction (each question comes from a different source passage). Repetition of near-identical wording was not measured.

## Known limitations

- **No textbook** was ingested. Only slides and videos, so the knowledge base is two of the three source types asked for.
- **Figures are covered only partly.** 29 of the most graphics-heavy slides have a model-written description; most slides do not. The descriptions were not reviewed one by one. Many slide formulas are still extracted as broken symbols unless they were on a captioned slide.
- **Topic tags are one topic per lecture**, not concept-level tags, and the course path follows lecture order rather than a mined prerequisite graph.
- **Quizzes are multiple choice only.** There are no short-answer or numerical questions.
- Quiz answer keys are checked by the same model that wrote the question, which catches some errors but not all. Some answer options are awkwardly worded.
- The quiz can stay on one weak topic for several questions in a row.
- Personalization has only been checked in a toy simulation (see above), not with real students, and the rate of near-duplicate questions has not been measured. The duplicate check itself (embedding similarity above 0.88 is rejected) is implemented.
- Answer-quality metrics come from an LLM judge of the same model family, on 10 questions, not from RAGAS or a similar framework.
- The post-quiz report is a separate page served by the backend, not a screen inside the React app, and its misconceptions are model-written hints.
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
3. Optional, figures: run `python diagrams.py --select` to see the chosen pages, `python diagrams.py` to caption them with Gemini (about 45 calls), then `python diagrams.py --apply`.
4. Run `python embed_local.py` (builds `data/embeddings.npy`). Run it again after step 3.
5. Start the backend with `uvicorn server:app --port 8000` and, in a second terminal, the interface with `cd frontend && npm run dev`. Then type `127.0.0.1:5173` into a browser address bar. This address only works on the computer where the app is running, so it is deliberately not a clickable link and will not open from GitHub. On Windows, `start.bat` starts both and opens the page. The report page is at `localhost:8000/report` on the same computer.
6. Optional: `python eval.py` reproduces the retrieval and refusal table, `python eval_judge.py` runs the answer-quality judge (about 20 Gemini calls), `python sim.py` runs the simulated students.
