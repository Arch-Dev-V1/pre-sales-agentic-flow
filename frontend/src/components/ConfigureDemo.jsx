import { useState } from "react";

// Fixed, predefined questions only — deliberately not a chat interface.
// This is the boundary that keeps the product honest: the user picks
// from known options here, they don't type "make the button round" or
// direct the UI in freeform language anywhere in this app. If you're
// ever tempted to add a free-text field that shapes layout/structure
// rather than just narration content, that's a sign it's drifting
// outside what this tool is meant to be.

const QUESTIONS = [
  {
    key: "industry",
    label: "Which industry is the prospect in?",
    type: "select",
    options: [
      "Banking & Financial Services",
      "Insurance",
      "Healthcare",
      "Retail & E-commerce",
      "Telecom",
      "Gaming",
      "Other",
    ],
  },
  {
    key: "emphasis",
    label: "What should the demo emphasize?",
    type: "select",
    options: [
      "Fraud prevention & risk",
      "Compliance & regulatory",
      "Onboarding speed",
      "Operational efficiency",
      "Other",
    ],
  },
  {
    key: "tone",
    label: "What tone should the narration use?",
    type: "select",
    options: ["Formal & enterprise", "Modern & approachable"],
  },
  {
    key: "theme",
    label: "Visual theme",
    type: "select",
    options: ["Light", "Dark"],
  },
  {
    key: "companyName",
    label: "Prospect's company name (optional — shown in the demo, e.g. \"Acme Bank\")",
    type: "text",
    optional: true,
  },
  {
    key: "depth",
    label: "How much of the demo should be shown?",
    type: "select",
    options: ["Quick overview (3 steps)", "Full walkthrough (all verified steps)"],
  },
];

const DEFAULTS = Object.fromEntries(
  QUESTIONS.map((q) => [q.key, q.type === "select" ? q.options[0] : ""])
);

export default function ConfigureDemo({ onSubmit }) {
  const [answers, setAnswers] = useState(DEFAULTS);

  const update = (key) => (e) => setAnswers({ ...answers, [key]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(answers);
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>A few quick questions before we build the demo</h2>
      <p>
        These shape the story the agents tell — not the layout. There's no
        "make this button round" field here on purpose.
      </p>

      {QUESTIONS.map((q) => (
        <label key={q.key}>
          {q.label}
          {q.type === "select" ? (
            <select value={answers[q.key]} onChange={update(q.key)}>
              {q.options.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={answers[q.key]}
              onChange={update(q.key)}
              required={!q.optional}
            />
          )}
        </label>
      ))}

      <button type="submit">Build the demo</button>
    </form>
  );
}
