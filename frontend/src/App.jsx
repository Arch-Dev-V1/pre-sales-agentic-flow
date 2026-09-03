import { useState } from "react";
import ConnectPostman from "./components/ConnectPostman";
import ConfigureDemo from "./components/ConfigureDemo";
import AgentTrace from "./components/AgentTrace";
import DemoRunner from "./components/DemoRunner";
import { generateDemo } from "./api/client";

// Four-screen flow: connect -> configure (fixed questions) -> generating
// (with live trace) -> run the verified demo. The configure step is
// intentionally a plain form, not a chat — see ConfigureDemo.jsx for why.
export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [collectionId, setCollectionId] = useState(null);
  const [demoConfig, setDemoConfig] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [demoResult, setDemoResult] = useState(null);
  const [traceEvents, setTraceEvents] = useState([]);
  const [error, setError] = useState(null);

  const handleConnected = (newSessionId, newCollectionId) => {
    setSessionId(newSessionId);
    setCollectionId(newCollectionId);
  };

  const handleConfigured = async (config) => {
    setDemoConfig(config);
    setGenerating(true);
    setError(null);
    try {
      // TODO: once generateDemo streams, push into setTraceEvents as
      // events arrive instead of getting one result at the end.
      const result = await generateDemo({ sessionId, collectionId, demoConfig: config });
      setDemoResult(result);
    } catch (e) {
      // Without this, a failed run rejected unhandled and every render
      // branch below fell through to `return null` — a blank screen.
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleRetry = () => {
    setError(null);
    setDemoConfig(null);
  };

  // The theme is chosen in ConfigureDemo and is pure presentation — it
  // never reaches an agent. Applied once here, on the shell, so every
  // screen after configuration honours it rather than just the runner.
  const theme = demoConfig?.theme === "Dark" ? "dark" : "light";

  return (
    <div className="shell" data-theme={theme}>
      <div className="shell-inner">{renderScreen()}</div>
    </div>
  );

  function renderScreen() {
    if (!sessionId) {
      return <ConnectPostman onConnected={handleConnected} />;
    }

    if (!demoConfig) {
      return <ConfigureDemo onSubmit={handleConfigured} />;
    }

    if (generating) {
      return (
        <div className="generating">
          <h2>Building your demo...</h2>
          <p className="hint">
            The Analyst is reading your collection, the Sequencer is ordering
            the story, and the Verifier is calling every endpoint for real.
          </p>
          <AgentTrace events={traceEvents} />
        </div>
      );
    }

    if (error) {
      return (
        <div className="panel">
          <h2>Couldn't build the demo</h2>
          <pre className="alert">{error}</pre>
          <button type="button" className="primary" onClick={handleRetry}>
            Back to setup
          </button>
        </div>
      );
    }

    if (demoResult?.status === "verified") {
      return (
        <DemoRunner
          demoScript={demoResult.demo_script}
          rawResponses={demoResult.raw_responses}
          screens={demoResult.screens}
          companyName={demoConfig.companyName}
          sessionId={sessionId}
          collectionId={collectionId}
        />
      );
    }

    if (demoResult?.status === "needs_human_review") {
      return (
        <div className="panel">
          <h2>Needs a quick look</h2>
          <p>The agents couldn't fully verify this demo:</p>
          <pre>{JSON.stringify(demoResult.verification.blockers, null, 2)}</pre>
          <button type="button" className="primary" onClick={handleRetry}>
            Back to setup
          </button>
        </div>
      );
    }

    return null;
  }
}
