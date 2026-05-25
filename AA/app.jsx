/* global React, ReactDOM */
const { useState, useEffect, useRef, useMemo } = React;

/* ============================================================
   Modus — v1 capture-to-SOP loop
   GT Parking & Transportation, Weekend Appeal Workflow
   ============================================================ */

/* ---------- Icons (simple line, never decorative) ---------- */
const Icon = {
  Text: () => (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.2">
      <rect x="3" y="4" width="16" height="14" rx="1" />
      <line x1="6" y1="8" x2="16" y2="8" />
      <line x1="6" y1="11" x2="16" y2="11" />
      <line x1="6" y1="14" x2="12" y2="14" />
    </svg>
  ),
  Mic: () => (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.2">
      <rect x="8" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a6 6 0 0 0 12 0" />
      <line x1="11" y1="17" x2="11" y2="20" />
    </svg>
  ),
  Doc: () => (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.2">
      <path d="M5 3h8l4 4v12H5z" />
      <path d="M13 3v4h4" />
      <line x1="8" y1="11" x2="14" y2="11" />
      <line x1="8" y1="14" x2="14" y2="14" />
    </svg>
  ),
  Screen: () => (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.2">
      <rect x="3" y="4" width="16" height="11" rx="1" />
      <line x1="7" y1="19" x2="15" y2="19" />
      <line x1="11" y1="15" x2="11" y2="19" />
      <circle cx="11" cy="9.5" r="2" />
    </svg>
  ),
  Arrow: () => (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="3" y1="7" x2="11" y2="7" />
      <polyline points="7,3 11,7 7,11" />
    </svg>
  ),
  Back: () => (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="11" y1="7" x2="3" y2="7" />
      <polyline points="7,3 3,7 7,11" />
    </svg>
  ),
  Plus: () => (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.4">
      <line x1="6" y1="2" x2="6" y2="10" />
      <line x1="2" y1="6" x2="10" y2="6" />
    </svg>
  ),
};

/* ---------- Topbar ---------- */
function Topbar({ dept = "GT — Parking & Transportation" }) {
  return (
    <div className="topbar">
      <div className="brand">
        <div className="mark" />
        <div className="name">Modus</div>
        <div className="dept">{dept}</div>
      </div>
      <div className="topbar-right">
        <div className="meta">v0.4.2 · staging</div>
        <div className="user">
          <span>D. Okafor</span>
          <div className="avatar">DO</div>
        </div>
      </div>
    </div>
  );
}

function Subbar({ crumbs }) {
  return (
    <div className="subbar">
      {crumbs.map((c, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="sep">/</span>}
          <span className={"crumb" + (i === crumbs.length - 1 ? " active" : "")}>{c}</span>
        </React.Fragment>
      ))}
      <div className="right">
        <span>autosaved · 2s ago</span>
      </div>
    </div>
  );
}

/* ============================================================
   SCREEN 1 — CAPTURE
   ============================================================ */
function ScreenCapture({ state, setState, onNext }) {
  const modalities = [
    { id: "text",   icon: <Icon.Text/>,   title: "Typed description", desc: "Describe the workflow in your own words.", tag: "TEXT" },
    { id: "voice",  icon: <Icon.Mic/>,    title: "Voice walkthrough", desc: "Record or upload audio talking through it.", tag: "AUDIO" },
    { id: "docs",   icon: <Icon.Doc/>,    title: "Supporting documents", desc: "Existing SOPs, manuals, policy PDFs.", tag: "FILES" },
    { id: "screen", icon: <Icon.Screen/>, title: "Screen recording",   desc: "Record yourself doing the work end-to-end.", tag: "VIDEO" },
  ];

  const canSubmit = state.name && state.dept && state.modality && (
    (state.modality === "text" && state.text.trim().length > 40) ||
    state.modality !== "text"
  );

  return (
    <div className="app">
      <Topbar />
      <Subbar crumbs={["Workflows", "New capture", state.name || "Untitled"]} />
      <div className="workarea">
        <div className="canvas">
          <div className="step-eyebrow">
            <span className="num">01 / 04</span>
            <span>Capture</span>
          </div>
          <h1 className="page-title">Tell Modus how this workflow gets done.</h1>
          <p className="page-sub">
            Any modality is fine — voice, documents, screen recording, or typed. The extraction model
            reads everything you provide, then asks clarifying questions to fill the gaps.
          </p>

          {/* Name + dept */}
          <div className="field-row">
            <div className="field-label">
              Workflow name<span className="req">*</span>
              <span className="hint">Short, descriptive. Will appear in the SOP header.</span>
            </div>
            <div className="field-control">
              <input
                className="text-input"
                placeholder="e.g. Weekend Citation Appeal — >$200"
                value={state.name}
                onChange={(e) => setState({ ...state, name: e.target.value })}
              />
            </div>
          </div>

          <div className="field-row">
            <div className="field-label">
              Department<span className="req">*</span>
              <span className="hint">Captures join this department's knowledge pool.</span>
            </div>
            <div className="field-control">
              <select
                className="text-input"
                value={state.dept}
                onChange={(e) => setState({ ...state, dept: e.target.value })}
              >
                <option value="">Select department</option>
                <option>Parking & Transportation</option>
                <option>Housing</option>
                <option>Dining Services</option>
                <option>Campus Recreation</option>
                <option>Facilities</option>
              </select>
            </div>
          </div>

          <div className="field-row">
            <div className="field-label">
              Input modality<span className="req">*</span>
              <span className="hint">Pick one to start. You can add supporting documents to any modality.</span>
            </div>
            <div className="field-control">
              <div className="modality-grid">
                {modalities.map((m) => (
                  <button
                    key={m.id}
                    className={"modality" + (state.modality === m.id ? " selected" : "")}
                    onClick={() => setState({ ...state, modality: m.id })}
                  >
                    <span className="m-tag">{m.tag}</span>
                    <span className="icon">{m.icon}</span>
                    <span className="m-title">{m.title}</span>
                    <span className="m-desc">{m.desc}</span>
                  </button>
                ))}
              </div>

              {state.modality && (
                <div className="input-pane">
                  <div className="input-pane-head">
                    <span className="label">
                      {state.modality === "text" && "TYPED DESCRIPTION"}
                      {state.modality === "voice" && "VOICE WALKTHROUGH"}
                      {state.modality === "docs" && "SUPPORTING DOCUMENTS"}
                      {state.modality === "screen" && "SCREEN RECORDING"}
                    </span>
                    <span className="label" style={{color: "var(--muted-2)"}}>OPTIONAL · ADD MORE BELOW</span>
                  </div>
                  {state.modality === "text" && (
                    <textarea
                      className="text-input"
                      placeholder="Walk through what happens, step by step. Don't worry about structure — Modus will ask follow-up questions to fill in gaps."
                      value={state.text}
                      onChange={(e) => setState({ ...state, text: e.target.value })}
                    />
                  )}
                  {state.modality === "voice" && <VoicePane />}
                  {state.modality === "docs" && <DocsPane />}
                  {state.modality === "screen" && <ScreenPane />}
                </div>
              )}
            </div>
          </div>

          <div className="actions">
            <div className="left">
              <button className="btn btn-ghost">Save draft</button>
            </div>
            <div className="right">
              <span style={{fontSize: 12, color: "var(--muted)"}}>
                Capture is encrypted and scoped to your department.
              </span>
              <button
                className="btn btn-primary"
                disabled={!canSubmit}
                onClick={onNext}
              >
                Run extraction <Icon.Arrow />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function VoicePane() {
  return (
    <div className="voice-rec">
      <button className="rec-btn"><span className="dot" /></button>
      <div className="voice-info">
        <div className="vi-title">Record in browser</div>
        <div className="vi-sub">Up to 30 minutes · or drop an .mp3 / .wav / .m4a file here</div>
      </div>
      <div className="waveform">
        {Array.from({length: 28}).map((_, i) => (
          <i key={i} style={{height: `${6 + Math.abs(Math.sin(i*0.6)) * 18}px`}} />
        ))}
      </div>
    </div>
  );
}

function DocsPane() {
  return (
    <div className="uploader">
      <div className="u-title">Drop files here</div>
      <div className="u-sub">PDF, DOCX, TXT, image, or screenshot · up to 50 MB each</div>
      <button className="btn btn-secondary"><Icon.Plus /> Choose files</button>
      <div className="files">
        <div className="file">
          <span style={{fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted)"}}>PDF</span>
          <span className="name">PTS_Appeals_Policy_2024.pdf</span>
          <span className="size">412 KB</span>
          <span className="x">✕</span>
        </div>
        <div className="file">
          <span style={{fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted)"}}>DOCX</span>
          <span className="name">Hearing_Officer_Notes_v3.docx</span>
          <span className="size">88 KB</span>
          <span className="x">✕</span>
        </div>
      </div>
    </div>
  );
}

function ScreenPane() {
  return (
    <div className="screencap">
      <div className="preview">
        <div className="cursor" />
        <div className="placeholder">[ no recording yet ]</div>
      </div>
      <div className="info">
        <div className="title">Record your screen</div>
        <div className="desc">Walk through the workflow in T2 Flex (or wherever it lives). We'll transcribe narration if your mic is on.</div>
        <ul className="checklist">
          <li>Close anything containing PII you don't want captured</li>
          <li>Narrate decisions as you make them</li>
          <li>Most workflows take 4–8 minutes</li>
        </ul>
        <div style={{marginTop: 16}}>
          <button className="btn btn-primary">Start recording</button>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   SCREEN 2 — PROCESSING (dark cooking animation)
   ============================================================ */
function ScreenProcessing({ onDone }) {
  const [phase, setPhase] = useState(0); // 0=code, 1=wireframe, 2=diagnostic
  const [captionIdx, setCaptionIdx] = useState(0);
  const [step, setStep] = useState(0);

  const captions = [
    "Transcribing audio",
    "Parsing documents",
    "Extracting workflow graph",
    "Identifying gaps",
  ];

  useEffect(() => {
    const timers = [];
    // cycle phases
    timers.push(setTimeout(() => setPhase(1), 3800));
    timers.push(setTimeout(() => setPhase(2), 6600));
    timers.push(setTimeout(() => onDone(), 9200));
    // cycle captions
    captions.forEach((_, i) => {
      timers.push(setTimeout(() => setCaptionIdx(i), i * 2200));
    });
    captions.forEach((_, i) => {
      timers.push(setTimeout(() => setStep(i), i * 2200));
    });
    return () => timers.forEach(clearTimeout);
  }, []);

  // Scan line animation via requestAnimationFrame
  const scanRef = useRef(null);
  useEffect(() => {
    let raf;
    let start = performance.now();
    const tick = (t) => {
      const elapsed = (t - start) % 2400;
      const pct = elapsed / 2400;
      if (scanRef.current) {
        scanRef.current.style.top = `${pct * 100}%`;
        scanRef.current.style.opacity = pct < 0.05 || pct > 0.95 ? "0" : "0.9";
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // Code line layout (widths in %)
  const lines = [
    { gutter: false, bars: [{w: 18, c: "grey-dim"}] },
    { gutter: false, bars: [{w: 26, c: "grey"}, {w: 14, c: "teal"}, {w: 22, c: "grey"}] },
    { gutter: true,  bars: [] },
    { gutter: false, bars: [{w: 12, c: "teal", glow: true}, {w: 6, c: "grey-dim"}] },
    { gutter: false, bars: [{w: 16, c: "slate"}, {w: 8, c: "slate-dim"}, {w: 6, c: "slate"}, {w: 14, c: "teal"}, {w: 22, c: "grey", fade: true}] },
    { gutter: false, bars: [{w: 10, c: "slate-dim"}, {w: 28, c: "teal"}] },
    { gutter: true,  bars: [] },
    { gutter: false, bars: [{w: 18, c: "grey"}, {w: 22, c: "teal"}, {w: 6, c: "grey-dim"}] },
    { gutter: false, bars: [{w: 8, c: "teal-dim"}] },
  ];

  return (
    <div className="app processing">
      <Topbar />
      <Subbar crumbs={["Workflows", "Weekend Citation Appeal — >$200", "Extracting"]} />
      <div className="proc-stage">
        <div className="proc-window-wrap">
          <div className="proc-window-ghost left" />
          <div className="proc-window-ghost right" />
          <div className="proc-window">
            <div className="pw-head">
              <div className="pw-dots"><i/><i/><i/></div>
              <div className="pw-title">workflow.graph.json</div>
              <div style={{width: 36}} />
            </div>
            <div className="pw-body">
              <div className="code-lines" style={{opacity: phase === 0 ? 1 : 0}}>
                {lines.map((ln, i) => (
                  <div className="code-line" key={i}>
                    {ln.gutter ? <span className="gutter"><i/></span> : <span style={{width: 14}} />}
                    {ln.bars.map((b, j) => (
                      <span
                        key={j}
                        className={`bar ${b.c}${b.glow ? " glow" : ""}${b.fade ? " fade-right" : ""}`}
                        style={{
                          width: `${b.w}%`,
                          animationDelay: `${(i * 120) + (j * 60)}ms`,
                        }}
                      />
                    ))}
                  </div>
                ))}
              </div>

              <div className={"wire-overlay" + (phase >= 1 ? " show" : "")}>
                <div className="wf-title">Weekend Citation Appeal — &gt;$200</div>
                <div className="wf-grid">
                  <div className="wf-col">
                    <div className="wf-box short" />
                    <div className="wf-box short" />
                    <div className="wf-box tall" style={{flex: 1}} />
                  </div>
                  <div className="wf-col">
                    <div className="wf-box tall" style={{flex: 1}} />
                    <div className="wf-box short" />
                  </div>
                </div>
              </div>

              {phase >= 2 && <div className="scan-line" ref={scanRef} />}
            </div>
          </div>
        </div>

        <div className="proc-caption">
          <div className="label">{captions[captionIdx]}</div>
          <div className="sub">~ {Math.max(8, 60 - captionIdx * 14)}s remaining</div>
        </div>
      </div>

      <div className="proc-pipeline">
        {["Transcribe", "Parse", "Extract", "Validate"].map((s, i) => (
          <div
            key={s}
            className={"proc-step " + (i < step ? "done" : i === step ? "active" : "")}
          >
            <span className="pulse" />
            <span>{s}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   SCREEN 3 — CLARIFY
   ============================================================ */
const QUESTIONS = [
  {
    context: "STEP 4 — APPEAL ROUTING",
    q: <>You mentioned forwarding appeals over $200 to someone. Is that the <span className="quote">"assistant director"</span> or the <span className="quote">"appeals manager"</span>?</>,
    hint: "I saw both titles used in the PDF and the recording. They sound like the same person, but I want to be sure.",
    placeholder: "Type the role title…",
    chips: ["Assistant Director, PTS", "Appeals Manager", "Same person — different titles"],
    gapLabel: "Approver role for $200+ appeals",
  },
  {
    context: "STEP 6 — SLA",
    q: <>How long does the appellant have to respond once a request for additional documentation is sent?</>,
    hint: "If they don't respond in time, what happens?",
    placeholder: "e.g. 10 business days, then auto-dismiss",
    chips: ["10 business days", "14 calendar days", "30 days"],
    gapLabel: "SLA on documentation requests",
  },
  {
    context: "STEP 8 — EXCEPTIONS",
    q: <>What are the conditions under which an appeal can bypass the standard review and go straight to the director?</>,
    hint: "Edge cases only — accessibility, medical, faculty/staff status, anything else?",
    placeholder: "Describe the conditions…",
    chips: ["Accessibility-related", "Medical emergency", "Faculty/staff appeals"],
    gapLabel: "Director-escalation conditions",
  },
  {
    context: "STEP 11 — APPROVAL",
    q: <>Once the director makes a decision, who is responsible for notifying the appellant — and via what channel?</>,
    hint: "Email, letter, T2 portal, phone? And does the notifier draft the language or follow a template?",
    placeholder: "Who notifies, and how…",
    chips: ["Appeals coordinator, via T2 Flex", "Hearing officer, via email", "Templated letter"],
    gapLabel: "Notification responsibility",
  },
  {
    context: "STEP 12 — RECORDS",
    q: <>How long are appeal records retained, and where do they live after the case is closed?</>,
    hint: "Georgia BOR retention schedule applies — confirm the specifics for your unit.",
    placeholder: "Retention period and location…",
    chips: ["7 years, T2 archive", "5 years, shared drive", "Per BOR schedule"],
    gapLabel: "Retention policy",
  },
];

function ScreenClarify({ onDone }) {
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState("");
  const [answered, setAnswered] = useState([]);
  const inputRef = useRef(null);
  const total = QUESTIONS.length;
  const done = idx >= total;

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, [idx]);

  const submit = () => {
    if (!answer.trim()) return;
    setAnswered([...answered, answer]);
    setAnswer("");
    setIdx(idx + 1);
  };

  const onKey = (e) => {
    if (e.key === "Enter") submit();
  };

  const current = QUESTIONS[Math.min(idx, total - 1)];

  return (
    <div className="app">
      <Topbar />
      <Subbar crumbs={["Workflows", "Weekend Citation Appeal — >$200", "Clarifying"]} />
      <div className="clarify">
        <div className="clar-main">
          <div className="clar-progress">
            <div className="bars">
              {Array.from({length: total}).map((_, i) => (
                <i key={i} className={i < idx ? "done" : i === idx ? "active" : ""} />
              ))}
            </div>
            <span>{done ? "Complete" : `Question ${idx + 1} of ${total}`}</span>
            <span style={{color: "var(--muted-2)"}}>· {answered.length} resolved</span>
          </div>

          {!done && (
            <>
              <div className="clar-context">{current.context}</div>
              <h2 className="clar-q">{current.q}</h2>
              <div className="clar-hint">{current.hint}</div>
              <div className="clar-input">
                <input
                  ref={inputRef}
                  placeholder={current.placeholder}
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={onKey}
                />
                <span className="enter">
                  <span className="kbd">↵</span> Enter to submit
                </span>
              </div>
              <div className="clar-suggestions">
                {current.chips.map((c) => (
                  <button key={c} className="clar-chip" onClick={() => setAnswer(c)}>{c}</button>
                ))}
              </div>
              <div className="clar-actions">
                <span>Modus is filling in the workflow graph as you answer.</span>
                <span style={{marginLeft: "auto"}}>
                  <button className="btn btn-ghost">Skip — I'm not sure</button>
                </span>
              </div>
            </>
          )}

          {done && (
            <>
              <div className="clar-context">GRAPH COMPLETE</div>
              <h2 className="clar-q">All gaps resolved. Ready to generate the SOP.</h2>
              <div className="clar-hint">
                The workflow graph has 14 steps, 4 decision points, 3 approver roles, and 2 SLA edges.
                Generating will produce a versioned SOP document — you can re-run clarification any time.
              </div>
              <div style={{marginTop: 32, display: "flex", gap: 10}}>
                <button className="btn btn-primary" onClick={onDone}>Generate SOP <Icon.Arrow /></button>
                <button className="btn btn-ghost" onClick={() => { setIdx(0); setAnswered([]); }}>Review answers</button>
              </div>
            </>
          )}
        </div>

        <div className="clar-rail">
          <h4>Capture</h4>
          <div className="meta-row">
            <div className="item"><span className="k">Workflow</span><div className="v">Weekend Citation Appeal — &gt;$200</div></div>
            <div className="item"><span className="k">Department</span><div className="v">PTS</div></div>
            <div className="item"><span className="k">Sources</span><div className="v">2 PDFs · 1 voice (14 min)</div></div>
          </div>

          <hr />

          <h4>Gaps</h4>
          <ul className="gaps">
            {QUESTIONS.map((q, i) => (
              <li
                key={i}
                className={i < idx ? "done" : i === idx ? "current" : ""}
              >
                {q.gapLabel}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   SCREEN 4 — SOP
   ============================================================ */
function ScreenSOP({ onRestart }) {
  const sections = [
    { id: "overview",   label: "Overview" },
    { id: "scope",      label: "Scope & applicability" },
    { id: "roles",      label: "Roles & responsibilities" },
    { id: "procedure",  label: "Procedure" },
    { id: "edge",       label: "Edge cases" },
    { id: "records",    label: "Records & retention" },
  ];

  return (
    <div className="app sop-shell">
      <Topbar />
      <div className="sop-toolbar">
        <span className="status"><span className="dot" /> SOP READY</span>
        <span>·</span>
        <span>Generated 11 May 2026, 09:42 EDT</span>
        <span>·</span>
        <span>Graph v0.1.0 · 14 steps · 4 decisions</span>
        <div className="right">
          <button className="tb-btn">Download .md</button>
          <button className="tb-btn">Download .pdf</button>
          <button className="tb-btn">Share</button>
          <button className="tb-btn primary" onClick={onRestart}>New capture</button>
        </div>
      </div>

      <div className="sop-layout">
        <aside className="sop-toc">
          <h5>Contents</h5>
          <ol>
            {sections.map((s) => (
              <li key={s.id}><a href={`#${s.id}`}>{s.label}</a></li>
            ))}
          </ol>
        </aside>

        <article className="sop-doc">
          <header className="sop-header">
            <div className="sop-eyebrow">SOP — PTS-APL-002 · v0.1.0</div>
            <h1 className="sop-title">Weekend Citation Appeal — Standard Amounts above $200</h1>
            <div className="sop-meta-grid">
              <div><span className="k">Department</span><span className="v">Parking & Transportation</span></div>
              <div><span className="k">Owner</span><span className="v">D. Okafor, Assistant Director</span></div>
              <div><span className="k">Generated</span><span className="v">11 May 2026</span></div>
              <div><span className="k">Source</span><span className="v">2 docs · 14m voice</span></div>
            </div>
          </header>

          <section className="sop-section" id="overview">
            <h2>Overview</h2>
            <p>
              This procedure governs the review and adjudication of citation appeals submitted by
              students, staff, faculty, and visitors when the contested fine exceeds $200. The
              workflow applies to citations issued during the weekend operating window (Friday 17:00
              through Monday 07:00, Atlanta local time) and supersedes the standard weekday appeals
              process for that subset of cases.
            </p>
            <p>
              The intent of the procedure is to deliver a defensible, consistently-reasoned decision
              within ten business days of appeal submission, while preserving the appellant's right
              to escalate to the Director of Auxiliary Services.
            </p>
          </section>

          <section className="sop-section" id="scope">
            <h2>Scope & applicability</h2>
            <ul>
              <li>Citations with a base amount of $200 or greater.</li>
              <li>Citations issued between Friday 17:00 and Monday 07:00.</li>
              <li>Appeals submitted within 14 calendar days of the citation issue date.</li>
              <li>Excludes immobilization, tow, and impound fee appeals (see PTS-IMB-001).</li>
            </ul>
          </section>

          <section className="sop-section" id="roles">
            <h2>Roles & responsibilities</h2>
            <ul>
              <li><strong>Appeals Coordinator</strong> — Performs initial intake and routing in T2 Flex.</li>
              <li><strong>Hearing Officer</strong> — Reviews evidence, applies precedent, drafts the decision.</li>
              <li><strong>Assistant Director, PTS</strong> — Approves all decisions on amounts above $200.</li>
              <li><strong>Director, Auxiliary Services</strong> — Final escalation authority for accessibility, medical, and policy-exception cases.</li>
            </ul>
          </section>

          <section className="sop-section" id="procedure">
            <h2>Procedure</h2>

            <Step n="01" title="Receive appeal in T2 Flex">
              <p>Appeals arrive in the <em>Appeals — Inbox</em> queue tagged with the citation number, issue
              timestamp, and stated grounds. The Appeals Coordinator opens each case within one business
              day and confirms it meets the scope criteria above.</p>
              <PillRow>
                <Pill k="Executor">Appeals Coordinator</Pill>
                <Pill k="System">T2 Flex</Pill>
                <Pill k="SLA">1 business day</Pill>
              </PillRow>
            </Step>

            <Step n="02" title="Verify weekend window and amount threshold">
              <p>Confirm the citation was issued during the weekend operating window and that the base
              amount is $200 or greater. If both conditions hold, apply the <code>PTS-WEEKEND-APPEAL</code>
              tag and proceed. Otherwise route to the standard appeals queue.</p>
              <div className="decision">
                <div className="lead">DECISION</div>
                If <em>issued_at</em> is within the weekend window <em>and</em> <em>amount</em> ≥ $200 →
                tag and continue. Else → route to <code>Appeals — Standard</code>.
              </div>
            </Step>

            <Step n="03" title="Collect supporting evidence">
              <p>Pull the citation photo set, officer notes, and any GIS / sensor data attached to the
              ticket. Cross-reference the location against published weekend lot closures and event
              parking exemptions.</p>
              <PillRow>
                <Pill k="Inputs">Citation #, officer notes, GIS log</Pill>
                <Pill k="Output">Evidence packet (PDF)</Pill>
              </PillRow>
            </Step>

            <Step n="04" title="Route to Assistant Director">
              <p>For amounts above $200, the Appeals Coordinator forwards the evidence packet and a one-paragraph case summary to the Assistant Director, PTS via T2 Flex's
              internal routing — not email. The Assistant Director acknowledges receipt within one business day.</p>
              <PillRow>
                <Pill k="Approver">Assistant Director, PTS</Pill>
                <Pill k="Channel">T2 Flex routing</Pill>
                <Pill k="SLA">1 business day ack</Pill>
              </PillRow>
            </Step>

            <Step n="05" title="Hearing Officer review">
              <p>The Hearing Officer reviews the evidence packet against the appeals precedent index
              (PTS-PRECEDENT-2024) and drafts a recommendation: <em>uphold</em>, <em>reduce</em>, or
              <em> dismiss</em>. The recommendation includes a citation to the precedent or policy clause that justifies it.</p>
            </Step>

            <Step n="06" title="Request additional documentation if needed">
              <p>If the Hearing Officer determines the record is incomplete, they send a documentation
              request to the appellant via T2 Flex with a clear list of what is needed.</p>
              <div className="decision">
                <div className="lead">SLA</div>
                Appellant has <strong>10 business days</strong> to respond. No response → appeal is auto-dismissed with a notification and a single one-time reinstatement option.
              </div>
            </Step>

            <Step n="07" title="Assistant Director approval">
              <p>The Assistant Director reviews the Hearing Officer's recommendation and either
              approves it, modifies it with documented reasoning, or returns it for further review.
              All three outcomes are recorded in the case audit log.</p>
            </Step>

            <Step n="08" title="Escalation to Director (conditional)">
              <p>Cases meeting any of the following criteria are escalated to the Director of Auxiliary
              Services regardless of the Assistant Director's recommendation:</p>
              <div className="decision">
                <div className="lead">ESCALATION CRITERIA</div>
                Accessibility-related citation · documented medical emergency · faculty or staff status
                with departmental endorsement · prior precedent contradiction.
              </div>
            </Step>

            <Step n="09" title="Decision recorded in T2 Flex">
              <p>Final disposition is recorded in T2 Flex with the decision rationale, applicable
              precedent citations, and any conditions (e.g. payment plan, reduced amount).</p>
            </Step>

            <Step n="10" title="Appellant notification">
              <p>The Appeals Coordinator notifies the appellant via T2 Flex's portal message and
              follow-up email using the approved template (<code>PTS-NOTIF-APPEAL-OUTCOME</code>).
              The notification includes the decision, rationale summary, and instructions for any
              further action.</p>
              <PillRow>
                <Pill k="Notifier">Appeals Coordinator</Pill>
                <Pill k="Template">PTS-NOTIF-APPEAL-OUTCOME</Pill>
              </PillRow>
            </Step>

            <Step n="11" title="Payment plan setup (if applicable)">
              <p>If the decision reduces but does not dismiss the amount, the Appeals Coordinator
              offers a payment plan per the standard ladder. Plans must be confirmed by the appellant
              within 7 calendar days of decision notification.</p>
            </Step>

            <Step n="12" title="Case closure and archival">
              <p>Once the appellant has acknowledged the decision or the response window has closed,
              the case is marked <code>Closed</code> in T2 Flex. The full case record is exported to
              the PTS appeals archive nightly.</p>
              <PillRow>
                <Pill k="Retention">7 years (Georgia BOR schedule)</Pill>
                <Pill k="Location">T2 archive · PTS-APPEALS-ARCHIVE</Pill>
              </PillRow>
            </Step>
          </section>

          <section className="sop-section" id="edge">
            <h2>Edge cases</h2>
            <div className="edge">
              <div className="lead">EDGE — DUPLICATE APPEAL</div>
              If an appellant files a second appeal for the same citation after a final decision,
              the second submission is auto-dismissed with a notification pointing to the original
              case. Director-level review is the only path to reopen.
            </div>
            <div className="edge">
              <div className="lead">EDGE — TIMESTAMP DISPUTE</div>
              If the appellant disputes the citation timestamp, the Hearing Officer pulls the
              corresponding LPR or officer-camera record and includes it in the evidence packet.
            </div>
            <div className="edge">
              <div className="lead">EDGE — EVENT PARKING EXEMPTION</div>
              For citations issued in an event-parking-exempt lot during an active event,
              auto-uphold-the-appeal applies unless the citation is for a non-parking violation
              (e.g. blocking a fire lane).
            </div>
          </section>

          <section className="sop-section" id="records">
            <h2>Records & retention</h2>
            <p>
              All appeal records — evidence packets, decisions, notifications, audit logs — are
              retained for seven years from the case closure date in accordance with the Georgia
              Board of Regents records retention schedule. Records are stored in the T2 Flex appeals
              archive with read-only access for the Hearing Officer pool and full access for the
              Assistant Director and Director.
            </p>
            <p style={{color: "var(--muted)", fontSize: 13, marginTop: 24}}>
              — End of procedure —
            </p>
          </section>
        </article>

        <aside className="sop-rail">
          <div className="block">
            <h5>Knowledge entities</h5>
            <div className="entity"><span>Roles</span><span className="count">4</span></div>
            <div className="entity"><span>Systems</span><span className="count">2</span></div>
            <div className="entity"><span>Policies</span><span className="count">3</span></div>
            <div className="entity"><span>SLAs</span><span className="count">5</span></div>
            <div className="entity"><span>Templates</span><span className="count">1</span></div>
          </div>

          <div className="block">
            <h5>Changelog</h5>
            <div className="changelog">
              <div className="row">
                <span className="ver">v0.1.0</span>
                <span className="note">Initial extraction · 11 May 2026</span>
              </div>
            </div>
          </div>

          <div className="block">
            <h5>Linked captures</h5>
            <div className="changelog">
              <div className="row">
                <span className="ver">CAP-7</span>
                <span className="note">Hearing Officer voice walkthrough</span>
              </div>
              <div className="row">
                <span className="ver">DOC-12</span>
                <span className="note">PTS_Appeals_Policy_2024.pdf</span>
              </div>
              <div className="row">
                <span className="ver">DOC-13</span>
                <span className="note">Hearing_Officer_Notes_v3.docx</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Step({ n, title, children }) {
  return (
    <div className="sop-step">
      <div className="num">{n}</div>
      <div>
        <h3 className="title">{title}</h3>
        {children}
      </div>
    </div>
  );
}
function Pill({ k, children }) {
  return <span className="sop-pill"><span className="k">{k}</span><span>{children}</span></span>;
}
function PillRow({ children }) {
  return <div className="pill-row">{children}</div>;
}

/* ============================================================
   APP — state machine across the 4 screens
   ============================================================ */
function App() {
  const [screen, setScreen] = useState(0); // 0=capture, 1=processing, 2=clarify, 3=sop
  const [state, setState] = useState({
    name: "Weekend Citation Appeal — >$200",
    dept: "Parking & Transportation",
    modality: "voice",
    text: "",
  });

  const screens = ["Capture", "Processing", "Clarify", "SOP"];

  const goNext = () => setScreen((s) => Math.min(3, s + 1));
  const goPrev = () => setScreen((s) => Math.max(0, s - 1));
  const restart = () => setScreen(0);

  return (
    <>
      {screen === 0 && <ScreenCapture state={state} setState={setState} onNext={goNext} />}
      {screen === 1 && <ScreenProcessing onDone={goNext} />}
      {screen === 2 && <ScreenClarify onDone={goNext} />}
      {screen === 3 && <ScreenSOP onRestart={restart} />}

      <div className="demo-nav">
        <span>{screens[screen]}</span>
        <span className="dots">
          {screens.map((_, i) => (
            <span key={i} className={"dot" + (i === screen ? " active" : "")} />
          ))}
        </span>
        <button onClick={goPrev} disabled={screen === 0}>← Back</button>
        <button onClick={goNext} disabled={screen === 3}>Next →</button>
        <button className="restart" onClick={restart}>Restart</button>
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
