import { supabaseAdmin } from '../supabase.js';

const DEFAULT_LIMIT = Number(process.env.FREE_LOOKUPS_PER_DAY || 100);

export async function enforceDailyLookupLimit(req, res, next) {
  try {
    const limit = DEFAULT_LIMIT;
    const start = new Date();
    start.setHours(0, 0, 0, 0);

    const { count, error } = await supabaseAdmin
      .from('usage_log')
      .select('id', { count: 'exact', head: true })
      .eq('user_id', req.user.id)
      .gte('created_at', start.toISOString());

    if (error) throw error;
    if ((count || 0) >= limit) {
      return res.status(429).json({
        error: `Daily lookup limit reached (${limit}/day).`,
        limit,
        used: count || 0
      });
    }

    next();
  } catch (err) {
    next(err);
  }
}
