export * from '../api/generated/schema';

export interface ClaimFilters {
  verification_status?: string;
  conflict_status?: string;
  review_status?: string;
  fact_type?: string;
  item_id?: string;
}
