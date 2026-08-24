import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadBatch } from '../api/aegis';
import type { BatchUploadResponse } from '../types/aegis';

interface Props {
  onResult: (result: BatchUploadResponse) => void;
}

/**
 * CSV dropzone with honest progress state (design.md §5.4 Batch page):
 * Tier-2 routing can make batches take tens of seconds — say so up front.
 */
export default function BatchUploader({ onResult }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!files[0]) return;
      setLoading(true);
      setError(null);
      setFileName(files[0].name);
      try {
        const result = await uploadBatch(files[0]);
        onResult(result);
      } catch (e: unknown) {
        let detail = 'Upload failed.';
        if (axiosError(e)) {
          const resp = e.response?.data as { detail?: string } | undefined;
          detail = resp?.detail ?? `${e.message}`;
        }
        setError(detail);
      } finally {
        setLoading(false);
      }
    },
    [onResult],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    maxFiles: 1,
    multiple: false,
  });

  return (
    <div className="flex flex-col gap-12">
      <div
        {...getRootProps()}
        role="button"
        aria-label="Upload mandates CSV"
        className={`rounded-2xl border-2 border-dashed p-48 text-center cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-signal ${
          isDragActive
            ? 'border-cyan-signal bg-sky-wash/20'
            : 'border-stone-muted hover:border-ash-gray bg-pure-white'
        }`}
      >
        <input {...getInputProps()} />

        {loading ? (
          <div className="flex flex-col items-center gap-8">
            <span
              aria-hidden="true"
              className="inline-block w-32 h-32 rounded-full border-2 border-stone-border border-t-cyan-signal animate-spin"
            />
            <p className="text-[14px] text-ink-black font-medium">Processing batch…</p>
            <p className="text-[13px] text-warm-gray max-w-[420px]">
              Ambiguous mandates are routed to the LLM one at a time. A 10–50 row batch usually
              finishes in under a minute.
            </p>
          </div>
        ) : (
          <>
            <p className="text-[15px] text-ink-black">
              {isDragActive ? 'Drop the CSV to start recovery' : 'Drag a CSV here, or click to browse'}
            </p>
            <p className="mt-8 text-[13px] text-warm-gray">
              One row per failed mandate · columns: mandate_id, customer_id, amount, mandate_type,
              product_category, decline_code, days_since_salary_credit, prior_bounce_count,
              is_revocable, attempt_number, timestamp
            </p>
            {fileName && <p className="mt-8 text-[12px] text-ash-gray">Last selected: {fileName}</p>}
          </>
        )}
      </div>

      {error && (
        <div role="alert" className="rounded-md bg-danger-tint border border-danger/30 text-danger text-[13px] px-16 py-8">
          {error}
        </div>
      )}
    </div>
  );
}

function axiosError(e: unknown): e is { response?: { data?: { detail?: string } }; message: string } {
  return typeof e === 'object' && e !== null && 'message' in e;
}
