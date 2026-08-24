const SESSION_KEY = 'aegis_session';

/**
 * Demo auth gate (design.md §5.5).
 * Aegis has no backend authentication until Phase 9 multi-tenancy ships;
 * this client-side session exists purely to demonstrate the onboarding flow.
 * The login page and app sidebar disclose this to the user.
 */
export function getSession(): boolean {
  try {
    return window.localStorage.getItem(SESSION_KEY) === 'active';
  } catch {
    return false;
  }
}

export function setSession(): void {
  try {
    window.localStorage.setItem(SESSION_KEY, 'active');
  } catch {
    /* storage unavailable — session simply won't persist */
  }
}

export function clearSession(): void {
  try {
    window.localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}
