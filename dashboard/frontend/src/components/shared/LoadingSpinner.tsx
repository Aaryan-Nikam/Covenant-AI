export function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center p-8">
      <div className="h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
