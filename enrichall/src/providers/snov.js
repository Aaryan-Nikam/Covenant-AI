import { fetchJson, normalizeEmailResult } from './utils.js';

async function getAccessToken(apiKey) {
  const [clientId, clientSecret] = String(apiKey).split(':');
  if (!clientId || !clientSecret) {
    throw new Error('Snov key must be stored as clientId:clientSecret.');
  }
  const params = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: clientId,
    client_secret: clientSecret
  });
  const body = await fetchJson(`https://api.snov.io/v1/oauth/access_token?${params}`, { method: 'POST' });
  return body.access_token;
}

export const snov = {
  name: 'snov',
  async findEmail(candidate, apiKey) {
    const token = await getAccessToken(apiKey);
    const body = await fetchJson('https://api.snov.io/v1/get-emails-from-names', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        firstName: candidate.firstName,
        lastName: candidate.lastName,
        domain: candidate.domain
      })
    });
    const email = body?.data?.emails?.[0]?.email || body?.emails?.[0]?.email;
    return normalizeEmailResult({
      email,
      confidence: null,
      verified: Boolean(body?.data?.emails?.[0]?.status === 'valid'),
      raw: body,
      source: 'snov'
    });
  },
  async testKey(apiKey) {
    await getAccessToken(apiKey);
    return true;
  }
};
