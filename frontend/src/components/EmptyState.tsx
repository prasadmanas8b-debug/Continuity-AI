import React from 'react';

export interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
}) => (
  <div className="empty-state">
    <h3>{title}</h3>
    <p>{description}</p>
    {actionLabel && onAction && (
      <button type="button" onClick={onAction}>
        {actionLabel}
      </button>
    )}
  </div>
);
