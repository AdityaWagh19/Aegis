import { useEffect, type ReactNode } from 'react';
import { NavLink, Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Wordmark } from '../components/Logo';
import { clearSession, getSession } from '../lib/auth';

/**
 * App shell (design.md §5.3): left sidebar with nav + env chip + sign out;
 * content region max-width 1200px. Wraps children in the demo AuthGuard.
 */

const NAV_ITEMS = [
  { to: '/app', label: 'Overview', end: true },
  { to: '/app/batch', label: 'Batches', end: false },
  { to: '/app/audit', label: 'Audit trail', end: false },
];

export default function AppShell({ title, children }: { title: string; children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const authed = getSession();

  useEffect(() => {
    document.title = `${title} · Aegis`;
  }, [title]);

  if (!authed) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }

  const handleSignOut = () => {
    clearSession();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-stone-canvas flex">
      <aside className="w-60 shrink-0 border-r border-stone-border bg-stone-canvas flex flex-col sticky top-0 h-screen">
        <div className="h-48 flex items-center px-16 border-b border-stone-border">
          <Link to="/" aria-label="Aegis home">
            <Wordmark />
          </Link>
        </div>

        <nav className="flex flex-col gap-4 p-12 flex-1">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-full px-16 py-8 text-[14px] transition-colors ${
                  isActive
                    ? 'bg-soot text-pure-white'
                    : 'text-warm-gray hover:text-ink-black hover:bg-pure-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-12 border-t border-stone-border flex flex-col gap-8">
          <span className="self-start rounded-full border border-stone-border bg-pure-white text-info text-[11px] font-medium px-12 py-4">
            Test mode
          </span>
          <button
            onClick={handleSignOut}
            className="self-start rounded-full border border-stone-border bg-transparent text-ink-black text-[13px] px-16 py-8 hover:border-stone-muted hover:bg-pure-white transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        <header className="h-48 border-b border-stone-border bg-stone-canvas/95 backdrop-blur flex items-center px-24 sticky top-0 z-30">
          <h1 className="font-roobert text-subheading leading-subheading tracking-subheading text-ink-black">
            {title}
          </h1>
        </header>
        <main className="mx-auto max-w-[1200px] px-24 py-32 flex flex-col gap-24">{children}</main>
      </div>
    </div>
  );
}
