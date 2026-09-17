CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS provider_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL CHECK (provider IN ('apollo','hunter','snov','rocketreach','prospeo','dropcontact')),
  api_key TEXT NOT NULL,
  api_secret TEXT,
  is_active BOOLEAN DEFAULT true,
  priority INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, provider)
);

CREATE TABLE IF NOT EXISTS enrichment_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lookup_key TEXT NOT NULL UNIQUE,
  linkedin_url TEXT,
  first_name TEXT,
  last_name TEXT,
  company TEXT,
  domain TEXT,
  email TEXT,
  confidence INT,
  source TEXT,
  verified BOOLEAN DEFAULT false,
  raw_response JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ DEFAULT now() + INTERVAL '30 days'
);

CREATE TABLE IF NOT EXISTS batch_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending','processing','complete','failed')),
  total_rows INT NOT NULL,
  processed_rows INT DEFAULT 0,
  found_emails INT DEFAULT 0,
  providers_used TEXT[],
  input_filename TEXT,
  result_csv_url TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS usage_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  lookup_type TEXT DEFAULT 'single',
  provider_used TEXT,
  cache_hit BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_lookup ON enrichment_cache(lookup_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON enrichment_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_usage_daily ON usage_log(user_id, created_at);

ALTER TABLE provider_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrichment_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage their own keys" ON provider_keys;
CREATE POLICY "Users can manage their own keys" ON provider_keys
  FOR ALL USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view their own jobs" ON batch_jobs;
CREATE POLICY "Users can view their own jobs" ON batch_jobs
  FOR ALL USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view their own usage" ON usage_log;
CREATE POLICY "Users can view their own usage" ON usage_log
  FOR ALL USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Anyone can read cache" ON enrichment_cache;
CREATE POLICY "Anyone can read cache" ON enrichment_cache
  FOR SELECT USING (true);

INSERT INTO storage.buckets (id, name, public)
VALUES ('batch-results', 'batch-results', true)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Users can read batch result files" ON storage.objects;
CREATE POLICY "Users can read batch result files" ON storage.objects
  FOR SELECT USING (bucket_id = 'batch-results');

DROP POLICY IF EXISTS "Service role can manage batch result files" ON storage.objects;
CREATE POLICY "Service role can manage batch result files" ON storage.objects
  FOR ALL USING (bucket_id = 'batch-results');
