import { useState, type ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Wordmark } from '../components/Logo';

const navLinkCls =
  'flex items-center px-12 text-[14px] text-warm-gray hover:text-ink-black transition-colors';

/**
 * Public marketing shell: minimal top bar — logo left, centered nav links,
 * sign-in + single cyan CTA right. Footer on stone-canvas with hairline border.
 * Responsive: mobile hamburger menu below md breakpoint.
 */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-stone-canvas flex flex-col">
      <header className="sticky top-0 z-40 bg-stone-canvas/95 backdrop-blur border-b border-stone-border shadow-subtle">
        <div className="mx-auto max-w-[1200px] h-48 flex items-center justify-between px-16">
          <Link to="/" aria-label="Aegis home">
            <Wordmark />
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center h-32 gap-4">
            <a href="/#how" className={navLinkCls}>Product</a>
            <a href="/#categories" className={navLinkCls}>Categories</a>
            <NavLink to="/docs" className={navLinkCls}>Docs</NavLink>
          </nav>

          <div className="hidden md:flex items-center gap-12">
            <NavLink to="/login" className={navLinkCls}>Sign in</NavLink>
            <Link
              to="/login"
              className="rounded-full bg-cyan-signal border border-cyan-edge text-pure-white font-inter font-medium text-[14px] px-16 py-8 hover:bg-cyan-edge transition-colors"
            >
              Open console
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden flex flex-col gap-4 p-8 -mr-8"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
          >
            {menuOpen ? (
              <span className="text-[18px] text-ink-black leading-none">✕</span>
            ) : (
              <>
                <span className="block w-[20px] h-[2px] bg-ink-black rounded-full" />
                <span className="block w-[20px] h-[2px] bg-ink-black rounded-full" />
                <span className="block w-[14px] h-[2px] bg-ink-black rounded-full" />
              </>
            )}
          </button>
        </div>

        {/* Mobile menu with backdrop */}
        {menuOpen && (
          <div className="md:hidden fixed inset-x-0 top-48 bottom-0 z-50" role="dialog" aria-modal="true">
            <button
              aria-label="Close menu"
              className="absolute inset-0 bg-soot/20 cursor-default"
              onClick={() => setMenuOpen(false)}
            />
            <nav className="relative border-t border-stone-border px-16 py-16 flex flex-col gap-4 bg-stone-canvas shadow-xl">
              <a href="/#how" className={navLinkCls} onClick={() => setMenuOpen(false)}>Product</a>
              <a href="/#categories" className={navLinkCls} onClick={() => setMenuOpen(false)}>Categories</a>
              <NavLink to="/docs" className={navLinkCls} onClick={() => setMenuOpen(false)}>Docs</NavLink>
              <div className="border-t border-stone-border my-8" />
              <NavLink to="/login" className={navLinkCls} onClick={() => setMenuOpen(false)}>Sign in</NavLink>
              <Link
                to="/login"
                className="rounded-full bg-cyan-signal border border-cyan-edge text-pure-white font-medium text-[14px] px-16 py-8 text-center mt-8"
                onClick={() => setMenuOpen(false)}
              >
                Open console
              </Link>
            </nav>
          </div>
        )}
      </header>

      <main className="flex-1">{children}</main>

      {/* Footer — stone-canvas with hairline border, column structure */}
      <footer className="border-t border-stone-border bg-stone-canvas">
        <div className="mx-auto max-w-[1200px] px-16 pt-48 pb-32">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-0 md:gap-64">
            {/* Brand */}
            <div className="flex flex-col items-start gap-12 pb-32 md:pb-0">
              <Link to="/" aria-label="Aegis home" className="self-start inline-block">
                <Wordmark />
              </Link>
              <p className="text-[13px] text-warm-gray max-w-[280px]">
                Compliant recovery for UPI Autopay and e-NACH mandates.
              </p>
            </div>

            {/* Product */}
            <div className="flex flex-col gap-8 py-32 md:py-0 border-t md:border-t-0 border-stone-border">
              <p className="text-[11px] font-medium uppercase tracking-[0.025em] text-ash-gray">
                Product
              </p>
              <Link to="/app" className="text-[13px] text-warm-gray hover:text-ink-black transition-colors">Overview</Link>
              <Link to="/app/batch" className="text-[13px] text-warm-gray hover:text-ink-black transition-colors">Batches</Link>
              <Link to="/app/audit" className="text-[13px] text-warm-gray hover:text-ink-black transition-colors">Audit</Link>
            </div>

            {/* Resources */}
            <div className="flex flex-col gap-8 py-32 md:py-0 border-t md:border-t-0 border-stone-border">
              <p className="text-[11px] font-medium uppercase tracking-[0.025em] text-ash-gray">
                Resources
              </p>
              <Link to="/docs" className="text-[13px] text-warm-gray hover:text-ink-black transition-colors">Docs</Link>
              <Link to="/login" className="text-[13px] text-warm-gray hover:text-ink-black transition-colors">Sign in</Link>
            </div>
          </div>

          {/* Bottom hairline + disclaimer */}
          <div className="border-t border-stone-border mt-32 pt-16 flex flex-col md:flex-row md:items-center justify-between gap-8">
            <p className="text-[12px] text-ash-gray">© 2026 Aegis</p>
            <p className="text-[12px] text-ash-gray">Razorpay Test Mode — no live money moved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
