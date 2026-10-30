export type Status = 'verified' | 'flagged' | 'suspicious' | 'tampered' | 'pending' | 'ok' | 'mismatch' | string

export interface Contributor {
  id: string
  name: string
  role: string | null
  created_at: string
}

export interface ChainNode {
  id: string
  type: 'contributor' | 'dataset' | 'model' | 'inference'
  label: string
  status: Status | null
  tier: number
  meta: Record<string, unknown>
}

export interface ChainEdge {
  id: string
  source: string
  target: string
  relation: string
}

export interface Chain {
  contributor_id: string
  nodes: ChainNode[]
  edges: ChainEdge[]
}

export interface Integrity {
  archive_match: boolean
  merkle_match: boolean
  recomputed_merkle_root: string | null
  changed_samples: string[]
  missing_samples: string[]
}

export interface Dataset {
  id: string
  contributor_id: string
  version: string
  name: string | null
  sha256: string
  actual_sha256: string | null
  merkle_root: string | null
  sample_count: number
  status: Status
  created_at: string
  verified_at: string | null
  integrity?: Integrity | null
  invalidated_inferences?: string[]
}

export interface Sample {
  id: string
  name: string
  sha256: string | null
  phash: string | null
  flags: string[]
}

export interface OodScore {
  sample_id: string
  image: string
  anomaly_score: number
  isolation_score: number
  mahalanobis_score: number
  flag: string | null
}

export interface DuplicatePair {
  sample_a_id: string
  sample_b_id: string
  image_a: string
  image_b: string
  phash_a: string
  phash_b: string
  hamming_distance: number
  severity: string
}

export interface Analysis {
  dataset_id: string
  status: Status
  duplicate_pairs: number
  ood_flagged: number
  total_samples_checked: number
  embedder: string
  thresholds: { hamming: number; ood: number }
  findings: Array<{ check: string } & Partial<DuplicatePair & OodScore>>
  scores: OodScore[]
}

export interface DatasetFinding {
  id: string
  check_type: string
  evidence_json: Record<string, unknown> | null
  severity: string
  created_at: string
}

export interface ByteDiff {
  bytes_changed: number
  first_offsets: number[]
  size: number
  tensors_touched: string[]
}

export interface ModelIntegrity {
  hash_match: boolean
  arch_match: boolean | null
  actual_arch_fingerprint: string | null
  byte_diff: ByteDiff | null
}

export interface GraphSummary {
  inputs?: Array<{ name: string; shape: Array<number | string> }>
  outputs?: Array<{ name: string; shape: Array<number | string> }>
  op_histogram?: Record<string, number>
  parameters?: number
  node_count?: number
  preprocess?: string
  sandbox_guards?: string[]
  opset?: number
  error?: string
}

export interface Model {
  id: string
  contributor_id: string
  dataset_id: string | null
  version: string
  name: string | null
  framework: string
  sha256: string
  actual_sha256: string | null
  arch_fingerprint: string | null
  graph_summary: GraphSummary | null
  status: Status
  created_at: string
  verified_at: string | null
  integrity?: ModelIntegrity | null
  invalidated_inferences?: string[]
}

export interface Flip {
  image: string
  position: string
  original_class: number
  original_confidence: number
  triggered_class: number
  triggered_confidence: number
  before: string
  after: string
}

export interface ScatterPoint {
  x: number
  y: number
  group: 'clean' | 'triggered'
}

export interface TriggerResult {
  trigger_type: string
  family: string
  target_class: number | null
  consistency_rate: number
  dominance: number
  anomaly_index: number
  strip_entropy_drop: number
  stage1_score: number
  escalated: boolean
  cluster_score: number
  confidence: number
  evidence: {
    total_pairs_tested: number
    flip_count: number
    target_class_votes: Record<string, number>
    flip_rate_by_position: Record<string, number>
    flips: Flip[]
    activation_scatter: ScatterPoint[]
    whitebox_source: string
  }
}

export interface ScanReport {
  scan_id: string
  model_id: string
  verdict: 'suspicious' | 'clean'
  top_confidence: number
  thresholds: { tau_gate: number; tau_bd: number; strip_gate: number }
  samples_used: number
  queries: number
  timing_ms: { stage1: number; stage2: number }
  escalated: string[]
  triggers: TriggerResult[]
  probe_source: string
  scanned_at: string
}

export interface Inference {
  id: string
  model_id: string
  model_sha256: string | null
  arch_fingerprint: string | null
  dataset_merkle_root: string | null
  input_sha256: string | null
  config_sha256: string | null
  output: {
    top_class: number
    top_confidence: number
    top_5: Array<{ class: number; prob: number }>
    logits?: number[]
  } | null
  confidence: number | null
  timestamp: string
  status: Status
  signature: string | null
  public_key: string | null
  key_id: string | null
}

export interface ReverifyResult {
  inference_id: string
  status: Status
  checks: {
    signature_valid: boolean
    model_hash_match: boolean
    input_hash_match: boolean
    dataset_root_match: boolean | null
    record_matches_evidence: boolean
  }
  diffs: string[]
}

export interface Pillar {
  key: 'dataset_integrity' | 'model_integrity' | 'backdoor_screening' | 'inference_binding'
  label: string
  score: number
  weight: number
  assessed: boolean
  explanation: string
  evidence: Record<string, unknown>
}

export interface Report {
  contributor_id: string
  contributor_name: string
  generated_at: string
  score: Record<Pillar['key'] | 'overall', number>
  grade: string
  summary: string
  pillars: Pillar[]
  findings_count: Record<string, number>
  limitations: string[]
}

export interface AuditEntry {
  id: string
  actor: string | null
  action: string | null
  artifact_type: string | null
  artifact_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  timestamp: string
}

export interface LiveMessage {
  type: string
  node_type?: string
  id?: string
  status?: Status
  cascade_from?: string
  hop?: number
  hops?: number
  origin_id?: string
  origin_type?: string
}
