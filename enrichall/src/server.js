import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import multer from 'multer';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { requireSupabase, supabaseAdmin, supabaseAnon, hasSupabaseConfig } from './supabase.js';
import { requireAuth } from './middleware/auth.js';
import { enforceDailyLookupLimit } from './middleware/rateLimit.js';
import { PROVIDERS, PROVIDER_NAMES } from './providers/index.js';
import { enrichCandidate } from './engine/waterfall.js';
import { createBatchJob, parseCsv, processBatchJob } from './jobs/batchProcessor.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dashboardDir = path.resolve(__dirname, '../dashboard');
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });
const app = express();

app.use(helmet({
  contentSecurityPolicy: false
}));
app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(express.static(dashboardDir));

app.get('/health', (req, res) => {
  res.json({
    ok: true,
    service: 'enrichall',
    supabaseConfigured: hasSupabaseConfig
  });
});

app.post('/api/auth/signup', async (req, res, next) => {
  try {
    requireSupabase();
    const { email, password } = req.body;
    const { data, error } = await supabaseAnon.auth.signUp({ email, password });
    if (error) throw error;
    res.json({ user: data.user, session: data.session });
  } catch (err) {
    next(err);
  }
});

app.post('/api/auth/login', async (req, res, next) => {
  try {
    requireSupabase();
    const { email, password } = req.body;
    const { data, error } = await supabaseAnon.auth.signInWithPassword({ email, password });
    if (error) throw error;
    res.json({ user: data.user, session: data.session });
  } catch (err) {
    next(err);
  }
});

app.get('/api/providers', requireAuth, async (req, res, next) => {
  try {
    const { data, error } = await supabaseAdmin
      .from('provider_keys')
      .select('provider, is_active, priority, created_at')
      .eq('user_id', req.user.id)
      .order('priority', { ascending: true });
    if (error) throw error;
    res.json({ providers: data || [], available: PROVIDER_NAMES });
  } catch (err) {
    next(err);
  }
});

app.post('/api/providers', requireAuth, async (req, res, next) => {
  try {
    const { provider, apiKey, apiSecret = null, isActive = true, priority = 0 } = req.body;
    if (!PROVIDERS[provider]) return res.status(400).json({ error: 'Unsupported provider.' });
    if (!apiKey) return res.status(400).json({ error: 'apiKey is required.' });

    const { data, error } = await supabaseAdmin
      .from('provider_keys')
      .upsert({
        user_id: req.user.id,
        provider,
        api_key: apiKey,
        api_secret: apiSecret,
        is_active: isActive,
        priority
      }, { onConflict: 'user_id,provider' })
      .select('provider, is_active, priority, created_at')
      .single();

    if (error) throw error;
    res.json({ provider: data });
  } catch (err) {
    next(err);
  }
});

app.post('/api/providers/test', requireAuth, async (req, res, next) => {
  try {
    const { provider, apiKey } = req.body;
    const adapter = PROVIDERS[provider];
    if (!adapter) return res.status(400).json({ error: 'Unsupported provider.' });
    if (!apiKey) return res.status(400).json({ error: 'apiKey is required.' });
    await adapter.testKey(apiKey);
    res.json({ ok: true });
  } catch (err) {
    res.status(400).json({ ok: false, error: err.message });
  }
});

app.delete('/api/providers/:provider', requireAuth, async (req, res, next) => {
  try {
    const { error } = await supabaseAdmin
      .from('provider_keys')
      .delete()
      .eq('user_id', req.user.id)
      .eq('provider', req.params.provider);
    if (error) throw error;
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

app.post('/api/enrich', requireAuth, enforceDailyLookupLimit, async (req, res, next) => {
  try {
    const result = await enrichCandidate(req.body, { userId: req.user.id, lookupType: 'single' });
    res.json(result);
  } catch (err) {
    next(err);
  }
});

app.post('/api/enrich/batch', requireAuth, upload.single('file'), async (req, res, next) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'CSV file is required.' });
    const rows = parseCsv(req.file.buffer);
    if (!rows.length) return res.status(400).json({ error: 'CSV has no rows.' });

    const job = await createBatchJob({
      userId: req.user.id,
      filename: req.file.originalname,
      rows
    });

    processBatchJob({ job, rows, userId: req.user.id });
    res.status(202).json({ job });
  } catch (err) {
    next(err);
  }
});

app.get('/api/jobs', requireAuth, async (req, res, next) => {
  try {
    const { data, error } = await supabaseAdmin
      .from('batch_jobs')
      .select('*')
      .eq('user_id', req.user.id)
      .order('created_at', { ascending: false });
    if (error) throw error;
    res.json({ jobs: data || [] });
  } catch (err) {
    next(err);
  }
});

app.get('/api/jobs/:id', requireAuth, async (req, res, next) => {
  try {
    const { data, error } = await supabaseAdmin
      .from('batch_jobs')
      .select('*')
      .eq('user_id', req.user.id)
      .eq('id', req.params.id)
      .single();
    if (error) throw error;
    res.json({ job: data });
  } catch (err) {
    next(err);
  }
});

app.get('/api/jobs/:id/download', requireAuth, async (req, res, next) => {
  try {
    const { data, error } = await supabaseAdmin
      .from('batch_jobs')
      .select('*')
      .eq('user_id', req.user.id)
      .eq('id', req.params.id)
      .single();
    if (error) throw error;
    if (!data?.result_csv_url) return res.status(404).json({ error: 'Result CSV is not ready.' });
    res.redirect(data.result_csv_url);
  } catch (err) {
    next(err);
  }
});

app.get('/api/stats', requireAuth, async (req, res, next) => {
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const [todayUsage, allUsage, jobs] = await Promise.all([
      supabaseAdmin.from('usage_log').select('id', { count: 'exact', head: true }).eq('user_id', req.user.id).gte('created_at', today.toISOString()),
      supabaseAdmin.from('usage_log').select('id, cache_hit', { count: 'exact' }).eq('user_id', req.user.id),
      supabaseAdmin.from('batch_jobs').select('id, found_emails').eq('user_id', req.user.id)
    ]);

    if (todayUsage.error) throw todayUsage.error;
    if (allUsage.error) throw allUsage.error;
    if (jobs.error) throw jobs.error;

    const totalUsage = allUsage.count || 0;
    const cacheHits = (allUsage.data || []).filter(row => row.cache_hit).length;
    const totalEnriched = (jobs.data || []).reduce((sum, job) => sum + (job.found_emails || 0), 0);

    res.json({
      lookupsToday: todayUsage.count || 0,
      totalLookups: totalUsage,
      totalEnriched,
      cacheHitRate: totalUsage ? Math.round((cacheHits / totalUsage) * 100) : 0
    });
  } catch (err) {
    next(err);
  }
});

app.get('*', (req, res) => {
  res.sendFile(path.join(dashboardDir, 'index.html'));
});

app.use((err, req, res, next) => {
  const status = err.status || err.statusCode || 500;
  res.status(status).json({
    error: err.message || 'Internal server error'
  });
});

const port = Number(process.env.PORT || 3001);
app.listen(port, () => {
  console.log(`Enrichall API running on http://localhost:${port}`);
});
