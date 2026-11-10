import React from 'react';
import {
  CONFLICT_LABELS,
  REVIEW_LABELS,
  UNCERTAINTY_LABELS,
  VERIFICATION_LABELS,
  VERIFIED_TOOLTIP,
} from './StatusBadge';

/**
 * Available on S5, S6, S8, and S9 (Section 10.6).
 * Explains the four independent status axes (T2).
 */
export const Legend: React.FC = () => {
  return (
    <section className="status-legend" aria-label="Status badge legend">
      <h4>Four Separate Trust Axes (Never Conflated)</h4>
      <div className="legend-grid">
        <div>
          <strong>1. Evidence Verification</strong>
          <ul>
            <li><code>verified</code>: {VERIFICATION_LABELS.verified} ({VERIFIED_TOOLTIP})</li>
            <li><code>uncertain</code>: {VERIFICATION_LABELS.uncertain}</li>
            <li><code>rejected</code>: {VERIFICATION_LABELS.rejected}</li>
          </ul>
        </div>
        <div>
          <strong>2. Conflict Detection</strong>
          <ul>
            <li><code>none</code>: {CONFLICT_LABELS.none}</li>
            <li><code>conflict</code>: {CONFLICT_LABELS.conflict}</li>
            <li><code>superseded</code>: {CONFLICT_LABELS.superseded}</li>
          </ul>
        </div>
        <div>
          <strong>3. Human Review</strong>
          <ul>
            <li><code>pending</code>: {REVIEW_LABELS.pending}</li>
            <li><code>accepted</code>: {REVIEW_LABELS.accepted}</li>
            <li><code>edited</code>: {REVIEW_LABELS.edited}</li>
            <li><code>rejected</code>: {REVIEW_LABELS.rejected}</li>
            <li><code>unresolved</code>: {REVIEW_LABELS.unresolved}</li>
          </ul>
        </div>
        <div>
          <strong>4. Handover Uncertainty & Permissions</strong>
          <ul>
            <li><code>uncertain</code>: {UNCERTAINTY_LABELS.uncertain}</li>
            <li><code>unresolved</code>: {UNCERTAINTY_LABELS.unresolved}</li>
            <li><code>conflicted</code>: {UNCERTAINTY_LABELS.conflicted}</li>
          </ul>
        </div>
      </div>
    </section>
  );
};
