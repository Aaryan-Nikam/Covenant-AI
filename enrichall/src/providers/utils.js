import fetch from 'node-fetch';

export async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {})
    }
  });

  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { raw: text };
  }

  if (!res.ok) {
    const err = new Error(body?.error || body?.message || `Provider request failed with ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }

  return body;
}

export function normalizeEmailResult({ email, confidence = null, verified = false, raw = null, source }) {
  if (!email) return { email: null, confidence, verified, raw, source };
  return {
    email: String(email).trim().toLowerCase(),
    confidence,
    verified: Boolean(verified),
    raw,
    source
  };
}
