import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import AuthLayout from '../layouts/AuthLayout';
import { setSession } from '../lib/auth';

/**
 * Demo onboarding gate (design.md §5.4). No backend auth exists until Phase 9;
 * the copy says so plainly. Both sign-in and guest paths set the local session.
 */
export default function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get('next') || '/app';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [hint, setHint] = useState<string | null>(null);

  const proceed = () => {
    setSession();
    navigate(next, { replace: true });
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setHint('Enter any email to continue — nothing is validated or stored.');
      return;
    }
    if (password && password.length < 4) {
      setHint('That passphrase is a little short — try 4+ characters, or continue as guest.');
      return;
    }
    proceed();
  };

  return (
    <AuthLayout>
      <div className="bg-pure-white rounded-lg border border-stone-border shadow-md p-24">
        <h1 className="font-roobert font-normal text-[26px] leading-tight text-ink-black">
          Sign in to{' '}
          <span className="bg-sky-wash rounded-md px-8 text-cyan-edge">Aegis</span>
        </h1>
        <p className="mt-8 text-[13px] text-warm-gray">
          Your compliance console for failed UPI Autopay &amp; e-NACH mandates.
        </p>

        <form onSubmit={handleSubmit} className="mt-24 flex flex-col gap-16" noValidate>
          <label className="flex flex-col gap-4">
            <span className="text-[13px] font-medium text-ink-black">Work email</span>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="ops@yourcompany.in"
              autoComplete="email"
              className="rounded-[6px] border border-stone-muted bg-pure-white px-12 py-8 text-[14px] text-ink-black placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-cyan-signal"
            />
          </label>

          <label className="flex flex-col gap-4">
            <span className="text-[13px] font-medium text-ink-black">Passphrase</span>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              className="rounded-[6px] border border-stone-muted bg-pure-white px-12 py-8 text-[14px] text-ink-black placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-cyan-signal"
            />
          </label>

          {hint && (
            <p role="alert" className="text-[13px] text-danger bg-danger-tint rounded-md px-12 py-8">
              {hint}
            </p>
          )}

          <button
            type="submit"
            className="rounded-full bg-cyan-signal border border-cyan-edge text-pure-white font-medium px-16 py-8 hover:bg-cyan-edge transition-colors"
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={proceed}
            className="rounded-full border border-stone-border bg-transparent text-ink-black px-16 py-8 hover:bg-stone-canvas transition-colors"
          >
            Continue as guest
          </button>
        </form>

        <p className="mt-24 text-[12px] text-warm-gray">
          Demo build — sessions live only in your browser and no credentials are sent anywhere.{' '}
          <Link to="/docs" className="text-cyan-edge hover:underline">
            Read the docs
          </Link>
          .
        </p>
      </div>
    </AuthLayout>
  );
}
