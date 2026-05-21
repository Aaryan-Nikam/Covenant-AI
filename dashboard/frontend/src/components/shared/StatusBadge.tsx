const STATUS_STYLES: Record<string, string> = {
  open:       'bg-blue-100 text-blue-800',
  in_review:  'bg-yellow-100 text-yellow-800',
  submitted:  'bg-green-100 text-green-800',
  closed:     'bg-gray-100 text-gray-600',
  compliant:  'bg-green-100 text-green-800',
  at_risk:    'bg-yellow-100 text-yellow-800',
  breached:   'bg-red-100 text-red-800',
  draft:      'bg-gray-100 text-gray-600',
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}
