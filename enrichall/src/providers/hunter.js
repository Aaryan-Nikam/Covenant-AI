import { fetchJson, normalizeEmailResult } from './utils.js';

export const hunter = {
  name: 'hunter',
  async findEmail(candidate, apiKey) {
    const params = new URLSearchParams({
      api_key: apiKey,
      first_name: candidate.firstName,
      last_name: candidate.lastName,
      domain: candidate.domain
    });
    const body = await fetchJson(`https://api.hunter.io/v2/email-finder?${params}`);
    return normalizeEmailResult({
      email: body?.data?.email,
      confidence: body?.data?.score || body?.data?.confidence || null,
      verified: Boolean(body?.data?.verification?.status === 'valid'),
      raw: body,
      source: 'hunter'
    });
  },
  async testKey(apiKey) {
    await fetchJson(`https://api.hunter.io/v2/account?api_key=${encodeURIComponent(apiKey)}`);
    return true;
  }
};
