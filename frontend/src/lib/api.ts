import axios from 'axios'
import type {
  Analysis,
  AuditEntry,
  Chain,
  Contributor,
  Dataset,
  DatasetFinding,
  Inference,
  Model,
  Report,
  ReverifyResult,
  Sample,
  ScanReport,
} from './types'

export const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws/status'

const http = axios.create({ baseURL: API_BASE, headers: { 'X-Visentra-Actor': 'forensic-ui' } })

export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    if (!err.response) return 'Backend unreachable. Is the API running?'
    return `${err.response.status} ${err.response.statusText}`
  }
  return err instanceof Error ? err.message : String(err)
}

const get = <T,>(url: string, params?: object) => http.get<T>(url, { params }).then((r) => r.data)
const post = <T,>(url: string, body?: unknown, params?: object) => http.post<T>(url, body, { params }).then((r) => r.data)

function form(fields: Record<string, string | Blob | undefined>): FormData {
  const fd = new FormData()
  for (const [k, v] of Object.entries(fields)) if (v !== undefined && v !== '') fd.append(k, v)
  return fd
}

export const api = {
  health: () => get<{ status: string; version: string; demo: boolean }>('/health'),
  publicKey: () => get<{ algorithm: string; public_key: string; key_id: string }>('/keys/public'),

  contributors: () => get<Contributor[]>('/contributors'),
  createContributor: (name: string, role: string) => post<Contributor>('/contributors', { name, role }),
  chain: (cid: string) => get<Chain>(`/chain/${cid}`),

  datasets: (cid?: string) => get<Dataset[]>('/datasets', { contributor_id: cid }),
  dataset: (id: string) => get<Dataset>(`/datasets/${id}`),
  samples: (id: string) => get<Sample[]>(`/datasets/${id}/samples`),
  findings: (id: string) => get<DatasetFinding[]>(`/datasets/${id}/findings`),
  uploadDataset: (cid: string, version: string, file: File) =>
    post<Dataset>('/datasets', form({ contributor_id: cid, version, file })),
  verifyDataset: (id: string) => post<Dataset>(`/datasets/${id}/verify`),
  analyzeDataset: (id: string) => post<Analysis>(`/datasets/${id}/analyze`),
  tamperDataset: (id: string) => post<{ detail: string; sample_id: string }>(`/demo/datasets/${id}/tamper`),
  restoreDataset: (id: string) => post<{ detail: string }>(`/demo/datasets/${id}/restore`),
  thumbnail: (datasetId: string, sampleId: string, size = 128) =>
    `${API_BASE}/datasets/${datasetId}/samples/${sampleId}/thumbnail?size=${size}`,

  models: (cid?: string) => get<Model[]>('/models', { contributor_id: cid }),
  model: (id: string) => get<Model>(`/models/${id}`),
  uploadModel: (cid: string, version: string, file: File, datasetId?: string) =>
    post<Model>('/models', form({ contributor_id: cid, version, file, dataset_id: datasetId })),
  verifyModel: (id: string) => post<Model>(`/models/${id}/verify`),
  scanModel: (id: string) => post<ScanReport>(`/models/${id}/backdoor-scan`),
  latestScan: (id: string) => get<ScanReport>(`/models/${id}/backdoor-scans/latest`),
  tamperModel: (id: string) =>
    post<{ detail: string; flipped_offsets: number[]; invalidated_inferences: string[] }>(`/demo/models/${id}/tamper`),
  restoreModel: (id: string) => post<{ detail: string }>(`/demo/models/${id}/restore`),

  inferences: (modelId?: string) => get<Inference[]>('/inference', { model_id: modelId }),
  inference: (id: string) => get<Inference>(`/inference/${id}`),
  evidence: (id: string) => get<Record<string, unknown>>(`/inference/${id}/evidence`),
  runInference: (modelId: string, image: File, config: string) =>
    post<Inference>('/inference', form({ model_id: modelId, image, config })),
  reverify: (id: string) => post<ReverifyResult>(`/inference/${id}/reverify`),

  report: (cid: string) => get<Report>(`/report/${cid}`),
  certificate: (cid: string) => get<Record<string, unknown>>(`/report/${cid}/certificate`),
  verifyCertificate: (envelope: unknown) =>
    post<{ signature_valid: boolean; trusted_key: boolean; key_id: string | null }>('/report/certificate/verify', envelope),

  audit: (artifactId?: string, limit = 150) => get<AuditEntry[]>('/audit', { artifact_id: artifactId, limit }),
}
