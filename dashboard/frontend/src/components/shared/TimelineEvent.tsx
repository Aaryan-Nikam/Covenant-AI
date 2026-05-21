export function TimelineEvent({ event }: { event: { event_type: string; description: string; created_at: string } }) {
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 w-1.5 h-1.5 mt-2 rounded-full bg-blue-400" />
      <div>
        <p className="text-xs font-medium text-gray-700">
          {event.event_type.replace(/_/g, ' ')}
        </p>
        <p className="text-xs text-gray-500">{event.description}</p>
        <p className="text-xs text-gray-400 mt-0.5">
          {new Date(event.created_at).toLocaleString()}
        </p>
      </div>
    </div>
  );
}
