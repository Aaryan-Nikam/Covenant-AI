import { fetchJson, normalizeEmailResult } from './utils.js';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export const dropcontact = {
  name: 'dropcontact',
  async findEmail(candidate, apiKey) {
    const submit = await fetchJson('https://api.dropcontact.io/batch', {
      method: 'POST',
      headers: { 'X-Access-Token': apiKey },
      body: JSON.stringify({
        data: [{
          first_name: candidate.firstName,
          last_name: candidate.lastName,
          company: candidate.company,
          website: candidate.domain
        }]
      })
    });

    const requestId = submit?.request_id || submit?.id;
    if (!requestId) {
      throw new Error('Dropcontact did not return a request id.');
    }

    let result = null;
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await sleep(5000);
      result = await fetchJson(`https://api.dropcontact.io/batch/${requestId}`, {
        headers: { 'X-Access-Token': apiKey }
      });
      if (result?.success || result?.status === 'complete' || result?.data?.length) break;
    }

    const row = result?.data?.[0] || result?.result?.[0] || {};
    return normalizeEmailResult({
      email: row.email || row.email_address,
      confidence: row.email_score || null,
      verified: Boolean(row.email),
      raw: result,
      source: 'dropcontact'
    });
  },
  async testKey(apiKey) {
    await fetchJson('https://api.dropcontact.io/credits', {
      headers: { 'X-Access-Token': apiKey }
    });
    return true;
  }
};
