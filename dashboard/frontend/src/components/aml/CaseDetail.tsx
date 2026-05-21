import { useEffect, useState } from 'react';
import { amlApi, ComplianceCase, SARReport } from '../../api/aml';
import { StatusBadge } from '../shared/StatusBadge';
import { RiskScoreBadge } from '../shared/RiskScoreBadge';
import { TimelineEvent } from '../shared/TimelineEvent';
import { SARDraftPanel } from './SARDraftPanel';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { ErrorBanner } from '../shared/ErrorBanner';

export function CaseDetail({ caseId }: { caseId: string }) {
  const [caseData, setCaseData] = useState<ComplianceCase | null>(null);
  const [sar, setSAR] = useState<SARReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatingSAR, setGeneratingSAR] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setLoading(true);
    amlApi.getCase(caseId)
      .then(setCaseData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [caseId]);

  async function handleGenerateSAR() {
    setGeneratingSAR(true);
    try {
      const draft = await amlApi.generateSARDraft(caseId);
      setSAR(draft);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to generate SAR');
    } finally {
      setGeneratingSAR(false);
    }
  }

  async function handleSubmitSAR() {
    setSubmitting(true);
    try {
      const submitted = await amlApi.submitSAR(caseId);
      setSAR(submitted);
      // Refresh case to get updated status
      const updated = await amlApi.getCase(caseId);
      setCaseData(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to submit SAR');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorBanner message={error} />;
  if (!caseData) return null;

  const canGenerateSAR = caseData.status === 'open' || caseData.status === 'in_review';
  const canSubmit = sar?.status === 'draft' && caseData.status !== 'submitted';

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-mono text-gray-400">{caseData.id}</p>
            <div className="mt-1 flex items-center gap-3">
              <StatusBadge status={caseData.status} />
              <RiskScoreBadge score={caseData.risk_score} />
            </div>
          </div>
          <div className="text-right text-xs text-gray-400">
            <p>Created {new Date(caseData.created_at).toLocaleString()}</p>
            <p>Updated {new Date(caseData.updated_at).toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="p-6 border-b border-gray-200">
        <h3 className="text-sm font-medium text-gray-900 mb-4">Event timeline</h3>
        {caseData.events.length === 0 ? (
          <p className="text-sm text-gray-400">No events recorded</p>
        ) : (
          <div className="space-y-3">
            {caseData.events.map(event => (
              <TimelineEvent key={event.id} event={event} />
            ))}
          </div>
        )}
      </div>

      {/* SAR section */}
      <div className="p-6">
        <h3 className="text-sm font-medium text-gray-900 mb-4">
          Suspicious Activity Report
        </h3>

        {!sar && canGenerateSAR && (
          <button
            onClick={handleGenerateSAR}
            disabled={generatingSAR}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generatingSAR ? 'Generating...' : 'Generate SAR draft'}
          </button>
        )}

        {sar && (
          <SARDraftPanel
            sar={sar}
            canSubmit={canSubmit}
            submitting={submitting}
            onSubmit={handleSubmitSAR}
          />
        )}

        {caseData.status === 'submitted' && !sar && (
          <p className="text-sm text-green-700 font-medium">
            SAR submitted successfully
          </p>
        )}
      </div>
    </div>
  );
}
