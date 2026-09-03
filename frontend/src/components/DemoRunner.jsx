import { useState } from "react";
import { runStep } from "../api/client";
import ResultView from "./ResultView";

// The thing a salesperson drives in front of a prospect. It is meant to
// read as a product with screens, not as a request/response inspector —
// so the designed result view is the page, the narration sits in a
// footer as the presenter's line, and the raw JSON is one disclosure
// down for the technically curious prospect.
//
// What's on each screen is decided per-collection by the Sequencer's
// presentation pass (screens[], see prompts/sequencer_agent.md) and
// rendered by ResultView. A banking collection produces applicants and
// risk bands; a sales collection produces orders and totals; this
// component is identical either way.
//
// Two sources for a response, always labelled:
//   - "Verified" — captured when the Verifier called the API during
//     generation. Always present, never fails mid-presentation.
//   - "Live" — fired just now via /run-step, optionally with a payload
//     the presenter edited to use the prospect's own values.
export default function DemoRunner({
  demoScript,
  rawResponses,
  screens,
  companyName,
  sessionId,
  collectionId,
}) {
  const [current, setCurrent] = useState(0);
  // All keyed by step_number so navigating away and back keeps what the
  // presenter already ran or typed.
  const [liveResponses, setLiveResponses] = useState({});
  const [drafts, setDrafts] = useState({});
  const [running, setRunning] = useState(false);
  const [liveError, setLiveError] = useState(null);

  const steps = demoScript?.steps ?? [];
  const step = steps[current];

  if (!step) return <p className="empty">No demo steps available.</p>;

  const screenFor = (n) => (screens ?? []).find((s) => s.step_number === n);
  const screen = screenFor(step.step_number) ?? {};

  const recorded = rawResponses?.[step.step_number];
  const live = liveResponses[step.step_number];
  const response = live ?? recorded;
  const isLive = Boolean(live);
  const body = response?.body;

  // ResultView returns null when the agent gave no usable blocks for
  // this step, which is the signal to fall back to the raw response.
  const designed = <ResultView blocks={screen.blocks} body={body} />;
  const hasDesignedView = designed !== null;

  const draft = drafts[step.step_number] ?? JSON.stringify(step.resolved_payload, null, 2);
  const canRunLive = Boolean(sessionId && collectionId);

  const goTo = (n) => {
    setCurrent(n);
    setLiveError(null);
  };

  const handleRunLive = async () => {
    let payload;
    try {
      payload = draft.trim() ? JSON.parse(draft) : null;
    } catch (e) {
      setLiveError(`That payload isn't valid JSON: ${e.message}`);
      return;
    }

    setRunning(true);
    setLiveError(null);
    try {
      const result = await runStep({
        sessionId,
        collectionId,
        endpointId: step.endpoint_id,
        payload,
        // Lets a step that threads {{stepN.response.field}} from an
        // earlier step still resolve when run on its own.
        priorResponses: rawResponses ?? {},
      });
      setLiveResponses((prev) => ({ ...prev, [step.step_number]: result }));
    } catch (e) {
      setLiveError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const revertToVerified = () => {
    setLiveResponses((prev) => {
      const next = { ...prev };
      delete next[step.step_number];
      return next;
    });
    setLiveError(null);
  };

  return (
    <div className="runner">
      <header className="runner-top">
        <div className="runner-id">
          {companyName && <span className="eyebrow">Prepared for {companyName}</span>}
        </div>
        <span className={isLive ? "badge badge-live" : "badge"}>
          {isLive ? "Live — just now" : "Verified"}
        </span>
      </header>

      <div className="progress" role="presentation">
        <span style={{ width: `${((current + 1) / steps.length) * 100}%` }} />
      </div>

      <div className="runner-body">
        {/* The journey, named by the agent in the collection's own
            vocabulary — "Applicant", "Shipment", "Settlement". */}
        <nav className="stages" aria-label="Demo stages">
          {steps.map((s, i) => (
            <button
              key={s.step_number}
              type="button"
              className={i < current ? "stage done" : "stage"}
              aria-current={i === current}
              onClick={() => goTo(i)}
            >
              <span className="stage-n">{i + 1}</span>
              <span className="stage-l">
                {screenFor(s.step_number)?.stage_label ?? `Step ${i + 1}`}
              </span>
            </button>
          ))}
        </nav>

        <section className="stage-main">
          <div className="stage-head">
            <p className="kicker">
              {screen.kicker ?? `Step ${current + 1} of ${steps.length}`}
            </p>
            <h2>{screen.screen_title ?? step.narration}</h2>
          </div>

          {response ? (
            hasDesignedView ? (
              designed
            ) : (
              // No usable blocks for this step — show the response
              // rather than an empty screen.
              <div className="card">
                <p className={response.status_code < 400 ? "status ok" : "status bad"}>
                  {response.status_code}
                </p>
                <pre>{JSON.stringify(body, null, 2)}</pre>
              </div>
            )
          ) : (
            <p className="empty">
              No response captured for this step — it may have been part of a
              correction round. Check `verification.step_results`.
            </p>
          )}

          {liveError && <p className="alert" role="alert">{liveError}</p>}

          <details className="raw">
            <summary>Behind the scenes — request and raw response</summary>

            <label className="raw-l">
              Request payload
              <textarea
                className="payload"
                value={draft}
                spellCheck={false}
                onChange={(e) =>
                  setDrafts((prev) => ({ ...prev, [step.step_number]: e.target.value }))
                }
              />
            </label>
            <p className="hint">
              Edit this to run the step with the prospect's own values. The
              backend still resolves {"{{variables}}"} and applies the host policy.
            </p>

            {response && (
              <>
                <div className="raw-head">
                  <span>Response</span>
                  <span className={response.status_code < 400 ? "status ok" : "status bad"}>
                    {response.status_code}
                  </span>
                </div>
                <pre>{JSON.stringify(body, null, 2)}</pre>
              </>
            )}

            <div className="raw-acts">
              {canRunLive ? (
                <button type="button" className="primary" onClick={handleRunLive} disabled={running}>
                  {running ? "Calling the API..." : "Run this step live"}
                </button>
              ) : (
                <p className="hint">Live re-runs need an active session.</p>
              )}
              {isLive && (
                <button type="button" className="link" onClick={revertToVerified}>
                  Show the verified response instead
                </button>
              )}
            </div>
          </details>
        </section>
      </div>

      <footer className="runner-foot">
        <div className="say">
          <div className="say-l">What you say</div>
          <p>{step.narration}</p>
        </div>
        <div className="say-acts">
          <button type="button" onClick={() => goTo(current - 1)} disabled={current === 0}>
            Back
          </button>
          <button
            type="button"
            className="primary"
            onClick={() => goTo(current + 1)}
            disabled={current === steps.length - 1}
          >
            {current === steps.length - 1 ? "Done" : "Continue"}
          </button>
        </div>
      </footer>
    </div>
  );
}
