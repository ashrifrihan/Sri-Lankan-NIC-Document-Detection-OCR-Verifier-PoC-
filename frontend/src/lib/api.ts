import { NICValidationResult, VerificationResponse } from './types';

export async function trainAnalysis(requestId: string, nicNumber: string, fullName: string) {
  const res = await fetch(`/api/train/${encodeURIComponent(requestId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nic_number: nicNumber, full_name: fullName }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : 'Could not save training feedback.');
  }
}

export async function checkBackendHealth() {
  const res = await fetch(`/api/health`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

export async function validateNIC(nicNumber: string): Promise<NICValidationResult> {
  const res = await fetch(`/api/validate-nic`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({ nic_number: nicNumber }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Validation error ${res.status}`);
  }

  return res.json();
}

export async function verifyNICDocument(formData: FormData): Promise<VerificationResponse> {
  const signal = AbortSignal.timeout(90000);
  const res = await fetch(`/api/verify`, {
    method: 'POST',
    body: formData,
    signal,
  }).catch(() => {
    if (signal.aborted) throw new Error('Analysis took too long. Try again with a clear, tightly framed image.');
    throw new Error('Could not reach the NIC API. Check that the FastAPI backend is running, then retry.');
  });

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    if (typeof err?.detail === 'string') throw new Error(err.detail);
    if (res.status === 502 || res.status === 503 || res.status === 504 || (!err && res.status === 500)) {
      throw new Error('The NIC API did not respond. Check the FastAPI terminal, then retry.');
    }
    throw new Error(`Verification failed (HTTP ${res.status}).`);
  }

  return res.json();
}
