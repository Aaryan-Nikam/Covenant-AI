import { supabaseAdmin } from '../supabase.js';
import { normalizeCandidate, lookupKey } from './normalizer.js';
import { PROVIDERS } from '../providers/index.js';

export async function getUserProviders(userId) {
  const { data, error } = await supabaseAdmin
    .from('provider_keys')
    .select('provider, api_key, api_secret, is_active, priority')
    .eq('user_id', userId)
    .eq('is_active', true)
    .order('priority', { ascending: true });

  if (error) throw error;
  return data || [];
}

export async function getCache(key) {
  const { data, error } = await supabaseAdmin
    .from('enrichment_cache')
    .select('*')
    .eq('lookup_key', key)
    .gt('expires_at', new Date().toISOString())
    .maybeSingle();

  if (error) throw error;
  return data;
}

export async function setCache(key, candidate, result) {
  const { error } = await supabaseAdmin
    .from('enrichment_cache')
    .upsert({
      lookup_key: key,
      linkedin_url: candidate.linkedinUrl,
      first_name: candidate.firstName,
      last_name: candidate.lastName,
      company: candidate.company,
      domain: candidate.domain,
      email: result.email,
      confidence: result.confidence,
      source: result.source,
      verified: result.verified,
      raw_response: result.raw,
      expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
    }, { onConflict: 'lookup_key' });

  if (error) throw error;
}

export async function logUsage(userId, { lookupType = 'single', providerUsed = null, cacheHit = false } = {}) {
  const { error } = await supabaseAdmin.from('usage_log').insert({
    user_id: userId,
    lookup_type: lookupType,
    provider_used: providerUsed,
    cache_hit: cacheHit
  });
  if (error) throw error;
}

export async function enrichCandidate(input, { userId, lookupType = 'single' }) {
  const candidate = normalizeCandidate(input);
  const key = lookupKey(candidate);
  const providersTried = [];

  const cached = await getCache(key);
  if (cached?.email) {
    await logUsage(userId, { lookupType, providerUsed: cached.source, cacheHit: true });
    return {
      candidate,
      email: cached.email,
      confidence: cached.confidence,
      verified: cached.verified,
      source: cached.source,
      cacheHit: true,
      providersTried
    };
  }

  const userProviders = await getUserProviders(userId);
  if (!userProviders.length) {
    return {
      candidate,
      email: null,
      confidence: null,
      verified: false,
      source: null,
      cacheHit: false,
      providersTried,
      error: 'No active providers configured.'
    };
  }

  for (const providerConfig of userProviders) {
    const adapter = PROVIDERS[providerConfig.provider];
    if (!adapter) continue;

    try {
      providersTried.push({ provider: providerConfig.provider, status: 'attempted' });
      const result = await adapter.findEmail(candidate, providerConfig.api_key);
      if (result?.email) {
        await setCache(key, candidate, result);
        await logUsage(userId, { lookupType, providerUsed: result.source, cacheHit: false });
        providersTried[providersTried.length - 1].status = 'found';
        return {
          candidate,
          ...result,
          cacheHit: false,
          providersTried
        };
      }
      providersTried[providersTried.length - 1].status = 'no_result';
    } catch (err) {
      providersTried[providersTried.length - 1].status = 'error';
      providersTried[providersTried.length - 1].error = err.message;
    }
  }

  await logUsage(userId, { lookupType, providerUsed: null, cacheHit: false });
  return {
    candidate,
    email: null,
    confidence: null,
    verified: false,
    source: null,
    cacheHit: false,
    providersTried
  };
}
