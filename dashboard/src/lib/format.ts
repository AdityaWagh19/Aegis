const ACTION_LABELS: Record<string, string> = {
  RETRY_AFTER_BACKOFF: 'Retry after backoff',
  SCHEDULE_POST_SALARY: 'Schedule post-salary',
  SEND_UPI_INTENT_PUSH: 'Send UPI intent push',
  SEND_MANDATE_RENEWAL_LINK: 'Send renewal link',
  SEND_HINGLISH_NUDGE: 'Send Hinglish nudge',
  ESCALATE_TO_HUMAN: 'Escalate to human',
  NO_ACTION_MONITORING: 'No action — monitoring',
};

const OUTCOME_LABELS: Record<string, string> = {
  executed: 'Executed',
  mocked: 'Mocked',
  escalated: 'Escalated',
  failed: 'Failed',
};

/** Humanized action name; falls back to the raw enum. */
export function humanizeAction(action: string | null): string {
  if (!action) return '—';
  return ACTION_LABELS[action] ?? action;
}

export function humanizeOutcome(outcome: string): string {
  return OUTCOME_LABELS[outcome] ?? outcome;
}

export function outcomeTone(outcome: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (outcome) {
    case 'executed':
      return 'success';
    case 'escalated':
      return 'warning';
    case 'failed':
      return 'danger';
    default:
      return 'info';
  }
}

/** Rs. with en-IN digit grouping, e.g. Rs. 1,23,456 */
export function fmtINR(n: number): string {
  return `Rs. ${n.toLocaleString('en-IN')}`;
}

export function fmtPct(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits)}%`;
}

export function shortId(id: string | null | undefined, chars = 8): string {
  if (!id) return '—';
  return id.length <= chars ? id : `${id.slice(0, chars)}…`;
}

export function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

export function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-IN', { hour12: false });
}
