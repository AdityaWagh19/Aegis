// Typed API client for the Aegis backend (plans/phase-7-dashboard.md Task 7.2).
import axios from 'axios';
import type { AggregateMetrics, AuditEntry, BatchResult, BatchUploadResponse, HumanReviewItem } from '../types/aegis';

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const api = axios.create({ baseURL: BASE, timeout: 60000 });

export async function uploadBatch(file: File): Promise<BatchUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<BatchUploadResponse>('/api/v1/recovery/batch', form);
  return data;
}

export async function getBatch(batchId: string): Promise<BatchResult> {
  const { data } = await api.get<BatchResult>(`/api/v1/recovery/batch/${batchId}`);
  return data;
}

export async function getMetrics(): Promise<AggregateMetrics> {
  const { data } = await api.get<AggregateMetrics>('/api/v1/metrics');
  return data;
}

export async function getAuditLog(
  page = 1,
  pageSize = 50,
): Promise<{ total: number; page: number; page_size: number; entries: AuditEntry[] }> {
  const { data } = await api.get(`/api/v1/audit?page=${page}&page_size=${pageSize}`);
  return data;
}

export async function getHumanReview(): Promise<{ total: number; items: HumanReviewItem[] }> {
  const { data } = await api.get('/api/v1/human-review');
  return data;
}

export async function resolveHumanReview(
  reviewId: string,
): Promise<{ status: string; review_id: string; resolved_at: string }> {
  const { data } = await api.post(`/api/v1/human-review/${reviewId}/resolve`);
  return data;
}
