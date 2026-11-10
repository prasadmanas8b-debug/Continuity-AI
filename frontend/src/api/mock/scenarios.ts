import { CONTRACT_FIXTURES } from '../../fixtures';
import type { ErrorCode } from '../generated/schema';

export interface MockDeveloperConfig {
  simulatedLatencyMs: number;
  forcedErrorCode: ErrorCode | null;
  contractVersionOverride: string | null;
  llmMode: 'fake' | 'live';
}

export const defaultMockConfig: MockDeveloperConfig = {
  simulatedLatencyMs: 250,
  forcedErrorCode: null,
  contractVersionOverride: null,
  llmMode: 'fake',
};

export { CONTRACT_FIXTURES };
