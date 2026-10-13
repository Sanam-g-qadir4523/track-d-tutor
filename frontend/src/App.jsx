import { useCallback, useEffect, useRef, useState } from "react";
import "./index.css";

const API = "http://localhost:8000";
// TrackDTutorUI v4

const VIDEOS = {
  1: "0xaLT4Svzgo",
  2: "A3obZhw7Jc4",
  3: "WZVNvfMdk-E",
  4: "abB3fwfPy14",
  5: "OpvrwhWEUmY",
};

async function api(path, options) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    let detail = "Something went wrong";
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

// "Lecture 2, video 3:26" -> ["Lecture 2", "video 3:26"]
function where(label) {
  const i = label.indexOf(", ");
  return i < 0 ? [label, ""] : [label.slice(0, i), label.slice(i + 2)];
}

function Timecode({ source, children }) {
  const [lec, at] = where(source.label);
  const isVideo = source.type ? source.type === "video" : at.startsWith("video");
  const short = at.replace("video ", "");
  return (
    <a className={"tc " + (isVideo ? "tc-video" : "tc-slide")} href={source.url} target="_blank" rel="noreferrer">
      <span className="tc-icon" aria-hidden="true" />
      <span className="tc-lec">{lec.replace("Lecture ", "L")}</span>
      <span className="tc-at">{short}</span>
      {children}
    </a>
  );
}

function Answer({ text, sources, urdu }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className={"answer-text" + (urdu ? " urdu" : "")} dir={urdu ? "rtl" : "ltr"}>
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (!m) return <span key={i}>{p}</span>;
        const s = sources.find((x) => x.n === Number(m[1]));
        return s ? (
          <a key={i} className="mark" href={s.url} target="_blank" rel="noreferrer" title={s.label}>
            {m[1]}
          </a>
        ) : (
          <span key={i}>{p}</span>
        );
      })}
    </p>
  );
}

const svgProps = {
  viewBox: "0 0 24 24",
  width: 20,
  height: 20,
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

const ICONS = {
  home: (
    <svg {...svgProps}>
      <path d="M4 11.5 12 4l8 7.5V20h-5v-5H9v5H4z" />
    </svg>
  ),
  ask: (
    <svg {...svgProps}>
      <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
    </svg>
  ),
  quiz: (
    <svg {...svgProps}>
      <rect x="4" y="3" width="16" height="18" rx="2.5" />
      <path d="M8 9h8M8 13h8M8 17h4" />
    </svg>
  ),
  dash: (
    <svg {...svgProps}>
      <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" />
    </svg>
  ),
  sun: (
    <svg {...svgProps}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
  moon: (
    <svg {...svgProps}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
    </svg>
  ),
};

const STATUS_TEXT = {
  weak: "Needs revision",
  ok: "Getting there",
  strong: "Strong",
  "not tested": "Not tried yet",
};

function Ring({ value, status, label, size = 44 }) {
  const r = size / 2 - 4;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value ?? 0));
  return (
    <svg className={"ring s-" + status.replace(" ", "-")} width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth="4" />
      <circle
        className="ring-fill"
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - v)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="ring-text">
        {label}
      </text>
    </svg>
  );
}

function Sidebar({ tab, setTab, data, online, theme, toggleTheme }) {
  return (
    <aside className="side">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div>
          <h1>Course Companion</h1>
          <p>MIT 6.036, Lectures 1 to 5</p>
        </div>
      </div>

      <nav className="menu">
        {[
          ["overview", "Overview", ICONS.home],
          ["chat", "Ask", ICONS.ask],
          ["quiz", "Practice", ICONS.quiz],
          ["dash", "Progress", ICONS.dash],
        ].map(([k, label, icon]) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {icon}
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="spine">
        <h2>Your course path</h2>
        <ol>
          {(data?.topics ?? []).map((t, i) => (
            <li key={t.topic} className={"spine-item s-" + t.status.replace(" ", "-")}>
              <Ring value={t.mastery} status={t.status} label={String(i + 1)} />
              <div>
                <strong>{t.topic}</strong>
                <span>{STATUS_TEXT[t.status]}</span>
              </div>
            </li>
          ))}
          {!data && <li className="spine-empty">Progress appears here once the tutor is online.</li>}
        </ol>
      </div>

      <button className="theme-btn" onClick={toggleTheme}>
        {theme === "dark" ? ICONS.sun : ICONS.moon}
        <span>{theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}</span>
      </button>

      <div className={"conn " + (online ? "on" : "off")}>
        <span className="conn-dot" />
        {online ? "Tutor online" : "Tutor offline. Start the server on port 8000."}
      </div>
    </aside>
  );
}

function Overview({ data, setTab }) {
  if (!data) {
    return (
      <section className="page">
        <div className="page-head">
          <div>
            <p className="eyebrow">Overview</p>
            <h2>Welcome back</h2>
          </div>
        </div>
        <div className="notice error">
          <strong>The tutor server is offline</strong>
          <p>Double-click start.bat in the project folder. This page fills in once the server is running.</p>
        </div>
      </section>
    );
  }
  const total = data.total_answers;
  const right = data.topics.reduce((a, t) => a + t.right, 0);
  const pct = total ? Math.round((100 * right) / total) : 0;
  const tested = data.topics.filter((t) => t.asked > 0);
  const untested = data.topics.filter((t) => t.asked === 0);
  const weakest = tested.length ? [...tested].sort((a, b) => a.mastery - b.mastery)[0] : null;
  const next = untested.length ? untested[0].topic : weakest ? weakest.topic : "Take a quiz";

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Overview</p>
          <h2>Welcome back</h2>
          <p className="muted">Your course at a glance. Pick a lecture to watch, read, or practise.</p>
        </div>
        <button className="primary" onClick={() => setTab("quiz")}>Practise now</button>
      </div>

      <div className="stats">
        <div className="stat">
          <span className="label">Questions answered</span>
          <strong>{total}</strong>
        </div>
        <div className="stat">
          <span className="label">Answered correctly</span>
          <strong>
            {pct}
            <small>%</small>
          </strong>
        </div>
        <div className="stat">
          <span className="label">{untested.length ? "Try next" : "Revise next"}</span>
          <strong className="text">{next}</strong>
        </div>
      </div>

      <h3 className="section-title">The lectures</h3>
      <div className="lec-list">
        {data.topics.map((t, i) => {
          const n = i + 1;
          return (
            <div key={t.topic} className={"lec-row s-" + t.status.replace(" ", "-")}>
              <Ring value={t.mastery} status={t.status} label={String(n)} size={56} />
              <div className="grow">
                <h3>{t.topic}</h3>
                <p className="lec-status">{STATUS_TEXT[t.status]}</p>
                <p className="muted small">
                  {t.asked ? `${t.right} of ${t.asked} correct. Mastery ${t.mastery}.` : "No questions yet."}
                </p>
              </div>
              <div className="lec-actions">
                <a className="btn-ghost" href={`https://youtu.be/${VIDEOS[n]}`} target="_blank" rel="noreferrer">
                  Watch lecture
                </a>
                <a className="btn-ghost" href={`${API}/slides/${n}`} target="_blank" rel="noreferrer">
                  Slides
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

const SUGGESTIONS = [
  { q: "What is a perceptron?", tag: "Lecture 2" },
  { q: "What is linear regression?", tag: "Lecture 5" },
  { q: "Why do we use regularization?", tag: "Lectures 4 and 5" },
  { q: "Who won the cricket world cup?", tag: "Off topic, to see how it refuses" },
];

function Chat() {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState("en");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  async function send(q) {
    const question = (q ?? text).trim();
    if (!question || busy) return;
    setText("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    try {
      const d = await api("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, lang }),
      });
      setMsgs((m) => [...m, { role: "bot", lang, ...d }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "error", text: e.message }]);
    }
    setBusy(false);
  }

  return (
    <section className="chat">
      <div className="thread">
        {msgs.length === 0 && (
          <div className="hero">
            <p className="eyebrow">Grounded in the lectures</p>
            <h2>What would you like to understand?</h2>
            <p className="hero-sub">
              Every answer is built only from the slides and videos. The yellow numbers open the
              exact slide, or the video at that second. You can ask for the explanation in Urdu too.
            </p>
            <div className="cards">
              {SUGGESTIONS.map((s) => (
                <button key={s.q} className="card" onClick={() => send(s.q)}>
                  <span className="card-tag">{s.tag}</span>
                  <span className="card-q">{s.q}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} className={"turn " + m.role}>
            {m.role === "user" && <p className="question">{m.text}</p>}

            {m.role === "error" && (
              <div className="notice error">
                <strong>The tutor could not answer</strong>
                <p>{m.text}</p>
                <p className="hint">Make sure the server window is open (port 8000), then ask again.</p>
              </div>
            )}

            {m.role === "bot" && m.refused && (
              <div className="notice refused">
                <span className="notice-tag">Outside the course</span>
                <p className={m.lang === "ur" ? "urdu" : ""} dir={m.lang === "ur" ? "rtl" : "ltr"}>{m.answer}</p>
                <p className="hint">The closest passage matched at {m.best_score}, which is not enough to answer from.</p>
              </div>
            )}

            {m.role === "bot" && !m.refused && (
              <article className="reply">
                <Answer text={m.answer} sources={m.sources} urdu={m.lang === "ur"} />
                <div className="sources">
                  <h3>Sources</h3>
                  <div className="tcs">
                    {m.sources.map((s) => (
                      <Timecode key={s.n} source={s}>
                        <span className="tc-n">{s.n}</span>
                      </Timecode>
                    ))}
                  </div>
                </div>
              </article>
            )}
          </div>
        ))}

        {busy && (
          <div className="working">
            <span className="pulse" />
            <span className="pulse" />
            <span className="pulse" />
            Searching the lectures
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="composer">
        <div className="seg" role="group" aria-label="Answer language">
          <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>English</button>
          <button className={lang === "ur" ? "on" : ""} onClick={() => setLang("ur")}>اردو</button>
        </div>
        <div className="composer-row">
          <input
            value={text}
            dir={lang === "ur" ? "auto" : "ltr"}
            placeholder={lang === "ur" ? "Ask in English or Urdu. The answer will be in Urdu." : "Ask about perceptrons, regression, regularization..."}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button className="primary" onClick={() => send()} disabled={busy || !text.trim()}>
            Ask
          </button>
        </div>
      </div>
    </section>
  );
}

function Quiz({ onAnswered }) {
  const [q, setQ] = useState(null);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [score, setScore] = useState({ right: 0, total: 0 });

  async function next() {
    setLoading(true);
    setError("");
    setPicked(null);
    setResult(null);
    setQ(null);
    try {
      setQ(await api("/api/quiz/next"));
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }

  async function choose(i) {
    if (result || !q) return;
    setPicked(i);
    try {
      const r = await api("/api/quiz/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: q.id, choice: i }),
      });
      setResult(r);
      setScore((s) => ({ right: s.right + (r.correct ? 1 : 0), total: s.total + 1 }));
      onAnswered();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Adaptive practice</p>
          <h2>Practice quiz</h2>
          <p className="muted">
            New topics come first. After that, every question targets the topic you know least.
          </p>
        </div>
        <div className="tally">
          <strong>
            {score.right}
            <small>/{score.total}</small>
          </strong>
          <span>correct this session</span>
        </div>
      </div>

      {!q && !loading && (
        <button className="primary big" onClick={next}>
          {score.total ? "Next question" : "Start the quiz"}
        </button>
      )}
      {loading && (
        <div className="working">
          <span className="pulse" />
          <span className="pulse" />
          <span className="pulse" />
          Writing and checking a question. This can take up to 30 seconds.
        </div>
      )}
      {error && (
        <div className="notice error">
          <strong>No question this time</strong>
          <p>{error}</p>
          <button className="linkish" onClick={next}>Try again</button>
        </div>
      )}

      {q && (
        <div className="qcard">
          <div className="qmeta">
            <span className="chip topic">{q.topic}</span>
            <span className={"chip diff d-" + q.difficulty}>{q.difficulty}</span>
            <span className="why">{q.reason}</span>
          </div>
          <h3 className="qtext">{q.question}</h3>
          <div className="options">
            {q.options.map((o, i) => {
              let cls = "option";
              if (result) {
                if (i === result.correct_index) cls += " right";
                else if (i === picked) cls += " wrong";
              }
              return (
                <button key={i} className={cls} onClick={() => choose(i)} disabled={!!result}>
                  <span className="letter">{"ABCD"[i]}</span>
                  <span>{o}</span>
                </button>
              );
            })}
          </div>
          {result && (
            <div className={"feedback " + (result.correct ? "ok" : "bad")}>
              <strong>{result.correct ? "Correct" : "Not quite"}</strong>
              <p>{result.explanation}</p>
              <div className="fb-row">
                <Timecode source={{ ...result.source, type: "video" }} />
                <span className="muted">Hear it explained in the lecture</span>
              </div>
              <button className="primary" onClick={next}>Next question</button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Dashboard({ data }) {
  if (!data) {
    return (
      <section className="page">
        <div className="notice error">
          <strong>Progress is not available</strong>
          <p>The tutor server is offline. Start it on port 8000 and this page will fill in.</p>
        </div>
      </section>
    );
  }
  const tested = data.topics.filter((t) => t.asked > 0);
  const untested = data.topics.filter((t) => t.asked === 0);
  const weakest = tested.length ? [...tested].sort((a, b) => a.mastery - b.mastery)[0] : null;

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Learner model</p>
          <h2>Your progress</h2>
          <p className="muted">
            Mastery is estimated per topic and updates after every answer. {data.total_answers} answers so far.
          </p>
        </div>
      </div>

      <div className="focus">
        <span className="focus-tag">Next step</span>
        {untested.length > 0 ? (
          <p>Try <strong>{untested[0].topic}</strong>. No questions have been asked on it yet.</p>
        ) : (
          weakest && <p>Revise <strong>{weakest.topic}</strong>. It has your lowest mastery ({weakest.mastery}).</p>
        )}
      </div>

      <div className="lectures">
        {data.topics.map((t, i) => (
          <div key={t.topic} className={"lecture s-" + t.status.replace(" ", "-")}>
            <Ring value={t.mastery} status={t.status} label={String(i + 1)} size={64} />
            <div>
              <h3>{t.topic}</h3>
              <p className="lec-status">{STATUS_TEXT[t.status]}</p>
              <p className="muted">
                {t.asked ? `${t.right} of ${t.asked} correct. Mastery ${t.mastery}.` : "No questions yet."}
              </p>
            </div>
          </div>
        ))}
      </div>

      <h3 className="section-title">Recent answers</h3>
      <div className="recent">
        {data.recent.length === 0 && <p className="muted">Answer a quiz question and it will appear here.</p>}
        {data.recent.map((r, i) => (
          <div key={i} className="recent-row">
            <span className={"verdict " + (r.correct ? "ok" : "bad")}>{r.correct ? "Right" : "Missed"}</span>
            <span className="r-topic">{r.topic}</span>
            <span className="r-src">{r.source}</span>
          </div>
        ))}
      </div>
      <p className="fineprint">
        Mastery uses a simple knowledge-tracing model whose starting values were chosen by hand, so read the
        numbers as estimates.
      </p>
    </section>
  );
}

function initialTheme() {
  try {
    const saved = localStorage.getItem("theme");
    if (saved === "dark" || saved === "light") return saved;
  } catch {}
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [tab, setTab] = useState("overview");
  const [data, setData] = useState(null);
  const [online, setOnline] = useState(false);
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("theme", theme);
    } catch {}
  }, [theme]);

  const refresh = useCallback(async () => {
    try {
      setData(await api("/api/mastery"));
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="shell">
      <Sidebar
        tab={tab}
        setTab={setTab}
        data={data}
        online={online}
        theme={theme}
        toggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
      />
      <main>
        {tab === "overview" && <Overview data={data} setTab={setTab} />}
        {tab === "chat" && <Chat />}
        {tab === "quiz" && <Quiz onAnswered={refresh} />}
        {tab === "dash" && <Dashboard data={data} />}
      </main>
    </div>
  );
}
