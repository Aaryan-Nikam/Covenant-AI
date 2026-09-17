import { fetchJson, normalizeEmailResult } from './utils.js';

export const prospeo = {
  name: 'prospeo',
  async findEmail(candidate, apiKey) {
    const body = await fetchJson('https://api.prospeo.io/linkedin-email-finder', {
      method: 'POST',
      headers: { 'X-KEY': apiKey },
      body: JSON.stringify({ url: candidate.linkedinUrl })
    });
    return normalizeEmailResult({
      email: body?.response?.email || body?.email,
      confidence: body?.response?.confidence || null,
      verified: Boolean(body?.response?.email_status === 'valid' || body?.verified),
      raw: body,
      source: 'prospeo'
    });
  },
  async testKey(apiKey) {
    await fetchJson('https://api.prospeo.io/account-information', {
      headers: { 'X-KEY': apiKey }
    });
    return true;
  }
};
