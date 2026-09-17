import { fetchJson, normalizeEmailResult } from './utils.js';

export const apollo = {
  name: 'apollo',
  async findEmail(candidate, apiKey) {
    const body = await fetchJson('https://api.apollo.io/api/v1/people/match', {
      method: 'POST',
      headers: { 'x-api-key': apiKey },
      body: JSON.stringify({
        first_name: candidate.firstName,
        last_name: candidate.lastName,
        organization_name: candidate.company,
        linkedin_url: candidate.linkedinUrl
      })
    });

    const person = body?.person || body;
    return normalizeEmailResult({
      email: person?.email,
      confidence: person?.email_status === 'verified' ? 95 : null,
      verified: person?.email_status === 'verified',
      raw: body,
      source: 'apollo'
    });
  },
  async testKey(apiKey) {
    await fetchJson('https://api.apollo.io/api/v1/auth/health', {
      headers: { 'x-api-key': apiKey }
    });
    return true;
  }
};
