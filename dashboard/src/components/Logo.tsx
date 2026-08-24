// Brand mark: shield glyph + wordmark (design.md §2.7 — compact black glyph, Inter 500 wordmark).
export function LogoGlyph({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 2.5 4.5 5.5v6c0 5 3.2 8.4 7.5 10 4.3-1.6 7.5-5 7.5-10v-6L12 2.5Z"
        stroke="#0c0a09"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="m12 7-3.5 5h3l-.8 4.5L15.5 11h-3L13.5 7 12 7Z" fill="#3ba6f1" />
    </svg>
  );
}

export function Wordmark({ dark = false }: { dark?: boolean }) {
  return (
    <span className="inline-flex items-center gap-8">
      <LogoGlyph />
      <span
        className={`text-[14px] font-medium tracking-tight ${dark ? 'text-pure-white' : 'text-ink-black'}`}
      >
        Aegis
      </span>
    </span>
  );
}
