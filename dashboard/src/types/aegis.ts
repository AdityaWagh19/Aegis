// TypeScript interfaces mirroring the Aegis API response shapes exactly
// (plans/phase-7-dashboard.md Task 7.1; endpoints defined in project-context/api.md).

export interface ComplianceResult {
  approved: boolean;
  final_action: string;
  violation_blocked: boolean;
  violation_rule: string | null;
}

export interface RecoveryDecision {
  mandate_id: string;
  tier_that_decided: number;
  proposed_action: string;
  compliance_result: ComplianceResult;
  final_action: string;
  outcome: string;
  rationale: string | null;
  confidence: number | null;
  hinglish_message: string | null;
  alternatives_considered: string[] | null;
  razorpay_response: Record<string, unknown> | null;
}

export interface BatchMetrics {
  total_records: number;
  tier1_count: number;
  tier2_count: number;
  tier1_pct: number;
  recovery_rate: number;
  rs_recovered: number;
  rs_at_risk: number;
  compliance_violations_caught: number;
  compliance_violations_executed: number;
}

export interface BatchResult {
  batch_id: string;
  status: string;
  metrics: BatchMetrics;
  decisions: RecoveryDecision[];
}

/** POST /api/v1/recovery/batch response envelope */
export interface BatchUploadResponse {
  batch_id: string;
  status: string;
  record_count: number;
  parse_errors: string[];
  metrics: BatchMetrics;
}

export interface HumanReviewItem {
  review_id: string;
  mandate_id: string;
  reason: string;
  compliance_rule: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AuditEntry {
  entry_id: number;
  mandate_id: string;
  timestamp: string;
  violation_blocked?: boolean;
  [key: string]: unknown;
}

export interface AggregateMetrics {
  total_records: number;
  message?: string;
  tier1_count: number;
  tier2_count: number;
  tier1_pct: number;
  executed_count: number;
  escalated_count: number;
  recovered_count: number;
  rs_recovered: number;
  rs_at_risk: number;
  auto_resolved_count: number;
  auto_resolution_rate: number;
  analyst_hours_saved: number;
  compliance_violations_caught: number;
  compliance_violations_executed: number;
  recovery_by_category: Record<string, number>;
}
