import React from 'react';

export interface SystemBadgesProps {
  authMode: 'demo';
  apiMode: 'mock' | 'real';
  llmMode: 'fake' | 'live';
}

export const SystemBadges: React.FC<SystemBadgesProps> = ({ authMode, apiMode, llmMode }) => {
  return (
    <div className="system-badges" aria-label="System trust and mode indicators">
      {authMode === 'demo' && (
        <span className="badge badge-demo" title="Demo authentication switcher is active (D-02)">
          DEMO AUTH
        </span>
      )}
      {apiMode === 'mock' && (
        <span className="badge badge-mock" title="Backed by contracts/examples/ mock adapter (D-17)">
          MOCK DATA
        </span>
      )}
      {llmMode === 'fake' && (
        <span className="badge badge-replay" title="AI extraction uses deterministic FakeLLM replay (Section 9.10)">
          REPLAY
        </span>
      )}
    </div>
  );
};
