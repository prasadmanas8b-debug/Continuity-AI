import React from 'react';
import type { EvidenceLocator, QuoteMatchStatus, SupportStatus } from '../api/generated/schema';

export interface EvidenceQuoteProps {
  sourceLabel: string;
  sourceDate: string | null;
  exactQuote: string;
  locator: EvidenceLocator;
  quoteMatchStatus?: QuoteMatchStatus;
  supportStatus: SupportStatus;
  supportNote?: string | null;
  onInspectSource?: () => void;
}

export const EvidenceQuote: React.FC<EvidenceQuoteProps> = ({
  sourceLabel,
  sourceDate,
  exactQuote,
  locator,
  quoteMatchStatus,
  supportStatus,
  supportNote,
  onInspectSource,
}) => {
  const locatorParts: string[] = [];
  if (locator.page !== undefined) locatorParts.push(`p. ${locator.page}`);
  if (locator.char_start !== undefined && locator.char_end !== undefined) {
    locatorParts.push(`chars ${locator.char_start}–${locator.char_end}`);
  }
  if (locator.path) locatorParts.push(locator.path);
  if (locator.commit_sha) locatorParts.push(`@${locator.commit_sha.slice(0, 7)}`);

  return (
    <blockquote className="evidence-quote">
      <p className="quote-text">“{exactQuote}”</p>
      <footer className="quote-meta">
        <span>Source: <strong>{sourceLabel}</strong></span>
        <span>Date: {sourceDate ?? 'Date unknown'}</span>
        {locatorParts.length > 0 && <span>Locator: {locatorParts.join(' · ')}</span>}
        {quoteMatchStatus && <span>Match: {quoteMatchStatus}</span>}
        <span>Support: {supportStatus}</span>
        {supportNote && <span className="support-note">Note: {supportNote}</span>}
        {onInspectSource && (
          <button type="button" onClick={onInspectSource} className="btn-link">
            Inspect source excerpt
          </button>
        )}
      </footer>
    </blockquote>
  );
};
