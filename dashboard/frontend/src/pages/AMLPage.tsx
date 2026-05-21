import { useState } from 'react';
import { AMLDashboard } from '../components/aml/AMLDashboard';
import { CaseQueue } from '../components/aml/CaseQueue';
import { CaseDetail } from '../components/aml/CaseDetail';
import { SignalForm } from '../components/aml/SignalForm';
import { AppShell } from '../components/mockups/covenant/_shared/AppShell';

export function AMLPage() {
  const [selectedCaseId, setSelectedCaseId] = useState<string | undefined>();
  const [showSignalForm, setShowSignalForm] = useState(false);

  return (
    <AppShell>
      <div className="flex flex-col h-full bg-gray-100">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">AML / SAR Workflow</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Anti-money laundering signal monitoring and suspicious activity reporting
            </p>
          </div>
          <button
            onClick={() => setShowSignalForm(true)}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            Submit signal
          </button>
        </div>

        {/* Dashboard metrics */}
        <div className="px-6 py-4 bg-white border-b border-gray-200">
          <AMLDashboard />
        </div>

        {/* Main content: queue + detail */}
        <div className="flex flex-1 overflow-hidden">
          {/* Case queue — fixed width left panel */}
          <div className="w-72 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col h-full">
            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Cases
              </p>
            </div>
            <CaseQueue
              onSelectCase={setSelectedCaseId}
              selectedCaseId={selectedCaseId}
            />
          </div>

          {/* Case detail — fills remaining space */}
          <div className="flex-1 overflow-hidden bg-white h-full">
            {selectedCaseId ? (
              <CaseDetail caseId={selectedCaseId} />
            ) : (
              <div className="flex items-center justify-center h-full text-sm text-gray-400">
                Select a case to view details
              </div>
            )}
          </div>
        </div>

        {/* Signal form modal */}
        {showSignalForm && (
          <SignalForm onClose={() => setShowSignalForm(false)} />
        )}
      </div>
    </AppShell>
  );
}
