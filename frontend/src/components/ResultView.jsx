// Renders the display blocks the Sequencer's presentation pass produced
// for one step (see prompts/sequencer_agent.md → "Presentation pass").
//
// The division of labour matters: the agent chooses WHICH response
// fields to show, what each one MEANS, and the human wording. This file
// owns every layout and colour decision. That's what lets one component
// set serve any collection — a banking response yields "Risk band" and
// a verdict, a sales response yields "Order total" and a line-item
// table, from the same ten block types.
//
// Every renderer returns null when its data isn't there. If nothing
// renders, ResultView returns null and DemoRunner falls back to showing
// the raw response, which beats an empty screen.

const REDACTED = "<redacted>";

// "profile.givenName" / "signals[0].weight" -> value, or undefined.
export function getPath(body, path) {
  if (!path || body == null) return undefined;
  return String(path)
    .replace(/\[(\d+)\]/g, ".$1")
    .split(".")
    .filter(Boolean)
    .reduce((acc, key) => (acc == null ? undefined : acc[key]), body);
}

// Nothing masked ever reaches a prospect's screen — the prompt forbids
// selecting these fields, but a model can slip, so enforce it here too.
function usable(v) {
  return v !== undefined && v !== null && v !== "" && v !== REDACTED;
}

function display(v) {
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function toneClass(tone) {
  if (tone === "pass") return "tone-pass";
  if (tone === "warn") return "tone-warn";
  if (tone === "critical") return "tone-crit";
  return "tone-neutral";
}

function passed(value, passWhen) {
  if (passWhen === undefined) return Boolean(value);
  return value === passWhen;
}

function initials(text) {
  return String(text)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function Identity({ block, body }) {
  const title = getPath(body, block.title_path);
  if (!usable(title)) return null;
  const subtitle = (block.subtitle_paths ?? [])
    .map((p) => getPath(body, p))
    .filter(usable)
    .map(display)
    .join(" · ");

  return (
    <div className="card who">
      <div className="avatar">{initials(title)}</div>
      <div>
        <div className="who-name">{display(title)}</div>
        {subtitle && <div className="who-sub">{subtitle}</div>}
        {block.caption && !subtitle && <div className="who-sub">{block.caption}</div>}
      </div>
    </div>
  );
}

function Verdict({ block, body }) {
  const text = block.text ?? display(getPath(body, block.value_path) ?? "");
  if (!usable(text)) return null;
  return (
    <div className={`verdict ${toneClass(block.tone)}`}>
      <div className="verdict-ic" aria-hidden="true">
        {block.tone === "critical" ? "!" : block.tone === "warn" ? "!" : "✓"}
      </div>
      <div>
        <div className="verdict-t">{text}</div>
        {block.detail && <div className="verdict-d">{block.detail}</div>}
      </div>
    </div>
  );
}

function Metric({ block, body }) {
  const value = getPath(body, block.value_path);
  if (!usable(value)) return null;
  return (
    <div className="card">
      <div className={`metric ${toneClass(block.tone)}`}>
        {display(value)}
        {block.unit && <span className="metric-u">{block.unit}</span>}
      </div>
      {block.label && <div className="metric-l">{block.label}</div>}
    </div>
  );
}

function Gauge({ block, body }) {
  const value = Number(getPath(body, block.value_path));
  if (!Number.isFinite(value)) return null;
  const max = Number(block.max) || 100;
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const C = 2 * Math.PI * 45;

  return (
    <div className="card gauge-row">
      <div className="gauge">
        <svg width="104" height="104" viewBox="0 0 104 104" aria-hidden="true">
          <circle cx="52" cy="52" r="45" fill="none" stroke="var(--border)" strokeWidth="9" />
          <circle
            cx="52" cy="52" r="45" fill="none" stroke="var(--ok)" strokeWidth="9"
            strokeLinecap="round" strokeDasharray={`${(pct / 100) * C} ${C}`}
            transform="rotate(-90 52 52)"
          />
        </svg>
        <div className="gauge-mid">{display(getPath(body, block.value_path))}</div>
      </div>
      {block.label && <div className="gauge-l">{block.label}</div>}
    </div>
  );
}

function Meter({ block, body }) {
  const value = Number(getPath(body, block.value_path));
  if (!Number.isFinite(value)) return null;
  const max = Number(block.max) || 1;
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="card">
      <div className="meter-head">
        <span>{block.label}</span>
        <b>{display(getPath(body, block.value_path))}</b>
      </div>
      <div className="meter"><span style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

function Checklist({ block, body }) {
  const items = (block.items ?? [])
    .map((it) => ({ ...it, value: getPath(body, it.value_path) }))
    .filter((it) => usable(it.value));
  if (items.length === 0) return null;

  return (
    <div className="card rows">
      {items.map((it, i) => {
        const ok = passed(it.value, it.pass_when);
        return (
          <div className="row" key={i}>
            <span className="row-k">{it.label}</span>
            <span className={ok ? "tick" : "tick tick-bad"} aria-hidden="true">{ok ? "✓" : "!"}</span>
            <span className={ok ? "tag" : "tag tag-bad"}>{display(it.value)}</span>
          </div>
        );
      })}
    </div>
  );
}

function Facts({ block, body }) {
  const items = (block.items ?? [])
    .map((it) => ({ ...it, value: getPath(body, it.value_path) }))
    .filter((it) => usable(it.value));
  if (items.length === 0) return null;

  return (
    <div className="card rows">
      {items.map((it, i) => (
        <div className="row" key={i}>
          <span className="row-k">{it.label}</span>
          <span className={it.mono ? "row-v mono" : "row-v"}>{display(it.value)}</span>
        </div>
      ))}
    </div>
  );
}

function Signals({ block, body }) {
  const raw = getPath(body, block.path);
  if (!Array.isArray(raw) || raw.length === 0) return null;

  const nameKey = block.name_key ?? "name";
  const weightKey = block.weight_key ?? "weight";
  const rows = raw
    .map((r) => ({ name: r?.[nameKey], weight: Number(r?.[weightKey]) }))
    .filter((r) => usable(r.name) && Number.isFinite(r.weight));
  if (rows.length === 0) return null;

  const peak = Math.max(...rows.map((r) => Math.abs(r.weight))) || 1;

  return (
    <div className="card">
      {block.label && <div className="block-l">{block.label}</div>}
      {rows.map((r, i) => (
        <div className="sig" key={i}>
          <span className="sig-n">{String(r.name).replace(/[_-]+/g, " ")}</span>
          <span className="sig-track">
            <span
              className={r.weight < 0 ? "sig-bar neg" : "sig-bar pos"}
              style={{ width: `${(Math.abs(r.weight) / peak) * 45}%` }}
            />
          </span>
          <span className="sig-w">{r.weight > 0 ? `+${r.weight}` : r.weight}</span>
        </div>
      ))}
    </div>
  );
}

// A real API can return hundreds of rows (a year of calendar events, a
// full order history). Nobody presents a 272-row table, so cap it here
// even when the agent forgets to — this is the frontend's layout call,
// not the agent's.
const DEFAULT_MAX_ROWS = 8;

function rowLimit(block) {
  const n = Number(block.max_rows);
  return Number.isFinite(n) && n > 0 ? n : DEFAULT_MAX_ROWS;
}

function MoreFooter({ hidden, noun }) {
  if (hidden <= 0) return null;
  return (
    <div className="more">
      + {hidden.toLocaleString()} more {noun}
    </div>
  );
}

function Count({ block, body }) {
  const raw = getPath(body, block.path);
  if (!Array.isArray(raw)) return null;
  // Aggregation the response itself doesn't carry — "272 events" is the
  // obvious headline for a list endpoint, but no field holds that number.
  return (
    <div className="card">
      <div className={`metric ${toneClass(block.tone)}`}>
        {raw.length.toLocaleString()}
        {block.unit && <span className="metric-u">{block.unit}</span>}
      </div>
      {block.label && <div className="metric-l">{block.label}</div>}
    </div>
  );
}

function ListBlock({ block, body }) {
  const raw = getPath(body, block.path);
  if (!Array.isArray(raw)) return null;

  if (raw.length === 0) {
    return block.empty_text ? (
      <div className="verdict tone-pass">
        <div className="verdict-ic" aria-hidden="true">✓</div>
        <div><div className="verdict-t">{block.empty_text}</div></div>
      </div>
    ) : null;
  }

  const limit = rowLimit(block);
  const shown = raw.slice(0, limit).map((item) => listRow(item, block));
  const usableRows = shown.filter((r) => r !== null);
  if (usableRows.length === 0) return null;

  return (
    <div className="card rows">
      {block.label && <div className="block-l">{block.label}</div>}
      {usableRows.map((row, i) => (
        <div className="row" key={i}>
          <span className="row-k">{row.primary}</span>
          {row.secondary && <span className="row-v">{row.secondary}</span>}
        </div>
      ))}
      <MoreFooter hidden={raw.length - shown.length} noun={block.noun ?? "items"} />
    </div>
  );
}

// An array of records is really a `table`, but agents reach for `list`
// anyway. Rendering the whole object as JSON puts
// {"title":"Candle lighting: 5:38pm","date":...} on a prospect's screen,
// so pick the one field a person would actually read instead.
const LABEL_KEYS = ["title", "name", "label", "summary", "description", "message", "id"];
const SUB_KEYS = ["date", "time", "status", "category", "type", "value", "amount"];

function listRow(item, block) {
  if (item === null || item === undefined) return null;
  if (typeof item !== "object") {
    return { primary: String(item).replace(/[_-]+/g, " "), secondary: null };
  }

  const pick = (keys, explicit) => {
    if (explicit && usable(item[explicit])) return display(item[explicit]);
    const key = keys.find((k) => usable(item[k]) && typeof item[k] !== "object");
    return key ? display(item[key]) : null;
  };

  const primary = pick(LABEL_KEYS, block.label_key);
  // Nothing human-readable in this record — skip it rather than dump
  // JSON onto the screen.
  if (!primary) return null;
  return { primary, secondary: pick(SUB_KEYS, block.sub_key) };
}

function TableBlock({ block, body }) {
  const raw = getPath(body, block.path);
  const cols = block.columns ?? [];
  if (!Array.isArray(raw) || raw.length === 0 || cols.length === 0) return null;

  const limit = rowLimit(block);
  const shown = raw.slice(0, limit);

  return (
    <div className="card">
      {block.label && <div className="block-l">{block.label}</div>}
      {/* Wide tables scroll inside their own box — the screen never
          scrolls sideways during a presentation. */}
      <div className="table-scroll">
        <table className="tbl">
          <thead>
            <tr>{cols.map((c, i) => <th key={i}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {shown.map((row, i) => (
              <tr key={i}>
                {cols.map((c, j) => {
                  const v = getPath(row, c.key);
                  return <td key={j}>{usable(v) ? display(v) : "—"}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <MoreFooter hidden={raw.length - shown.length} noun={block.noun ?? "rows"} />
    </div>
  );
}

const RENDERERS = {
  identity: Identity,
  count: Count,
  verdict: Verdict,
  metric: Metric,
  gauge: Gauge,
  meter: Meter,
  checklist: Checklist,
  facts: Facts,
  signals: Signals,
  list: ListBlock,
  table: TableBlock,
};

export default function ResultView({ blocks, body }) {
  if (!Array.isArray(blocks) || blocks.length === 0) return null;

  const rendered = blocks
    .map((block, i) => {
      const Renderer = RENDERERS[block?.type];
      // An unknown block type is skipped rather than thrown — the agent
      // may name a type this frontend doesn't implement yet.
      if (!Renderer) return null;
      return <Renderer key={i} block={block} body={body} />;
    })
    .filter(Boolean);

  return rendered.length > 0 ? <>{rendered}</> : null;
}
