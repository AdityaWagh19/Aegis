import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Wordmark } from '../components/Logo';
import { clearSession, getSession } from '../lib/auth';

/**
 * App shell (design.md §5.3): left sidebar with nav + env chip + sign out;
 * content region max-width 1200px. Wraps children in the demo AuthGuard.
 * Responsive: sidebar collapses to a slide-in drawer on mobile (<lg).
 */

const NAV_ITEMS = [
  { to: '/app', label: 'Overview', end: true },
  { to: '/app/batch', label: 'Batches', end: false },
  { to: '/app/audit', label: 'Audit', end: false },
];

export default function AppShell({ title, children }: { title: string; children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const authed = getSession();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    document.title = `${title} · Aegis`;
  }, [title]);

  // Close drawer on route change
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  if (!authed) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }

  const handleSignOut = () => {
    clearSession();
    navigate('/login');
  };

  const sidebarContent = (
    <>
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
    </>
  );

  return (
    <div className="min-h-screen bg-stone-canvas flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-60 shrink-0 border-r border-stone-border bg-stone-canvas flex-col sticky top-0 h-screen">
        {sidebarContent}
      </aside>

      {/* Mobile drawer overlay */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <button
            aria-label="Close menu"
            className="absolute inset-0 bg-soot/30 cursor-default"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-64 bg-stone-canvas border-r border-stone-border shadow-xl flex flex-col">
            {sidebarContent}
          </aside>
        </div>
      )}

      <div className="flex-1 min-w-0">
        {/* Mobile top bar with hamburger */}
        <header className="lg:hidden h-48 border-b border-stone-border bg-stone-canvas/95 backdrop-blur flex items-center justify-between px-16 sticky top-0 z-40">
          <button
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            className="flex flex-col gap-4 p-8 -ml-8"
          >
            <span className="block w-20 h-[2px] bg-ink-black rounded-full" />
            <span className="block w-20 h-[2px] bg-ink-black rounded-full" />
            <span className="block w-14 h-[2px] bg-ink-black rounded-full" />
          </button>
          <h1 className="font-roobert text-[16px] text-ink-black">{title}</h1>
          <div className="w-28" /> {/* Spacer for centering */}
        </header>

        {/* Desktop title bar */}
        <header className="hidden lg:flex h-48 border-b border-stone-border bg-stone-canvas/95 backdrop-blur items-center px-24 sticky top-0 z-30">
          <h1 className="font-roobert text-subheading leading-subheading tracking-subheading text-ink-black">
            {title}
          </h1>
        </header>

        <main className="mx-auto max-w-[1200px] px-16 md:px-24 py-24 md:py-32 flex flex-col gap-16 md:gap-24">
          {children}
        </main>
      </div>
    </div>
  );
}
