import { useState } from 'react';
import { amlApi, SignalCreatePayload } from '../../api/aml';

export function SignalForm({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState<SignalCreatePayload>({
    customer_id: '', amount: 0, channel: 'bank_transfer',
    jurisdiction: 'GB', is_pep: false, is_sanctioned: false,
    unusual_pattern: false, new_customer: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ risk_score: number } | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const signal = await amlApi.submitSignal(form);
      setResult({ risk_score: signal.risk_score });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-base font-semibold text-gray-900">Submit AML signal</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>

        {result ? (
          <div className="text-center py-6">
            <p className="text-sm font-medium text-gray-900">Signal submitted</p>
            <p className="text-xs text-gray-500 mt-1">
              Risk score: <span className={`font-bold ${result.risk_score >= 70 ? 'text-red-600' : 'text-gray-700'}`}>
                {result.risk_score}
              </span>
              {result.risk_score >= 70 && ' — case created automatically'}
            </p>
            <button onClick={onClose}
              className="mt-4 px-4 py-2 text-sm bg-gray-100 rounded-lg hover:bg-gray-200">
              Close
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Customer ID</label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                value={form.customer_id}
                onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Amount (£)</label>
                <input type="number"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  value={form.amount}
                  onChange={e => setForm(f => ({ ...f, amount: parseFloat(e.target.value) }))}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Channel</label>
                <select
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  value={form.channel}
                  onChange={e => setForm(f => ({ ...f, channel: e.target.value }))}
                >
                  <option value="bank_transfer">Bank transfer</option>
                  <option value="cash">Cash</option>
                  <option value="crypto">Crypto</option>
                  <option value="card">Card</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                { key: 'is_pep', label: 'PEP hit' },
                { key: 'is_sanctioned', label: 'Sanctions hit' },
                { key: 'unusual_pattern', label: 'Unusual pattern' },
                { key: 'new_customer', label: 'New customer' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="checkbox"
                    checked={form[key as keyof SignalCreatePayload] as boolean}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.checked }))}
                    className="rounded border-gray-300"
                  />
                  {label}
                </label>
              ))}
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <div className="flex justify-end gap-3 pt-2">
              <button onClick={onClose}
                className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200">
                Cancel
              </button>
              <button onClick={handleSubmit} disabled={submitting || !form.customer_id}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {submitting ? 'Submitting...' : 'Submit signal'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
