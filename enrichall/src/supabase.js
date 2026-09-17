import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.SUPABASE_URL;
const anonKey = process.env.SUPABASE_ANON_KEY;
const serviceKey = process.env.SUPABASE_SERVICE_KEY;

export const hasSupabaseConfig = Boolean(supabaseUrl && anonKey && serviceKey);

export const supabaseAnon = hasSupabaseConfig
  ? createClient(supabaseUrl, anonKey)
  : null;

export const supabaseAdmin = hasSupabaseConfig
  ? createClient(supabaseUrl, serviceKey, {
      auth: {
        autoRefreshToken: false,
        persistSession: false
      }
    })
  : null;

export function requireSupabase() {
  if (!hasSupabaseConfig) {
    const err = new Error('Supabase is not configured. Add SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_KEY.');
    err.status = 503;
    throw err;
  }
}
