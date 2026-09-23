/**
 * The 04 §9 pagination envelope (DRF PageNumberPagination, page size 20).
 */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
