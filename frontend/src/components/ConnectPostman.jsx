import { useState } from "react";
import { connect, listWorkspaces, listWorkspaceContents } from "../api/client";

// Three-stage flow, all on one screen: enter the API key -> pick a
// workspace by name -> pick a collection and environment by name. The
// user never sees or types a raw Postman id anywhere — the ids ride
// along invisibly once something's selected from a dropdown. This is
// the fix for "how does it know where the collection is": it doesn't
// ask, it browses and lets the user point.
export default function ConnectPostman({ onConnected }) {
  const [postmanApiKey, setPostmanApiKey] = useState("");
  const [workspaces, setWorkspaces] = useState(null); // null = not fetched yet
  const [workspaceId, setWorkspaceId] = useState("");
  const [contents, setContents] = useState(null); // {collections, environments}
  const [collectionId, setCollectionId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");

  const [targetForm, setTargetForm] = useState({
    targetBaseUrl: "",
    targetUsername: "",
    targetPassword: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFetchWorkspaces = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const ws = await listWorkspaces(postmanApiKey);
      setWorkspaces(ws);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePickWorkspace = async (e) => {
    const id = e.target.value;
    setWorkspaceId(id);
    setContents(null);
    setCollectionId("");
    setEnvironmentId("");
    if (!id) return;

    setLoading(true);
    setError(null);
    try {
      const result = await listWorkspaceContents(postmanApiKey, id);
      setContents(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const sessionId = await connect({
        postmanApiKey,
        collectionId,
        environmentId,
        ...targetForm,
      });
      onConnected(sessionId, collectionId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Connect your Postman collection</h2>

      {/* Stage 1: API key -> fetch workspaces */}
      {workspaces === null && (
        <form onSubmit={handleFetchWorkspaces}>
          <label>
            Postman API key
            <input
              type="password"
              value={postmanApiKey}
              onChange={(e) => setPostmanApiKey(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Looking up your workspaces..." : "Continue"}
          </button>
        </form>
      )}

      {/* Stage 2 + 3: pick workspace, then collection + environment, then
          target API details, all by name — no id fields anywhere. */}
      {workspaces !== null && (
        <form onSubmit={handleSubmit}>
          <label>
            Workspace
            <select value={workspaceId} onChange={handlePickWorkspace} required>
              <option value="">Select a workspace...</option>
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>

          {contents && (
            <>
              <label>
                Collection
                <select value={collectionId} onChange={(e) => setCollectionId(e.target.value)} required>
                  <option value="">Select a collection...</option>
                  {contents.collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Environment (optional)
                <select value={environmentId} onChange={(e) => setEnvironmentId(e.target.value)}>
                  <option value="">
                    {contents.environments.length === 0 ? "No environments in this workspace" : "None"}
                  </option>
                  {contents.environments.map((env) => (
                    <option key={env.id} value={env.id}>
                      {env.name}
                    </option>
                  ))}
                </select>
                {contents.environments.length === 0 && (
                  <p>
                    This is fine — if the collection defines its own variables (its "Variables"
                    tab in Postman, not a separate environment), those will be used instead.
                  </p>
                )}
              </label>
            </>
          )}

          <label>
            Sandbox base URL
            <input
              value={targetForm.targetBaseUrl}
              onChange={(e) => setTargetForm({ ...targetForm, targetBaseUrl: e.target.value })}
              placeholder="https://sandbox.example.com"
              required
            />
          </label>

          {/* TODO: only show these if the collection's auth type actually
              needs them — some APIs are token-only, sourced entirely from
              the environment instead. */}
          <label>
            Target API username (optional)
            <input
              value={targetForm.targetUsername}
              onChange={(e) => setTargetForm({ ...targetForm, targetUsername: e.target.value })}
            />
          </label>
          <label>
            Target API password (optional)
            <input
              type="password"
              value={targetForm.targetPassword}
              onChange={(e) => setTargetForm({ ...targetForm, targetPassword: e.target.value })}
            />
          </label>

          {error && <p role="alert">{error}</p>}

          <button type="submit" disabled={loading || !collectionId}>
            {loading ? "Connecting..." : "Connect"}
          </button>
        </form>
      )}
    </div>
  );
}
