import React from 'react';
import type {
  ConflictStatus,
  ReviewStatus,
  UncertaintyLabel,
  VerificationStatus,
} from '../api/generated/schema';

/**
 * Exact fixed wording from Section 10.6.
 * Never uses the words "confirmed", "true", or "fact" for any claim.
 */
export const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  verified: 'Quote found and supports',
  uncertain: 'Needs checking',
  rejected: 'Evidence not found or unsupported',
};

export const VERIFIED_TOOLTIP =
  'the quote was found and supports this claim; it does not prove the claim is true in the real world.';

export const CONFLICT_LABELS: Record<ConflictStatus, string> = {
  none: 'No conflict',
  conflict: 'Sources disagree',
  superseded: 'Replaced by a later update',
};

export const REVIEW_LABELS: Record<ReviewStatus, string> = {
  pending: 'Not reviewed',
  accepted: 'Accepted',
  edited: 'Edited by reviewer',
  rejected: 'Rejected',
  unresolved: 'Left unresolved',
};

export const UNCERTAINTY_LABELS: Record<UncertaintyLabel, string> = {
  none: '',
  uncertain: 'Uncertain',
  unresolved: 'Unresolved',
  conflicted: 'Disputed',
};

export interface StatusBadgeProps {
  field: 'verification_status' | 'conflict_status' | 'review_status' | 'uncertainty_label';
  value: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ field, value }) => {
  if (field === 'uncertainty_label' && value === 'none') {
    return null;
  }

  let label = value;
  let tooltip: string | undefined;

  if (field === 'verification_status') {
    label = VERIFICATION_LABELS[value as VerificationStatus] ?? value;
    if (value === 'verified') {
      tooltip = VERIFIED_TOOLTIP;
    }
  } else if (field === 'conflict_status') {
    label = CONFLICT_LABELS[value as ConflictStatus] ?? value;
  } else if (field === 'review_status') {
    label = REVIEW_LABELS[value as ReviewStatus] ?? value;
  } else if (field === 'uncertainty_label') {
    label = UNCERTAINTY_LABELS[value as UncertaintyLabel] ?? value;
  }

  return (
    <span className={`status-badge status-${field}-${value}`} title={tooltip}>
      {label}
    </span>
  );
};
