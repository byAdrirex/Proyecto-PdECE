interface ProgressBarProps {
  value: number;
  label: string;
}

export function ProgressBar({ value, label }: ProgressBarProps) {
  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div className="progress" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={bounded} role="progressbar">
      <span style={{ width: `${bounded}%` }} />
    </div>
  );
}
