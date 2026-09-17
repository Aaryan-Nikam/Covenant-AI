import { requireSupabase, supabaseAdmin } from '../supabase.js';

export async function requireAuth(req, res, next) {
  try {
    requireSupabase();

    const header = req.headers.authorization || '';
    const token = header.startsWith('Bearer ') ? header.slice(7) : null;
    if (!token) {
      return res.status(401).json({ error: 'Missing Bearer token.' });
    }

    const { data, error } = await supabaseAdmin.auth.getUser(token);
    if (error || !data?.user) {
      return res.status(401).json({ error: 'Invalid or expired session.' });
    }

    req.user = data.user;
    req.accessToken = token;
    next();
  } catch (err) {
    next(err);
  }
}
