interface Props {
  message: string | null;
}

/**
 * Hinglish draft preview — rendered verbatim; the caption clarifies it is a
 * mock (no real WhatsApp/SMS is sent in this build).
 */
export default function HinglishMessagePreview({ message }: Props) {
  if (!message) return null;
  return (
    <div className="rounded-lg border border-success/30 bg-success-tint p-16">
      <p className="text-[11px] font-medium uppercase tracking-[0.025em] text-success mb-4">
        Hinglish message (draft)
      </p>
      <p className="text-[14px] italic text-ink-black leading-body-lg">"{message}"</p>
      <p className="mt-8 text-[11px] text-warm-gray">
        Would send via WhatsApp/SMS — notifications are mocked in this build.
      </p>
    </div>
  );
}
