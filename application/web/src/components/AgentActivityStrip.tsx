import { useState } from "react";
import type { ToolEvent } from "../types";
import { deriveAgentActivity } from "../utils/agentActivity";

interface Props {
  waiting: boolean;
  streamEvents: ToolEvent[];
  streamText?: string;
}

export function AgentActivityStrip({
  waiting,
  streamEvents,
  streamText = "",
}: Props) {
  const [open, setOpen] = useState(false);

  if (!waiting) return null;

  const activity = deriveAgentActivity(streamEvents, streamText);
  if (!activity) return null;

  const hasSteps = activity.steps.length > 0;

  return (
    <div className="agent-activity-strip" role="status" aria-live="polite">
      <button
        type="button"
        className={`agent-activity-summary${open ? " is-open" : ""}`}
        aria-expanded={hasSteps ? open : undefined}
        aria-controls={hasSteps ? "agent-activity-steps" : undefined}
        disabled={!hasSteps}
        onClick={() => hasSteps && setOpen((v) => !v)}
      >
        <span className="agent-activity-icon" aria-hidden="true">
          <span className="agent-activity-dots">
            <i />
            <i />
          </span>
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path
              d="M3.5 1.5 7 5 3.5 8.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span className="agent-activity-text">{activity.summary}</span>
        {hasSteps ? (
          <span className="agent-activity-caret" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 12 12">
              <path
                d={open ? "M3 7.5 6 4.5 9 7.5" : "M4.5 3 7.5 6 4.5 9"}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
        ) : null}
      </button>
      {open && hasSteps ? (
        <ol id="agent-activity-steps" className="agent-activity-steps">
          {activity.steps.map((step) => (
            <li
              key={step.id}
              className={`agent-activity-step${step.pending ? " is-pending" : ""}`}
            >
              <span className="agent-activity-step-mark" aria-hidden="true" />
              <span className="agent-activity-step-body">
                <span className="agent-activity-step-label">{step.label}</span>
                {step.detail ? (
                  <span className="agent-activity-step-detail">{step.detail}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
