import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Wordmark } from '../components/Logo';

const navLinkCls =
  'flex items-center px-12 text-[14px] text-warm-gray hover:text-ink-black transition-colors';

/**
 * Public marketing shell (design.md §5.3): minimal top bar — logo left,
 * centered nav links, sign-in + single cyan CTA right; inverted footer band.
 */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-stone-canvas flex flex-col">
      <header className="sticky top-0 z-40 bg-stone-canvas/95 backdrop-blur border-b border-stone-border shadow-subtle">
        <div className="mx-auto max-w-[1200px] h-48 flex items-center justify-between px-16">
          <Link to="/" aria-label="Aegis home">
            <Wordmark />
          </Link>
          <nav className="hidden md:flex items-center h-32 gap-4">
            <a href="/#how" className={navLinkCls}>
              How it works
            </a>
            <a href="/#categories" className={navLinkCls}>
              Failure categories
            </a>
            <NavLink to="/docs" className={navLinkCls}>
              Docs
            </NavLink>
          </nav>
          <div className="flex items-center gap-12">
            <NavLink to="/login" className={navLinkCls}>
              Sign in
            </NavLink>
            <Link
              to="/login"
              className="rounded-full bg-cyan-signal border border-cyan-edge text-pure-white font-inter font-medium text-[14px] px-16 py-8 hover:bg-cyan-edge transition-colors"
            >
              Open console
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="bg-soot text-pure-white mt-96">
        <div className="mx-auto max-w-[1200px] px-16 py-32 flex flex-col md:flex-row md:items-center justify-between gap-16">
          <Wordmark dark />
          <nav className="flex items-center gap-24 text-[13px] text-ash-gray">
            <a href="/#how" className="hover:text-pure-white transition-colors">
              How it works
            </a>
            <Link to="/docs" className="hover:text-pure-white transition-colors">
              Docs
            </Link>
            <Link to="/login" className="hover:text-pure-white transition-colors">
              Sign in
            </Link>
          </nav>
          <p className="text-[12px] text-ash-gray">
            Runs on Razorpay Test Mode only — no live money is ever moved.
          </p>
        </div>
      </footer>
    </div>
  );
}
