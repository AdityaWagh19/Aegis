import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Wordmark } from '../components/Logo';

/**
 * Centered auth shell (design.md §5.3): full-canvas centering with a single
 * flat card. The shield mascot sticker is allowed once here (§2.7).
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-stone-canvas flex flex-col">
      <header className="h-48 flex items-center px-16 border-b border-stone-border">
        <Link to="/" aria-label="Aegis home" className="mx-auto md:mx-0">
          <Wordmark />
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center px-16 py-64">
        <div className="w-full max-w-[400px]">{children}</div>
      </main>

      {/* Mascot sticker — outline SVG, one appearance, never animated (design.md §2.7) */}
      <svg
        width="72"
        height="72"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
        className="fixed bottom-8 right-8 opacity-70 drop-shadow-[0_2px_4px_rgba(0,0,0,0.25)] hidden md:block"
      >
        <path
          d="M12 2.5 4.5 5.5v6c0 5 3.2 8.4 7.5 10 4.3-1.6 7.5-5 7.5-10v-6L12 2.5Z"
          stroke="#a8a29e"
          strokeWidth="1"
          strokeLinejoin="round"
        />
        <circle cx="10" cy="10.5" r="0.9" fill="#78716c" />
        <circle cx="14.5" cy="10.5" r="0.9" fill="#78716c" />
        <path d="M10.5 13.5c.9.8 2.1.8 3 0" stroke="#78716c" strokeWidth="0.9" strokeLinecap="round" />
      </svg>
    </div>
  );
}
