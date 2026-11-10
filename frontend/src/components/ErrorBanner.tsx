import React from 'react';
import { ApiError } from '../api/client';

export interface ErrorBannerProps {
  error: ApiError | Error | null;
  onRetry?: () => void;
  onOpenExistingSource?: (sourceId: string) => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  error,
  onRetry,
  onOpenExistingSource,
}) => {
  if (!error) return null;
  const apiError = error instanceof ApiError ? error : null;
  const existingSourceId =
    apiError?.code === 'DUPLICATE_SOURCE' && apiError.details?.existing_source_id
      ? String(apiError.details.existing_source_id)
      : null;

  return (
    <div role="alert" className="error-banner">
      <div className="error-message">{apiError ? apiError.userMessage : error.message}</div>
      {apiError && (
        <div className="error-details">
          details: code={apiError.code} · request_id={apiError.requestId}
        </div>
      )}
      <div className="error-actions">
        {existingSourceId && onOpenExistingSource && (
          <button type="button" onClick={() => onOpenExistingSource(existingSourceId)}>
            Open existing source
          </button>
        )}
        {onRetry && (
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    </div>
  );
};
