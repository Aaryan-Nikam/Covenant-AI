import { useEffect, useState } from 'react';
import { amlApi, ComplianceCase } from '../../api/aml';
import { StatusBadge } from '../shared/StatusBadge';
import { RiskScoreBadge } from '../shared/RiskScoreBadge';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { ErrorBanner } from '../shared/ErrorBanner';

interface Props {
  onSelectCase: (caseId: string) => void;
  selectedCaseId?: string;
}

const STATUS_FILTERS = ['all', 'open', 'in_review', 'submitted', 'closed'];

export function CaseQueue({ onSelectCase, selectedCaseId }: Props) {
  const [cases, setCases] = useState<ComplianceCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    amlApi.listCases()
      .then(setCases)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = statusFilter === 'all'
    ? cases
    : cases.filter(c => c.status === statusFilter);

  // Sort: open first, then by risk score descending
  const sorted = [...filtered].sort((a, b) => {
    const statusOrder = { open: 0, in_review: 1, submitted: 2, closed: 3 };
    const statusDiff =
      (statusOrder[a.status as keyof typeof statusOrder] ?? 4) -
      (statusOrder[b.status as keyof typeof statusOrder] ?? 4);
    return statusDiff !== 0 ? statusDiff : b.risk_score - a.risk_score;
  });

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorBanner message={error} />;

  return (
    <div className="flex flex-col h-full">
      {/* Filter tabs */}
      <div className="flex gap-1 p-3 border-b border-gray-200 bg-gray-50">
        {STATUS_FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setStatusFilter(f)}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              statusFilter === f
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {f === 'all' ? 'All' : f.replace(/_/g, ' ')}
            {f === 'all' && ` (${cases.length})`}
            {f !== 'all' && ` (${cases.filter(c => c.status === f).length})`}
          </button>
        ))}
      </div>

      {/* Case list */}
      <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
        {sorted.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">
            No cases match this filter
          </div>
        ) : (
          sorted.map(c => (
            <button
              key={c.id}
              onClick={() => onSelectCase(c.id)}
              className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                selectedCaseId === c.id ? 'bg-blue-50 border-l-2 border-blue-600' : ''
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-mono text-gray-400 truncate">
                  {c.id.slice(0, 8)}...
                </span>
                <RiskScoreBadge score={c.risk_score} />
              </div>
              <div className="mt-1 flex items-center gap-2">
                <StatusBadge status={c.status} />
                <span className="text-xs text-gray-400">
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
