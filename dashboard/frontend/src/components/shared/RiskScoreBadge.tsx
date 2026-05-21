export function RiskScoreBadge({ score }: { score: number }) {
  const colour =
    score >= 70 ? 'text-red-700 bg-red-50 ring-red-600/20' :
    score >= 40 ? 'text-yellow-700 bg-yellow-50 ring-yellow-600/20' :
                  'text-green-700 bg-green-50 ring-green-600/20';

  return (
    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${colour}`}>
      {score}
    </span>
  );
}
