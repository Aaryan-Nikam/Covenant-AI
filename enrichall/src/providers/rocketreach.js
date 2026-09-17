import { fetchJson, normalizeEmailResult } from './utils.js';

export const rocketreach = {
  name: 'rocketreach',
  async findEmail(candidate, apiKey) {
    const params = new URLSearchParams({
      name: candidate.fullName,
      current_employer: candidate.company,
      linkedin_url: candidate.linkedinUrl
    });
    const body = await fetchJson(`https://api.rocketreach.co/v2/api/lookupProfile?${params}`, {
      headers: { 'Api-Key': apiKey }
    });
    const emails = body?.emails || [];
    const best = emails.find(e => e.email) || emails[0];
    return normalizeEmailResult({
      email: best?.email,
      confidence: best?.grade ? null : best?.confidence,
      verified: Boolean(best?.smtp_valid === 'valid' || best?.type === 'professional'),
      raw: body,
      source: 'rocketreach'
    });
  },
  async testKey(apiKey) {
    await fetchJson('https://api.rocketreach.co/v2/api/account', {
      headers: { 'Api-Key': apiKey }
    });
    return true;
  }
};
