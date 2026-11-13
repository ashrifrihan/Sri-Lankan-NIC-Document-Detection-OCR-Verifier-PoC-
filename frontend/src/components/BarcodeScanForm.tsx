'use client';

import { useEffect, useState } from 'react';
import { ImageUploader } from './ImageUploader';

type ScanResult = {
  status: 'unread' | 'decoded' | 'ambiguous' | 'unavailable';
  nic_number: string | null;
  decoded_dob: string | null;
};

export function BarcodeScanForm() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  function selectPhoto(photo: File | null) {
    setFile(photo);
    setPreview(photo ? URL.createObjectURL(photo) : null);
    setResult(null);
    setError('');
  }

  async function scan(event: React.FormEvent) {
    event.preventDefault();
    if (!file || loading) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const body = new FormData();
      body.set('back_image', file);
      const response = await fetch('/api/scan-barcode', {
        method: 'POST', body, signal: AbortSignal.timeout(30000)
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : 'The scan service did not respond. Try again.');
      }
      setResult(data);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not scan the photo.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={scan} className="mx-auto max-w-xl space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
      <fieldset disabled={loading} className="space-y-4">
        <ImageUploader label="NIC back photo" description="Keep the full barcode in focus and free of glare"
          file={file} previewUrl={preview} onFileSelect={selectPhoto} required />
        <button type="submit" disabled={!file || loading}
          className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">
          {loading ? 'Scanning…' : 'Scan barcode'}
        </button>
      </fieldset>
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      {result && (
        <section aria-live="polite" className="rounded-xl bg-slate-50 p-4 text-sm text-slate-800">
          <p className="font-semibold">{{
            unread: 'Could not read the barcode. Try a sharper photo with the full code visible.',
            decoded: result.nic_number ? 'NIC number read from PDF417' : 'Barcode read. The payload format is unsupported.',
            ambiguous: 'Multiple barcode values found. Scan one card at a time.',
            unavailable: 'Barcode scanner unavailable. Try again.',
          }[result.status]}</p>
          {result.nic_number && <dl className="mt-2 grid grid-cols-2 gap-2">
            <dt>NIC number</dt><dd className="font-mono">{result.nic_number}</dd>
            {result.decoded_dob && <><dt>DOB decoded from NIC</dt><dd>{result.decoded_dob}</dd></>}
          </dl>}
        </section>
      )}
    </form>
  );
}
