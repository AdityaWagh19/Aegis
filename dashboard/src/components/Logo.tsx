// Brand lockup: processed from the user's Aegis_web.png (transparent, cropped).
// The mark + wordmark image replaces the previous inline SVG placeholder.
const LOGO_SRC = "/aegis-logo.png";

export function LogoGlyph({ size = 28 }: { size?: number }) {
  return (
    <img
      src="/favicon.png"
      alt=""
      width={size}
      height={size}
      className="rounded-[4px]"
      aria-hidden="true"
    />
  );
}

export function Wordmark({ dark = false }: { dark?: boolean }) {
  return (
    <img
      src={LOGO_SRC}
      alt="Aegis"
      className={`h-7 w-auto ${dark ? "opacity-95" : ""}`}
    />
  );
}
