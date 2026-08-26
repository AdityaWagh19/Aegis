// Brand lockup: processed from the user's Aegis_web.png (transparent, cropped).
// Uses inline styles for reliable sizing — our custom spacing scale doesn't
// include odd-numbered steps (h-7 generates no CSS in Tailwind v4).
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
      style={{ height: 28, width: 'auto' }}
      className={dark ? "opacity-95" : ""}
    />
  );
}
