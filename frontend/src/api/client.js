// Thin wrapper around the backend's routes. Deliberately the ONLY place
// in the frontend that constructs a request — nothing else in the app
// should reach for fetch() directly, so credentials never accidentally
// end up in a component instead of going straight to the backend.

const BASE_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

// FastAPI puts the useful text in `detail`. Without pulling it out, a
// backend failure surfaces in the UI as a generic sentence and the
// actual reason only exists in the server log.
async function errorMessage(res, fallback) {
  try {
    const { detail } = await res.json();
    return detail ? `${fallback} ${detail}` : fallback;
  } catch {
    return fallback;
  }
}

export async function listWorkspaces(postmanApiKey) {
  const res = await fetch(`${BASE_URL}/postman/workspaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ postman_api_key: postmanApiKey }),
  });
  if (!res.ok) throw new Error("Couldn't fetch workspaces — check your API key.");
  const { workspaces } = await res.json();
  return workspaces; // [{id, name}]
}

export async function listWorkspaceContents(postmanApiKey, workspaceId) {
  const res = await fetch(`${BASE_URL}/postman/workspace-contents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ postman_api_key: postmanApiKey, workspace_id: workspaceId }),
  });
  if (!res.ok) throw new Error("Couldn't fetch that workspace's contents.");
  return res.json(); // {collections: [{id, name}], environments: [{id, name}]}
}

export async function connect({
  postmanApiKey,
  collectionId,
  environmentId,
  targetBaseUrl,
  targetUsername,
  targetPassword,
}) {
  // NOTE: these values are sent once, over the wire, to establish the
  // session — they are never stored in frontend state after this call
  // returns. Only the opaque session_id is kept client-side from here on.
  const res = await fetch(`${BASE_URL}/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      postman_api_key: postmanApiKey,
      collection_id: collectionId,
      environment_id: environmentId,
      target_base_url: targetBaseUrl,
      target_username: targetUsername,
      target_password: targetPassword,
    }),
  });
  if (!res.ok) throw new Error("Failed to connect.");
  const { session_id } = await res.json();
  return session_id;
}

export async function generateDemo({ sessionId, collectionId, demoConfig }) {
  // TODO: switch this to an EventSource/SSE connection once the backend
  // streams agent progress, so AgentTrace can render live instead of
  // waiting for one big response at the end.
  const res = await fetch(`${BASE_URL}/generate-demo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      collection_id: collectionId,
      demo_config: {
        industry: demoConfig.industry,
        emphasis: demoConfig.emphasis,
        tone: demoConfig.tone,
        company_name: demoConfig.companyName || null,
        depth: demoConfig.depth,
      },
    }),
  });
  if (!res.ok) throw new Error(await errorMessage(res, "Failed to generate demo."));
  return res.json();
}

export async function runStep({ sessionId, collectionId, endpointId, payload, priorResponses }) {
  // Fires one endpoint live, right now, rather than showing the
  // response recorded during verification. Same backend guardrails —
  // the route is a thin wrapper over the Verifier's own call path.
  const res = await fetch(`${BASE_URL}/run-step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      collection_id: collectionId,
      endpoint_id: endpointId,
      payload: payload ?? null,
      prior_responses: priorResponses ?? {},
    }),
  });
  if (!res.ok) throw new Error(await errorMessage(res, "Couldn't run that step live."));
  return res.json(); // {status_code, body}
}

export async function endSession(sessionId) {
  await fetch(`${BASE_URL}/end-session?session_id=${sessionId}`, { method: "POST" });
}
