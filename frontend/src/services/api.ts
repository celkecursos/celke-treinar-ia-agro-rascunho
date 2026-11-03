import type {
  Alert,
  Analysis,
  ChatEvent,
  ChatRequest,
  CollectionOverview,
  CollectionRun,
  CollectionSource,
  Conversation,
  ConversationDetail,
  CropKey,
  DiscoveryReport,
  Estimate,
  ForecastView,
  IbgeMunicipality,
  Municipality,
  SystemStatus,
} from '../types/api';
import { readSse } from './sse';

/** Base da API. Vazio = mesma origem (o nginx ou o Vite repassam /api ao backend). */
const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '') + '/api';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = 'erro',
  ) {
    super(message);
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    if (body?.erro?.mensagem) return new ApiError(body.erro.mensagem, response.status, body.erro.codigo);
  } catch {
    // resposta sem JSON (proxy, timeout…)
  }
  if (response.status === 502 || response.status === 504) {
    return new ApiError('O backend não respondeu. Verifique se os containers estão rodando.', response.status);
  }
  return new ApiError(`Erro ${response.status} ao acessar a API.`, response.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API_URL + path, init);
  } catch {
    throw new ApiError('Não foi possível conectar ao backend.', 0, 'sem_conexao');
  }
  if (!response.ok) throw await errorFrom(response);
  if (response.status === 204 || response.status === 202 && response.headers.get('content-length') === '0') {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  status: () => request<SystemStatus>('/status'),
  municipalities: () => request<{ items: Municipality[] }>('/municipalities').then((r) => r.items),
  createMunicipality: (code: number) => request<Municipality>('/municipalities', json('POST', { code })),
  deleteMunicipality: (code: number) => request<void>(`/municipalities/${code}`, { method: 'DELETE' }),
  stateMunicipalities: (uf: string) =>
    request<{ items: IbgeMunicipality[] }>(`/ibge/states/${encodeURIComponent(uf)}/municipalities`).then((r) => r.items),
  collections: () => request<CollectionOverview>('/collections'),
  collect: (source: CollectionSource) => request<CollectionRun>(`/collections/${source}`, { method: 'POST' }),
  analysis: (code: number, crop: CropKey) => request<Analysis>(`/analyses/${code}/${crop}`),
  estimates: () => request<{ items: Estimate[] }>('/estimates').then((r) => r.items),
  forecast: (code: number, crop: CropKey) => request<ForecastView>(`/forecasts/${code}/${crop}`),
  trainForecast: (code: number, crop: CropKey) =>
    request<void>(`/forecasts/${code}/${crop}/train`, { method: 'POST' }),
  discoveries: () => request<DiscoveryReport>('/discoveries'),
  regenerateDiscoveries: () => request<void>('/discoveries', { method: 'POST' }),
  alerts: (includeInactive = false) =>
    request<{ items: Alert[] }>(`/alerts${includeInactive ? '?include_inactive=true' : ''}`).then((r) => r.items),
  conversations: () => request<{ items: Conversation[] }>('/conversations').then((r) => r.items),
  conversation: (id: string) => request<ConversationDetail>(`/conversations/${encodeURIComponent(id)}`),
  deleteConversation: (id: string) =>
    request<void>(`/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

/** Pergunta ao backend e devolve os eventos do streaming conforme chegam. */
export async function* streamChat(body: ChatRequest, signal: AbortSignal): AsyncGenerator<ChatEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (signal.aborted) return;
    throw e instanceof Error && e.name === 'AbortError'
      ? e
      : new ApiError('Não foi possível conectar ao backend.', 0, 'sem_conexao');
  }
  if (!response.ok || !response.body) throw await errorFrom(response);
  yield* readSse(response.body);
}
