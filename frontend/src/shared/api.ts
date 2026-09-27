import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({ baseURL: BASE })

export const WS_URL = BASE.replace(/^http/, 'ws') + '/ws/status'

// --- contributors ---
export const createContributor = (name: string) =>
  api.post('/contributors', { name }).then(r => r.data)

export const listContributors = () =>
  api.get('/contributors').then(r => r.data)

// --- datasets ---
export const uploadDataset = (contributorId: string, version: string, file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('contributor_id', contributorId)
  fd.append('version', version)
  return api.post('/datasets', fd).then(r => r.data)
}

export const verifyDataset = (id: string) =>
  api.post(`/datasets/${id}/verify`).then(r => r.data)

export const tamperDataset = (id: string) =>
  api.post(`/demo/datasets/${id}/tamper`).then(r => r.data)

// --- models ---
export const uploadModel = (contributorId: string, version: string, file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('contributor_id', contributorId)
  fd.append('version', version)
  return api.post('/models', fd).then(r => r.data)
}

export const verifyModel = (id: string) =>
  api.post(`/models/${id}/verify`).then(r => r.data)

export const tamperModel = (id: string) =>
  api.post(`/demo/models/${id}/tamper`).then(r => r.data)

export const restoreModel = (id: string) =>
  api.post(`/demo/models/${id}/restore`).then(r => r.data)

// --- inference ---
export const runInference = (modelId: string, imageFile: File, config = '{}'): Promise<unknown> => {
  const fd = new FormData()
  fd.append('image', imageFile)
  fd.append('model_id', modelId)
  fd.append('config', config)
  return api.post('/inference', fd).then(r => r.data)
}

export const getInference = (id: string) =>
  api.get(`/inference/${id}`).then(r => r.data)

export const reverifyInference = (id: string) =>
  api.post(`/inference/${id}/reverify`).then(r => r.data)

// --- chain ---
export const getChain = (contributorId: string) =>
  api.get(`/chain/${contributorId}`).then(r => r.data)
