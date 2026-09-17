import { useState, useEffect } from 'react';
import { amlApi, SARReport } from '../../api/aml';
import { StatusBadge } from '../shared/StatusBadge';

interface Props {
  sar: SARReport;
  canSubmit: boolean;
  submitting: boolean;
  onSubmit: () => void;
  onUpdate: (sar: SARReport) => void;
}

export function SARDraftPanel({ sar, canSubmit, submitting, onSubmit, onUpdate }: Props) {
  const [summary, setSummary] = useState(sar.suspicion_summary || '');
  const [narrative, setNarrative] = useState(sar.narrative || '');
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    setSummary(sar.suspicion_summary || '');
    setNarrative(sar.narrative || '');
  }, [sar]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await amlApi.saveSARDraft(sar.case_id, summary, narrative);
      onUpdate(updated);
    } catch (e) {
      console.error(e);
      alert('Failed to save draft');
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerate = async () => {
    setGenerating(true);
    try {
      const regenerated = await amlApi.generateSARDraft(sar.case_id);
      onUpdate(regenerated);
    } catch (e) {
      console.error(e);
      alert('Failed to regenerate SAR');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 justify-between">
        <div className="flex items-center gap-2">
          <StatusBadge status={sar.status} />
          {sar.submitted_at && (
            <span className="text-xs text-gray-400">
              Submitted {new Date(sar.submitted_at).toLocaleString()}
            </span>
          )}
        </div>
        {!sar.submitted_at && (
          <div className="flex gap-2">
            <button
              onClick={handleRegenerate}
              disabled={generating || submitting || saving}
              className="px-3 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              {generating ? 'Regenerating...' : 'Regenerate'}
            </button>
            <button
              onClick={handleSave}
              disabled={saving || submitting || generating || (summary === sar.suspicion_summary && narrative === sar.narrative)}
              className="px-3 py-1 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Final Draft'}
            </button>
          </div>
        )}
      </div>

      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Suspicion Summary</label>
          <textarea
            value={summary}
            onChange={e => setSummary(e.target.value)}
            disabled={!!sar.submitted_at}
            rows={2}
            className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Narrative</label>
          <textarea
            value={narrative}
            onChange={e => setNarrative(e.target.value)}
            disabled={!!sar.submitted_at}
            rows={8}
            className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
          />
        </div>
      </div>

      {canSubmit && (
        <div className="flex items-start gap-3 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex-1">
            <p className="text-sm font-medium text-yellow-800">
              Review before submitting
            </p>
            <p className="text-xs text-yellow-700 mt-1">
              Submitting this SAR is a formal regulatory action.
              Verify all details are accurate before proceeding.
            </p>
          </div>
          <button
            onClick={onSubmit}
            disabled={submitting}
            className="flex-shrink-0 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Submitting...' : 'Submit SAR'}
          </button>
        </div>
      )}
    </div>
  );
}
