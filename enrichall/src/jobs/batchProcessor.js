import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';
import { supabaseAdmin } from '../supabase.js';
import { mapCsvRow } from '../engine/normalizer.js';
import { enrichCandidate } from '../engine/waterfall.js';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export function parseCsv(buffer) {
  return parse(buffer.toString('utf8'), {
    columns: true,
    skip_empty_lines: true,
    trim: true
  });
}

export async function createBatchJob({ userId, filename, rows }) {
  const { data, error } = await supabaseAdmin
    .from('batch_jobs')
    .insert({
      user_id: userId,
      status: 'pending',
      total_rows: rows.length,
      processed_rows: 0,
      found_emails: 0,
      providers_used: [],
      input_filename: filename
    })
    .select('*')
    .single();

  if (error) throw error;
  return data;
}

async function updateJob(jobId, patch) {
  const { error } = await supabaseAdmin
    .from('batch_jobs')
    .update(patch)
    .eq('id', jobId);
  if (error) throw error;
}

async function uploadResultCsv(jobId, csvContent) {
  const path = `${jobId}/result.csv`;
  const { error } = await supabaseAdmin.storage
    .from('batch-results')
    .upload(path, Buffer.from(csvContent, 'utf8'), {
      contentType: 'text/csv',
      upsert: true
    });

  if (error) throw error;

  const { data } = supabaseAdmin.storage.from('batch-results').getPublicUrl(path);
  return data.publicUrl;
}

export async function processBatchJob({ job, rows, userId }) {
  const outputRows = [];
  const providersUsed = new Set();
  let foundEmails = 0;

  try {
    await updateJob(job.id, { status: 'processing' });

    for (let index = 0; index < rows.length; index += 1) {
      const original = rows[index];
      const candidate = mapCsvRow(original);
      const result = await enrichCandidate(candidate, { userId, lookupType: 'batch' });

      if (result.email) foundEmails += 1;
      if (result.source) providersUsed.add(result.source);

      outputRows.push({
        ...original,
        Email: result.email || '',
        'Email Source': result.source || '',
        'Email Confidence': result.confidence || '',
        'Email Verified': result.verified ? 'yes' : 'no',
        'Cache Hit': result.cacheHit ? 'yes' : 'no',
        'Providers Tried': (result.providersTried || []).map(p => `${p.provider}:${p.status}`).join('; ')
      });

      if ((index + 1) % 5 === 0 || index === rows.length - 1) {
        await updateJob(job.id, {
          processed_rows: index + 1,
          found_emails: foundEmails,
          providers_used: Array.from(providersUsed)
        });
      }

      await sleep(500);
    }

    const csv = stringify(outputRows, { header: true });
    const resultCsvUrl = await uploadResultCsv(job.id, csv);

    await updateJob(job.id, {
      status: 'complete',
      processed_rows: rows.length,
      found_emails: foundEmails,
      providers_used: Array.from(providersUsed),
      result_csv_url: resultCsvUrl,
      completed_at: new Date().toISOString()
    });
  } catch (err) {
    await updateJob(job.id, {
      status: 'failed',
      error_message: err.message,
      completed_at: new Date().toISOString()
    });
  }
}
