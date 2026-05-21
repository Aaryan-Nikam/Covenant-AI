import { SARReport } from '../../api/aml';
import { StatusBadge } from '../shared/StatusBadge';

interface Props {
  sar: SARReport;
  canSubmit: boolean;
  submitting: boolean;
  onSubmit: () => void;
}

export function SARDraftPanel({ sar, canSubmit, submitting, onSubmit }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <StatusBadge status={sar.status} />
        {sar.submitted_at && (
          <span className="text-xs text-gray-400">
            Submitted {new Date(sar.submitted_at).toLocaleString()}
          </span>
        )}
      </div>

      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
          {sar.draft_content}
        </pre>
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
