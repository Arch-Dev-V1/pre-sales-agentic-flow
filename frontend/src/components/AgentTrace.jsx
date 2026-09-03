// This is the single most important component for the hackathon demo.
// A loading spinner says "trust me." This live feed says "watch me
// think" — it's the difference between the demo reading as a wrapper
// and reading as genuinely agentic. See the conversation notes: judges
// should see something like:
//
//   🔍 Analyst: scanning 12 endpoints...
//   🧠 Analyst: found 4 demo-worthy endpoints in "identity verification"
//   📝 Sequencer: sequencing steps, threading personId from step 1 to 3...
//   ✅ Verifier: step 1 passed
//   ✗ Verifier: step 2 failed — auth token rejected, retrying...
//   📝 Sequencer: revising step 2...
//   ✅ Verifier: step 2 passed on retry
//
// TODO: this currently expects `events` to be passed in as a static list
// once generateDemo() resolves. Swap for a live-updating list once the
// backend streams progress via SSE/websocket (see api/client.js's TODO
// on generateDemo) — that's what makes this feel live during an actual
// judged demo instead of appearing all at once.

export default function AgentTrace({ events }) {
  if (!events || events.length === 0) return null;

  return (
    <div aria-live="polite">
      <h3>Agent trace</h3>
      <ul>
        {events.map((event, i) => (
          <li key={i}>
            <strong>{event.agent}:</strong> {event.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
