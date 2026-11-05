/** Tipos das respostas da API (backend/app/schemas). */

export type CropKey = 'soja' | 'milho';

export interface Municipality {
  code: number;
  name: string;
  state: string;
  state_code: number;
  latitude: number;
  longitude: number;
  principal: boolean;
  status: 'coletando' | 'pronto' | 'erro';
  status_message: string | null;
  created_at: string;
  rain_first_day: string | null;
  rain_last_day: string | null;
  rain_days: number;
  production_last_year: number | null;
}

export interface IbgeMunicipality {
  code: number;
  name: string;
}

export type CollectionSource = 'chuva' | 'producao' | 'estimativa';

export interface CollectionRun {
  id: string;
  source: CollectionSource;
  trigger: 'agendada' | 'botao' | 'cadastro';
  status: 'executando' | 'concluida' | 'sem_novidade' | 'erro';
  records: number;
  message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface SourceStatus {
  source: CollectionSource;
  name: string;
  provider: string;
  schedule: string;
  last_data: string | null;
  running: boolean;
  last_run: CollectionRun | null;
}

export interface CollectionOverview {
  sources: SourceStatus[];
  runs: CollectionRun[];
}

/** Especificação de gráfico montada pelo backend (services/charts.py). */
export interface ChartSpec {
  tipo: 'linha' | 'barras' | 'combinado' | 'dispersao' | 'mapa_calor';
  titulo: string;
  descricao?: string;
  [opcao: string]: unknown;
}

export interface SeasonRow {
  year: number;
  rain_mm: number | null;
  rain_state_mm: number | null;
  rain_anomaly_pct: number | null;
  dry_spell_days: number | null;
  planting_rain_mm: number | null;
  production_t: number | null;
  yield_kg_ha: number | null;
  yield_state_kg_ha: number | null;
  yield_brazil_kg_ha: number | null;
  trend_kg_ha: number | null;
  yield_anomaly_pct: number | null;
}

export interface IndicatorItem {
  rotulo: string;
  valor: string;
  descricao: string | null;
  variacao: number | null;
  variacao_boa: 'alta' | 'baixa' | null;
  tendencia: number[] | null;
}

export interface Analysis {
  municipality: Municipality;
  crop: CropKey;
  crop_name: string;
  window: string;
  seasons: SeasonRow[];
  correlation: { r: number; p: number; n: number } | null;
  indicators: IndicatorItem[];
  charts: ChartSpec[];
  notes: string[];
}

export interface Estimate {
  product: string;
  product_name: string;
  level: 'uf' | 'brasil';
  territory_code: number;
  territory_name: string;
  period: number;
  period_label: string;
  production_t: number | null;
  yield_kg_ha: number | null;
  planted_area_ha: number | null;
  harvested_area_ha: number | null;
  expected_yield_kg_ha: number | null;
}

export interface Discovery {
  id: string;
  municipality_code: number;
  municipality_name: string;
  crop: CropKey;
  kind: 'correlacao' | 'pior_safra' | 'comparacao_uf' | 'tendencia';
  title: string;
  fact: string;
  stats: Record<string, unknown>;
  chart: ChartSpec | null;
  interpretation: string | null;
  hypothesis: string | null;
}

export interface DiscoveryReport {
  id: string;
  status: 'gerando' | 'pronto' | 'erro';
  model: string;
  tests: number;
  summary: string | null;
  next_questions: string[];
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
  discoveries: Discovery[];
}

export interface Alert {
  id: string;
  municipality_code: number;
  municipality_name: string;
  crop: CropKey;
  kind: 'chuva_abaixo' | 'veranico';
  season_year: number;
  severity: 'warn' | 'err';
  title: string;
  message: string;
  facts: Record<string, unknown>;
  chart: ChartSpec | null;
  explanation: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ToolCallRecord {
  name: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  summary: string;
  source: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  state: 'concluida' | 'erro';
  error_message: string | null;
  tool_calls: ToolCallRecord[];
  charts: ChartSpec[];
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: StoredMessage[];
}

export interface ChatRequest {
  question: string;
  conversation_id?: string;
  retry?: boolean;
}

export type ChatEvent =
  | { type: 'conversation'; id: string; title: string }
  | { type: 'thinking' }
  | { type: 'tool_call'; name: string; arguments: Record<string, unknown> }
  | { type: 'tool_result'; result: ToolCallRecord }
  | { type: 'chart'; chart: ChartSpec }
  | { type: 'token'; text: string }
  | { type: 'done' }
  | { type: 'error'; code: string; message: string };

/** local = Ollama deste computador; externo = GPU externa pelo túnel SSH. */
export type OllamaLocation = 'local' | 'externo';

export interface PullStatus {
  model: string;
  status: 'baixando' | 'concluido' | 'erro';
  message: string | null;
  percent: number | null;
}

export interface OllamaServer {
  location: OllamaLocation;
  label: string;
  configured: boolean;
  online: boolean;
  models: { name: string; size_gb: number | null; parameter_size: string | null }[];
  /** Modelo escolhido para este Ollama. */
  chat_model: string;
  error: string | null;
  pull: PullStatus | null;
}

/** O Ollama e o modelo em uso, escolhidos na página Modelo de IA. */
export interface OllamaStatus {
  online: boolean;
  chat_model: { name: string; installed: boolean; tools: boolean | null };
  location: OllamaLocation;
  error: string | null;
  servers: OllamaServer[];
}

/** Servidor da GPU externa e o túnel SSH que o backend abre até ele. */
export interface GpuStatus {
  configured: boolean;
  host: string | null;
  port: number;
  user: string;
  state: 'nao_configurado' | 'desconectado' | 'conectando' | 'conectado' | 'erro';
  message: string | null;
  /** Chave pública do backend, para cadastrar no servidor. */
  public_key: string;
  host_key_fingerprint: string | null;
  host_key_mismatch: boolean;
  tunnel_port: number;
}

export interface SystemStatus {
  backend: { online: boolean; error: string | null };
  ollama: OllamaStatus;
  gpu: GpuStatus;
  database: { online: boolean; error: string | null };
  scheduler: { enabled: boolean; timezone: string; rain_hour: number; monthly_day: number };
}

export interface SeasonForecast {
  season_year: number;
  status: 'chuva_completa' | 'em_andamento';
  rain_until: string | null;
  rain_mm: number | null;
  predicted_kg_ha: number;
  low_kg_ha: number;
  high_kg_ha: number;
  trend_kg_ha: number;
  vs_trend_pct: number;
  scenarios: { name: 'seco' | 'normal' | 'chuvoso'; seasons: number; rain_mm: number; predicted_kg_ha: number }[];
  ibge_state_kg_ha: number | null;
  ibge_period_label: string | null;
}

export interface TrainedForecast {
  municipality_code: number;
  municipality_name: string;
  crop: CropKey;
  crop_name: string;
  seasons_used: number;
  first_year: number;
  last_year: number;
  features: { key: string; label: string; unit: string; coefficient: number }[];
  year_coefficient: number;
  intercept: number;
  equation: string;
  uses_rain: boolean;
  candidates: number;
  error_kg_ha: number;
  error_pct: number;
  baseline_error_kg_ha: number;
  baseline_error_pct: number;
  gain_pct: number;
  backtest: { year: number; actual: number; predicted: number; trend_only: number }[];
  forecasts: SeasonForecast[];
  charts: ChartSpec[];
}

export interface ForecastView {
  latest: {
    id: string;
    trigger: 'coleta' | 'botao';
    model: string;
    trained_at: string;
    explanation: string | null;
    result: TrainedForecast;
  } | null;
  history: {
    id: string;
    trigger: 'coleta' | 'botao';
    trained_at: string;
    seasons_used: number;
    features: string[];
    error_pct: number;
    baseline_error_pct: number;
  }[];
  training: boolean;
}
