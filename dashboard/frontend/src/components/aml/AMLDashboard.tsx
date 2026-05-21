import { useEffect, useState } from 'react';
import { amlApi, AMLDashboardData } from '../../api/aml';

export function AMLDashboard() {
  const [data, setData] = useState<AMLDashboardData | null>(null);

  useEffect(() => {
    amlApi.getDashboard().then(setData).catch(console.error);
  }, []);

  if (!data) return null;

  const metrics = [
    { label: 'Open cases', value: data.open_cases,
      colour: 'text-blue-700', bg: 'bg-blue-50' },
    { label: 'High risk signals', value: data.high_risk_signals,
      colour: 'text-red-700', bg: 'bg-red-50' },
    { label: 'Overdue cases', value: data.overdue_cases,
      colour: 'text-orange-700', bg: 'bg-orange-50' },
    { label: 'Signals today', value: data.signals_today,
      colour: 'text-gray-700', bg: 'bg-gray-50' },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {metrics.map(m => (
        <div key={m.label}
          className={`rounded-xl p-4 ${m.bg} flex flex-col gap-1`}>
          <span className="text-xs font-medium text-gray-500">{m.label}</span>
          <span className={`text-3xl font-bold ${m.colour}`}>{m.value}</span>
        </div>
      ))}
    </div>
  );
}
