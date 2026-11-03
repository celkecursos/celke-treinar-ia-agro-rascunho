# Frontend React com o Kole

**Etapa:** 3 de 6
**Requer:** etapa 2

## Orientação antes de começar

> **O que vai acontecer agora:** vou criar as telas de Análises, Previsão, Chat, Descobertas, Alertas, Municípios e
> Status com o layout `@celke/kole-react`. **O que você precisa fazer:** nada. Ao final, a aplicação já abre no navegador.

## Prompt

Crie o frontend do **Celke Treinar IA Agro** em React, TypeScript e Vite, com o `@celke/kole-react` (com os gráficos,
instalado do GitHub na tag `v0.4.0`) e nginx com proxy da API.

Regras desta etapa:

- Crie os arquivos com **exatamente** o conteúdo indicado, sem melhorar nem reformatar. O conteúdo já foi
  testado junto; uma alteração aqui quebra outra etapa.
- Não pergunte nada ao usuário: as decisões estão neste prompt e em `docs/configuracao.md`.
- Mostre ao usuário as seções **Orientação** (antes de começar e ao terminar), com as suas palavras só onde
  houver marcador a trocar. Se o terminal não permitir mostrar agora, inclua no seu relatório final.
- Rode tudo o que está em **Verificação** e corrija o que falhar antes de terminar.
- Nunca mostre o valor de `POSTGRES_PASSWORD`.

`frontend/.dockerignore`:

``````text
node_modules
dist
.env
*.log
``````

`frontend/Dockerfile`:

``````dockerfile
FROM node:24-alpine AS build
# git: o @celke/kole-react vem direto do GitHub (tag fixa) até a versão com gráficos sair no npm
RUN apk add --no-cache git
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Testes e verificação de tipos (docker compose --profile test run --rm frontend-tests)
FROM build AS test
CMD ["sh", "-c", "npm run typecheck && npm test"]

FROM build AS bundle
RUN npm run build

FROM nginx:1.30-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=bundle /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
``````

`frontend/index.html`:

``````html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" type="image/svg+xml" href="/logo.svg" />
    <title>Celke Treinar IA Agro</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
``````

`frontend/nginx.conf`:

``````nginx
# Serve o React e repassa /api ao backend pela rede interna do Docker.
# O navegador só fala com este servidor (mesma origem, sem CORS).
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;

    client_max_body_size 1m;

    # add_header de um location substitui os do server: os de segurança se repetem em cada um.
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # Streaming do chat: entrega cada pedaço da resposta assim que chega.
        proxy_buffering off;
        proxy_cache off;
        # O modelo pode levar minutos para carregar na primeira pergunta e para chamar as ferramentas.
        proxy_read_timeout 900s;
        proxy_send_timeout 900s;
    }

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options DENY always;
        add_header Referrer-Policy same-origin always;
        try_files $uri =404;
    }

    location / {
        add_header Cache-Control "no-cache";
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options DENY always;
        add_header Referrer-Policy same-origin always;
        try_files $uri /index.html;
    }
}
``````

`frontend/package.json`:

``````json
{
  "name": "celke-treinar-ia-agro-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "preview": "vite preview"
  },
  "dependencies": {
    "@celke/kole-react": "git+https://github.com/celkecursos/kole-react.git#v0.4.0",
    "lucide-react": "^1.60.0",
    "react": "^19.3.1",
    "react-dom": "^19.3.1",
    "react-router": "^8.5.1"
  },
  "devDependencies": {
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "@vitejs/plugin-react": "^6.1.2",
    "typescript": "~6.0.3",
    "vite": "^8.3.5",
    "vitest": "^5.0.5"
  }
}
``````

`frontend/public/logo.svg`:

``````xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1f8a4c"/><path d="M32 50c-9 0-15-6-15-15 0-12 11-20 27-21 0 16-6 36-12 36z" fill="#e8f5e9"/><path d="M22 47c4-9 10-16 19-23" stroke="#1f8a4c" stroke-width="3" stroke-linecap="round" fill="none"/><path d="M47 34c-2 4-4 6-4 8a4 4 0 0 0 8 0c0-2-2-4-4-8z" fill="#7cc4ff"/></svg>
``````

`frontend/src/components/ChartView.tsx`:

``````tsx
import {
  GraficoBarras,
  GraficoCombinado,
  GraficoDispersao,
  GraficoLinha,
  MapaCalor,
  type GraficoBarrasProps,
  type GraficoCombinadoProps,
  type GraficoDispersaoProps,
  type GraficoLinhaProps,
  type MapaCalorProps,
} from '@celke/kole-react';
import type { ChartSpec } from '../types/api';
import { chartProps } from './chartProps';

/** Desenha com o Kole o gráfico que o backend montou (as contas já vêm feitas). */
export function ChartView({ spec, altura }: { spec: ChartSpec; altura?: number }) {
  const props = { ...chartProps(spec), altura };
  switch (spec.tipo) {
    case 'linha':
      return <GraficoLinha {...(props as unknown as GraficoLinhaProps)} />;
    case 'barras':
      return <GraficoBarras {...(props as unknown as GraficoBarrasProps)} />;
    case 'combinado':
      return <GraficoCombinado {...(props as unknown as GraficoCombinadoProps)} />;
    case 'dispersao':
      return <GraficoDispersao {...(props as unknown as GraficoDispersaoProps)} />;
    case 'mapa_calor':
      return <MapaCalor {...(props as unknown as MapaCalorProps)} />;
    default:
      return null;
  }
}
``````

`frontend/src/components/StatusLabel.tsx`:

``````tsx
import { Status } from '@celke/kole-react';
import type { CollectionRun, Municipality } from '../types/api';

type Severidade = 'ok' | 'info' | 'warn' | 'err' | 'neutral';

const MUNICIPALITY: Record<Municipality['status'], { rotulo: string; severidade: Severidade }> = {
  coletando: { rotulo: 'Coletando', severidade: 'info' },
  pronto: { rotulo: 'Pronto', severidade: 'ok' },
  erro: { rotulo: 'Erro', severidade: 'err' },
};

const RUN: Record<CollectionRun['status'], { rotulo: string; severidade: Severidade }> = {
  executando: { rotulo: 'Executando', severidade: 'info' },
  concluida: { rotulo: 'Concluída', severidade: 'ok' },
  sem_novidade: { rotulo: 'Sem novidade', severidade: 'neutral' },
  erro: { rotulo: 'Erro', severidade: 'err' },
};

export const TRIGGER_LABEL: Record<CollectionRun['trigger'], string> = {
  agendada: 'Agendada',
  botao: 'Botão',
  cadastro: 'Cadastro',
};

export function MunicipalityStatusLabel({ status }: { status: Municipality['status'] }) {
  return <Status {...MUNICIPALITY[status]} />;
}

export function RunStatusLabel({ status }: { status: CollectionRun['status'] }) {
  return <Status {...RUN[status]} />;
}

export function OnlineStatus({ online, rotulo }: { online: boolean; rotulo?: string }) {
  return <Status rotulo={rotulo ?? (online ? 'Conectado' : 'Desconectado')} severidade={online ? 'ok' : 'err'} />;
}
``````

`frontend/src/components/chartProps.test.ts`:

``````ts
import { describe, expect, it } from 'vitest';
import { camelKey, chartProps } from './chartProps';

describe('chartProps', () => {
  it('troca snake_case pelos nomes das props do Kole', () => {
    expect(camelKey('eixo_y_direito')).toBe('eixoYDireito');
    expect(camelKey('chave_destaque')).toBe('chaveDestaque');
    expect(camelKey('titulo')).toBe('titulo');
  });

  it('tira o tipo e os valores vazios', () => {
    const props = chartProps({
      tipo: 'dispersao',
      titulo: 'Chuva × rendimento',
      chave_x: 'x',
      eixo_x: { rotulo: 'Chuva', unidade: 'mm' },
      nota: null,
    });
    expect(props).toEqual({ titulo: 'Chuva × rendimento', chaveX: 'x', eixoX: { rotulo: 'Chuva', unidade: 'mm' } });
  });
});
``````

`frontend/src/components/chartProps.ts`:

``````ts
import type { ChartSpec } from '../types/api';

/** `eixo_y_direito` → `eixoYDireito`: as opções do backend usam os mesmos nomes das props do Kole, em snake_case. */
export function camelKey(key: string): string {
  return key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

/** Props do componente do Kole a partir da especificação do backend (sem o `tipo`). */
export function chartProps(spec: ChartSpec): Record<string, unknown> {
  const props: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(spec)) {
    if (key === 'tipo' || value === null || value === undefined) continue;
    props[camelKey(key)] = value;
  }
  return props;
}
``````

`frontend/src/hooks/usePolling.ts`:

``````ts
import { useCallback, useEffect, useRef, useState } from 'react';

interface PollingState<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => Promise<void>;
}

/**
 * Carrega `load` e repete a cada `intervalMs` enquanto `active` for verdadeiro
 * (ex.: enquanto houver documento processando). `intervalMs = 0` não repete.
 */
export function usePolling<T>(load: () => Promise<T>, intervalMs: number, active = true): PollingState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  loadRef.current = load;

  const reload = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(undefined);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!active || intervalMs <= 0) return;
    const timer = window.setInterval(() => void reload(), intervalMs);
    return () => window.clearInterval(timer);
  }, [active, intervalMs, reload]);

  return { data, error, loading, reload };
}
``````

`frontend/src/layouts/AppLayout.tsx`:

``````tsx
import { Estrutura } from '@celke/kole-react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router';

// Os usos da IA no projeto: prever com um modelo treinado (Previsão), responder (Chat), descobrir (Descobertas)
// e avisar (Alertas).
const NAV = [
  {
    itens: [{ rotulo: 'Análises', icone: 'chart-line', rota: '/' }],
  },
  {
    rotulo: 'Inteligência',
    itens: [
      { rotulo: 'Previsão (treino)', icone: 'brain', rota: '/previsao' },
      { rotulo: 'Chat', icone: 'message-square', rota: '/chat' },
      { rotulo: 'Descobertas', icone: 'lightbulb', rota: '/descobertas' },
      { rotulo: 'Alertas', icone: 'bell', rota: '/alertas' },
    ],
  },
  {
    rotulo: 'Dados',
    itens: [
      { rotulo: 'Municípios', icone: 'map-pin', rota: '/municipios' },
      { rotulo: 'Status e coletas', icone: 'activity', rota: '/status' },
    ],
  },
];

export function AppLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  return (
    <Estrutura
      marca={{ nome: 'Celke Agro', subtitulo: 'Treinar IA', logo: '/logo.svg', href: '/' }}
      nav={NAV}
      rotaAtual={pathname}
      aoNavegar={(rota) => navigate(rota)}
      renderLink={(p) => (
        <Link to={p.href} className={p.className} onClick={p.onClick} aria-current={p['aria-current']}>
          {p.children}
        </Link>
      )}
      busca={false}
      versao="1.0.0"
      rodape={<span>Dados: Open-Meteo (CC BY 4.0) e IBGE · a IA roda no seu computador com o Ollama</span>}
    >
      <Outlet />
    </Estrutura>
  );
}
``````

`frontend/src/main.tsx`:

``````tsx
import '@celke/kole-react/estilos.css';
import './styles.css';
import { ProvedorUi, registrarIcones } from '@celke/kole-react';
import {
  Activity,
  Bell,
  Bot,
  Brain,
  CalendarClock,
  ChartScatter,
  CloudRain,
  Cpu,
  Database,
  History,
  Lightbulb,
  Plus,
  Sparkles,
  Sprout,
  Trash2,
  Wrench,
} from 'lucide-react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { router } from './router';

// Ícones usados pelo nome que não vêm registrados no Kole
registrarIcones({
  activity: Activity,
  bell: Bell,
  bot: Bot,
  brain: Brain,
  'calendar-clock': CalendarClock,
  'chart-scatter': ChartScatter,
  'cloud-rain': CloudRain,
  cpu: Cpu,
  database: Database,
  history: History,
  lightbulb: Lightbulb,
  plus: Plus,
  sparkles: Sparkles,
  sprout: Sprout,
  'trash-2': Trash2,
  wrench: Wrench,
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ProvedorUi>
      <RouterProvider router={router} />
    </ProvedorUi>
  </StrictMode>,
);
``````

`frontend/src/pages/AlertsPage.tsx`:

``````tsx
import { Alerta, Botao, CabecalhoPagina, Card, Escolha, Tabela, Vazio, formatDataHoraBr } from '@celke/kole-react';
import { useState } from 'react';
import { ChartView } from '../components/ChartView';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import { formatIsoDate, formatNumber } from '../utils/format';

interface SimilarSeason {
  safra: number;
  desvio_chuva_pct: number;
  desvio_rendimento_pct: number;
}

const pct = (v: unknown) => (typeof v === 'number' ? `${v > 0 ? '+' : ''}${v.toLocaleString('pt-BR')}%` : '–');

export function AlertsPage() {
  const [show, setShow] = useState<'ativos' | 'todos'>('ativos');
  const alerts = usePolling(() => api.alerts(show === 'todos'), 30000);

  return (
    <div className="app-pagina">
      <CabecalhoPagina
        titulo="Alertas"
        icone="bell"
        acoes={<Botao rotulo="Atualizar" icone="refresh-cw" severidade="secundario" onClick={() => void alerts.reload()} />}
      >
        A cada coleta de chuva, a safra em andamento é comparada com o mesmo trecho das safras passadas. Chuva bem
        abaixo da média ou muitos dias seguidos sem chuva geram um alerta, com as safras parecidas do passado.
      </CabecalhoPagina>

      <Escolha<'ativos' | 'todos'>
        ariaLabel="Quais alertas mostrar"
        opcoes={[
          { valor: 'ativos', rotulo: 'Ativos' },
          { valor: 'todos', rotulo: 'Todos' },
        ]}
        valor={show}
        aoMudar={(v) => {
          setShow(v);
          setTimeout(() => void alerts.reload());
        }}
      />

      {alerts.error && <Alerta severidade="err" titulo="Não foi possível carregar" mensagem={alerts.error.message} />}
      {alerts.data?.length === 0 && (
        <Vazio
          titulo="Nenhum alerta"
          descricao="A chuva da safra em andamento está dentro do normal nos municípios cadastrados, ou ainda não há dados suficientes."
          icone="bell"
        />
      )}

      {alerts.data?.map((a) => {
        const similar = (a.facts.safras_parecidas as SimilarSeason[] | undefined) ?? [];
        return (
          <Card
            key={a.id}
            titulo={a.title}
            subtitulo={`${a.municipality_name} · safra ${a.season_year} · atualizado em ${formatDataHoraBr(new Date(a.updated_at))}${a.active ? '' : ' · encerrado'}`}
          >
            <div className="app-pagina">
              <Alerta
                severidade={a.active ? a.severity : 'neutral'}
                titulo={a.message}
                mensagem={a.explanation ? `IA: ${a.explanation}` : undefined}
              />
              <p className="app-texto">
                Chuva de {formatIsoDate(String(a.facts.inicio_janela))} a {formatIsoDate(String(a.facts.ate))}:{' '}
                {formatNumber(a.facts.chuva_mm as number, 'mm')}; média do mesmo período:{' '}
                {formatNumber(a.facts.media_mesmo_periodo_mm as number, 'mm')} ({pct(a.facts.desvio_pct)}).
              </p>
              {a.chart && <ChartView spec={a.chart} altura={240} />}
              {similar.length > 0 && (
                <Tabela<SimilarSeason>
                  rotulo="Safras passadas com chuva parecida"
                  registros={similar}
                  chave={(s) => s.safra}
                  colunas={[
                    { campo: 'safra', rotulo: 'Safra parecida', destaque: true },
                    { campo: 'desvio_chuva_pct', rotulo: 'Chuva no mesmo trecho', alinhamento: 'direita', formato: pct },
                    {
                      campo: 'desvio_rendimento_pct',
                      rotulo: 'Rendimento × tendência',
                      alinhamento: 'direita',
                      formato: pct,
                    },
                  ]}
                />
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
``````

`frontend/src/pages/AnalysesPage.tsx`:

``````tsx
import {
  Alerta,
  Botao,
  CabecalhoPagina,
  Card,
  CampoSelect,
  Escolha,
  Indicador,
  Indicadores,
  Tabela,
  Vazio,
} from '@celke/kole-react';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { ChartView } from '../components/ChartView';
import { usePolling } from '../hooks/usePolling';
import { ApiError, api } from '../services/api';
import type { Analysis, CropKey, Estimate } from '../types/api';
import { CROP_OPTIONS, formatNumber } from '../utils/format';

export function AnalysesPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const municipalities = usePolling(api.municipalities, 4000);
  const alerts = usePolling(() => api.alerts(), 0);
  const estimates = usePolling(api.estimates, 0);
  const list = municipalities.data ?? [];
  const code = Number(params.get('municipio')) || list[0]?.code;
  const crop = (params.get('cultura') as CropKey) || 'soja';
  const selected = list.find((m) => m.code === code);
  const [analysis, setAnalysis] = useState<Analysis>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const ready = selected?.status !== 'coletando';

  useEffect(() => {
    if (!code || !ready) return;
    let cancelled = false;
    setLoading(true);
    setError(undefined);
    api
      .analysis(code, crop)
      .then((a) => !cancelled && setAnalysis(a))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : 'Não foi possível carregar a análise.'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [code, crop, ready]);

  const choose = (next: { municipio?: number; cultura?: CropKey }) =>
    setParams({ municipio: String(next.municipio ?? code), cultura: next.cultura ?? crop }, { replace: true });

  if (municipalities.data && !list.length) {
    return (
      <div className="app-pagina">
        <CabecalhoPagina titulo="Análises" icone="chart-line" />
        <Vazio
          titulo="Nenhum município cadastrado"
          descricao="Cadastre um município: o sistema baixa a chuva diária (Open-Meteo) e a produção de soja e milho (IBGE) e cruza os dados."
          icone="map-pin"
        >
          <Botao rotulo="Cadastrar município" icone="plus" onClick={() => navigate('/municipios')} />
        </Vazio>
      </div>
    );
  }

  const myAlerts = (alerts.data ?? []).filter((a) => a.municipality_code === code);
  const myEstimates = (estimates.data ?? []).filter(
    (e) => e.level === 'brasil' || e.territory_code === selected?.state_code,
  );

  return (
    <div className="app-pagina">
      <CabecalhoPagina
        titulo="Análises"
        icone="chart-line"
        acoes={<Botao rotulo="Perguntar à IA" icone="message-square" onClick={() => navigate('/chat')} />}
      >
        Chuva da safra cruzada com o rendimento. As contas são feitas pelo sistema; a IA interpreta.
      </CabecalhoPagina>

      <div className="app-filtros">
        <CampoSelect<number>
          rotulo="Município"
          opcoes={list.map((m) => ({ valor: m.code, rotulo: `${m.name} (${m.state})` }))}
          valor={code ?? null}
          aoMudar={(v) => v && choose({ municipio: v })}
          comBusca
        />
        <Escolha<CropKey> rotulo="Cultura" opcoes={CROP_OPTIONS} valor={crop} aoMudar={(v) => choose({ cultura: v })} />
      </div>

      {selected?.status === 'coletando' && (
        <Alerta severidade="info" titulo="Coletando os dados deste município" mensagem={selected.status_message ?? ''} />
      )}
      {selected?.status === 'erro' && (
        <Alerta
          severidade="err"
          titulo="A última coleta deste município falhou"
          mensagem={selected.status_message ?? ''}
          acoes={<Botao rotulo="Ver municípios" tamanho="pequeno" onClick={() => navigate('/municipios')} />}
        />
      )}
      {myAlerts.map((a) => (
        <Alerta
          key={a.id}
          severidade={a.severity}
          titulo={a.title}
          mensagem={a.message}
          acoes={<Botao rotulo="Ver alerta" tamanho="pequeno" onClick={() => navigate('/alertas')} />}
        />
      ))}
      {error && <Alerta severidade="err" titulo="Não foi possível carregar a análise" mensagem={error} />}

      <Indicadores>
        {(analysis?.indicators ?? [{ rotulo: 'Carregando', valor: '–' }]).map((i) => (
          <Indicador
            key={i.rotulo}
            rotulo={i.rotulo}
            valor={i.valor}
            descricao={'descricao' in i ? (i.descricao ?? undefined) : undefined}
            variacao={'variacao' in i ? (i.variacao ?? undefined) : undefined}
            tendencia={'tendencia' in i ? (i.tendencia ?? undefined) : undefined}
            carregando={loading || !analysis}
          />
        ))}
      </Indicadores>

      {analysis && (
        <div className="app-graficos">
          {analysis.charts.map((chart, index) => (
            <Card key={chart.titulo} className={index === 0 ? 'app-grafico-largo' : undefined}>
              <ChartView spec={chart} altura={index === 0 ? 320 : 260} />
            </Card>
          ))}
        </div>
      )}

      {myEstimates.length > 0 && (
        <Card titulo="Estimativa da safra em andamento" subtitulo="LSPA/IBGE, último levantamento">
          <Tabela<Estimate>
            rotulo="Estimativas da safra"
            registros={myEstimates}
            chave={(e) => `${e.level}-${e.territory_code}-${e.product}`}
            colunas={[
              { campo: 'territory_name', rotulo: 'Território', destaque: true },
              { campo: 'product_name', rotulo: 'Produto' },
              { campo: 'period_label', rotulo: 'Levantamento' },
              { campo: 'production_t', rotulo: 'Produção', alinhamento: 'direita', formato: (v) => formatNumber(v as number, 't') },
              { campo: 'yield_kg_ha', rotulo: 'Rendimento', alinhamento: 'direita', formato: (v) => formatNumber(v as number, 'kg/ha') },
              {
                campo: 'expected_yield_kg_ha',
                rotulo: 'Esperado pela tendência',
                alinhamento: 'direita',
                formato: (v) => formatNumber(v as number | null, 'kg/ha'),
              },
            ]}
          />
        </Card>
      )}

      {analysis && (
        <Card titulo="Como ler estes números" recolhivel recolhidoInicial>
          <ul className="app-notas">
            {analysis.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
``````

`frontend/src/pages/ChatPage.tsx`:

``````tsx
import {
  Alerta,
  Botao,
  CabecalhoPagina,
  CampoMensagem,
  Conversa,
  Dialogo,
  ItemLista,
  Lista,
  Mensagem,
  Referencias,
  Vazio,
  formatDataHoraBr,
  useConfirmacao,
  useToast,
} from '@celke/kole-react';
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { ChartView } from '../components/ChartView';
import { usePolling } from '../hooks/usePolling';
import { ApiError, api, streamChat } from '../services/api';
import type { ChartSpec, StoredMessage, ToolCallRecord } from '../types/api';

const TOOL_LABEL: Record<string, string> = {
  listar_municipios: 'Municípios cadastrados',
  consultar_chuva: 'Chuva no período',
  chuva_da_safra: 'Chuva das safras',
  consultar_producao: 'Produção e rendimento',
  correlacao_chuva_rendimento: 'Correlação chuva × rendimento',
  estimativa_safra: 'Estimativa da safra',
  ver_descobertas: 'Descobertas',
  ver_alertas: 'Alertas',
  previsao_safra: 'Previsão do modelo treinado',
  mostrar_grafico: 'Gráfico',
};

const EXAMPLES = [
  'Quanto choveu em cada safra de soja nos municípios cadastrados?',
  'A chuva da safra explica o rendimento da soja? Mostre o gráfico.',
  'Qual foi a pior safra de milho e o que aconteceu com a chuva?',
  'Qual a previsão do modelo para a próxima safra de milho em Rio Verde?',
  'Qual a estimativa da safra de soja deste ano no Brasil?',
];

function toReference(t: ToolCallRecord, i: number) {
  const args = Object.entries(t.arguments)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(' · ');
  return {
    id: `${t.name}-${i}`,
    titulo: `${TOOL_LABEL[t.name] ?? t.name}${t.ok ? '' : ' (não deu certo)'}`,
    detalhe: t.source ?? undefined,
    trecho: args ? `${t.summary}\n${args}` : t.summary,
  };
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  state: 'concluida' | 'gerando' | 'erro';
  toolCalls: ToolCallRecord[];
  charts: ChartSpec[];
  /** Ferramenta em execução agora. */
  working?: string;
  thinking?: boolean;
  error?: string;
  createdAt: Date;
}

const newId = () => crypto.randomUUID();

function fromStored(m: StoredMessage): ChatMessage {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    state: m.state,
    toolCalls: m.tool_calls,
    charts: m.charts,
    error: m.error_message ?? undefined,
    createdAt: new Date(m.created_at),
  };
}

export function ChatPage() {
  const toast = useToast();
  const confirmar = useConfirmacao();
  const [params, setParams] = useSearchParams();
  const conversationParam = params.get('conversa');
  const conversations = usePolling(api.conversations, 0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  // Pergunta sugerida pela página Descobertas (?pergunta=)
  const [text, setText] = useState(() => params.get('pergunta') ?? '');
  const [listOpen, setListOpen] = useState(false);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const abortRef = useRef<AbortController | null>(null);
  const currentRef = useRef<string | null>(null);
  const generating = messages.some((m) => m.state === 'gerando');
  const current = conversations.data?.find((c) => c.id === conversationParam);

  // A conversa da URL: abre ao recarregar a página ou ao escolher na lista.
  useEffect(() => {
    if (conversationParam === currentRef.current) return;
    abortRef.current?.abort();
    currentRef.current = conversationParam;
    setLoadError(undefined);
    if (!conversationParam) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setLoadingConversation(true);
    setMessages([]);
    api
      .conversation(conversationParam)
      .then((c) => !cancelled && setMessages(c.messages.map(fromStored)))
      .catch((e) => {
        if (cancelled) return;
        currentRef.current = null;
        setLoadError(e instanceof ApiError ? e.message : 'Não foi possível abrir a conversa.');
      })
      .finally(() => !cancelled && setLoadingConversation(false));
    return () => {
      cancelled = true;
    };
  }, [conversationParam]);

  useEffect(() => () => abortRef.current?.abort(), []);

  function patch(id: string, change: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) {
    setMessages((list) =>
      list.map((m) => (m.id === id ? { ...m, ...(typeof change === 'function' ? change(m) : change) } : m)),
    );
  }

  async function ask(question: string, assistantId: string, retry = false) {
    const controller = new AbortController();
    abortRef.current = controller;
    const body = { question, conversation_id: currentRef.current ?? undefined, retry };
    try {
      for await (const event of streamChat(body, controller.signal)) {
        if (controller.signal.aborted) break;
        if (event.type === 'conversation') {
          if (currentRef.current !== event.id) {
            // A conversa nova vai para a URL: recarregar a página continua nela.
            currentRef.current = event.id;
            setParams({ conversa: event.id }, { replace: true });
          }
        } else if (event.type === 'thinking') patch(assistantId, { thinking: true });
        else if (event.type === 'tool_call') patch(assistantId, { working: TOOL_LABEL[event.name] ?? event.name });
        else if (event.type === 'tool_result')
          patch(assistantId, (m) => ({ toolCalls: [...m.toolCalls, event.result], working: undefined }));
        else if (event.type === 'chart') patch(assistantId, (m) => ({ charts: [...m.charts, event.chart] }));
        else if (event.type === 'token') patch(assistantId, (m) => ({ content: m.content + event.text }));
        else if (event.type === 'error') {
          patch(assistantId, { state: 'erro', error: event.message, working: undefined });
          return;
        } else if (event.type === 'done') break;
      }
      patch(assistantId, (m) => ({
        state: 'concluida',
        working: undefined,
        content: m.content || (controller.signal.aborted ? 'Resposta interrompida.' : m.content),
      }));
    } catch (e) {
      if (controller.signal.aborted) {
        patch(assistantId, (m) => ({ state: 'concluida', working: undefined, content: m.content || 'Resposta interrompida.' }));
      } else {
        patch(assistantId, {
          state: 'erro',
          working: undefined,
          error: e instanceof ApiError ? e.message : 'Não foi possível obter a resposta.',
        });
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      void conversations.reload();
    }
  }

  function send(question: string) {
    if (generating || !question.trim()) return;
    const assistantId = newId();
    const now = new Date();
    setMessages((list) => [
      ...list,
      { id: newId(), role: 'user', content: question, state: 'concluida', toolCalls: [], charts: [], createdAt: now },
      { id: assistantId, role: 'assistant', content: '', state: 'gerando', toolCalls: [], charts: [], createdAt: now },
    ]);
    void ask(question, assistantId);
  }

  /** Só a última resposta, que deu erro: o backend refaz a mesma pergunta. */
  function retry(message: ChatMessage) {
    const question = [...messages].reverse().find((m) => m.role === 'user')?.content;
    if (!question || generating) return;
    patch(message.id, { state: 'gerando', content: '', thinking: false, error: undefined, toolCalls: [], charts: [] });
    void ask(question, message.id, true);
  }

  function openConversation(id: string | null) {
    setListOpen(false);
    setText('');
    setParams(id ? { conversa: id } : {});
  }

  async function removeConversation() {
    if (!conversationParam) return;
    const ok = await confirmar.remover({
      titulo: 'Excluir conversa?',
      mensagem: `"${current?.title ?? 'Esta conversa'}" e todas as mensagens serão removidas.`,
    });
    if (!ok) return;
    try {
      await api.deleteConversation(conversationParam);
      toast.ok('Conversa excluída');
      openConversation(null);
      await conversations.reload();
    } catch (e) {
      toast.err('Não foi possível excluir', e instanceof Error ? e.message : undefined);
    }
  }

  return (
    <div className="app-chat">
      <CabecalhoPagina
        className="app-chat-cabecalho"
        titulo={current?.title ?? 'Chat'}
        icone="message-square"
        acoes={
          <>
            <Botao
              rotulo="Conversas"
              icone="history"
              severidade="secundario"
              disabled={generating}
              onClick={() => {
                setListOpen(true);
                void conversations.reload();
              }}
            />
            {conversationParam && (
              <Botao
                rotulo="Excluir"
                icone="trash-2"
                severidade="secundario"
                disabled={generating}
                onClick={() => void removeConversation()}
              />
            )}
            <Botao
              rotulo="Nova conversa"
              icone="plus"
              severidade="secundario"
              disabled={(!messages.length && !conversationParam) || generating}
              onClick={() => openConversation(null)}
            />
          </>
        }
      />

      <Dialogo
        aberto={listOpen}
        aoFechar={() => setListOpen(false)}
        titulo="Conversas"
        subtitulo="Da mais recente para a mais antiga"
        icone="history"
        aparencia="lateral"
      >
        {conversations.error ? (
          <Alerta severidade="err" titulo="Não foi possível carregar as conversas" mensagem={conversations.error.message} />
        ) : conversations.data?.length ? (
          <Lista rotulo="Conversas salvas">
            {conversations.data.map((c) => (
              <ItemLista
                key={c.id}
                titulo={c.title}
                icone="message-square"
                ativo={c.id === conversationParam}
                onClick={() => openConversation(c.id)}
              >
                {formatDataHoraBr(new Date(c.updated_at))}
              </ItemLista>
            ))}
          </Lista>
        ) : (
          <Vazio
            titulo={conversations.loading ? 'Carregando…' : 'Nenhuma conversa ainda'}
            descricao="As conversas ficam salvas aqui assim que você faz a primeira pergunta."
            icone="history"
          />
        )}
      </Dialogo>

      {loadError && (
        <Alerta
          severidade="err"
          titulo="Não foi possível abrir a conversa"
          mensagem={loadError}
          acoes={<Botao rotulo="Nova conversa" tamanho="pequeno" onClick={() => openConversation(null)} />}
        />
      )}

      <div className="app-chat-conversa">
        <Conversa
          rotulo="Conversa com o assistente"
          larguraMaxima="56rem"
          vazio={
            loadingConversation ? (
              <Vazio titulo="Abrindo a conversa…" icone="history" />
            ) : (
              <Vazio
                titulo="Pergunte sobre chuva e safra"
                descricao="A IA consulta os dados com ferramentas e responde com os números calculados pelo sistema. A primeira resposta demora mais: o modelo é carregado na memória."
                icone="bot"
              >
                <div className="app-exemplos">
                  {EXAMPLES.map((q) => (
                    <Botao key={q} rotulo={q} severidade="secundario" tamanho="pequeno" onClick={() => send(q)} />
                  ))}
                </div>
              </Vazio>
            )
          }
          campo={
            <CampoMensagem
              valor={text}
              aoMudar={setText}
              aoEnviar={(question) => {
                setText('');
                send(question);
              }}
              gerando={generating}
              aoParar={() => abortRef.current?.abort()}
              desabilitado={loadingConversation}
              placeholder="Ex.: a chuva de janeiro influencia o rendimento da soja em Rio Verde?"
              maxCaracteres={4000}
            />
          }
        >
          {messages.map((m, index) => {
            if (m.role === 'user') {
              return (
                <Mensagem key={m.id} autor="usuario" nome="Você" hora={m.createdAt}>
                  {m.content}
                </Mensagem>
              );
            }
            const status = m.working
              ? `Consultando: ${m.working}…`
              : m.thinking
                ? 'Analisando…'
                : m.toolCalls.length
                  ? 'Escrevendo a resposta…'
                  : 'Pensando…';
            return (
              <Mensagem
                key={m.id}
                autor="assistente"
                nome="Celke IA Agro"
                avatar={<span className="app-avatar-ia" aria-hidden="true">IA</span>}
                estado={m.state}
                erro={m.error}
                aoTentarNovamente={index === messages.length - 1 ? () => retry(m) : undefined}
                copiavel
                textoCopia={m.content}
                rodape={
                  m.toolCalls.length || m.charts.length ? (
                    <div className="app-resposta-extra">
                      {m.charts.map((chart) => (
                        <div key={chart.titulo} className="app-grafico-chat">
                          <ChartView spec={chart} altura={240} />
                        </div>
                      ))}
                      {m.toolCalls.length > 0 && (
                        <Referencias
                          itens={m.toolCalls.map(toReference)}
                          rotulo={(n) => (n === 1 ? '1 ferramenta usada' : `${n} ferramentas usadas`)}
                        />
                      )}
                    </div>
                  ) : undefined
                }
              >
                {m.content || (m.state === 'gerando' ? <span className="app-pensando">{status}</span> : undefined)}
              </Mensagem>
            );
          })}
        </Conversa>
      </div>
    </div>
  );
}
``````

`frontend/src/pages/DiscoveriesPage.tsx`:

``````tsx
import { Alerta, Botao, CabecalhoPagina, Card, Chip, Vazio, formatDataHoraBr, useToast } from '@celke/kole-react';
import { useNavigate } from 'react-router';
import { ChartView } from '../components/ChartView';
import { usePolling } from '../hooks/usePolling';
import { ApiError, api } from '../services/api';
import type { Discovery, DiscoveryReport } from '../types/api';

const KIND_LABEL: Record<Discovery['kind'], string> = {
  correlacao: 'Relação estatística',
  pior_safra: 'Pior safra',
  comparacao_uf: 'Comparação com a UF',
  tendencia: 'Tendência',
};

async function loadReport(): Promise<DiscoveryReport | null> {
  try {
    return await api.discoveries();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

function stat(value: unknown, digits: number): string {
  return typeof value === 'number' ? value.toLocaleString('pt-BR', { maximumFractionDigits: digits }) : '–';
}

export function DiscoveriesPage() {
  const toast = useToast();
  const navigate = useNavigate();
  const report = usePolling(loadReport, 5000);
  const r = report.data;
  const generating = r?.status === 'gerando';

  async function regenerate() {
    try {
      await api.regenerateDiscoveries();
      toast.info('Gerando o relatório', 'A IA leva de alguns segundos a poucos minutos, conforme o computador.');
      await report.reload();
    } catch (e) {
      toast.err('Não foi possível gerar', e instanceof ApiError ? e.message : undefined);
    }
  }

  const ask = (question: string) => navigate(`/chat?pergunta=${encodeURIComponent(question)}`);

  return (
    <div className="app-pagina">
      <CabecalhoPagina
        titulo="Descobertas"
        icone="lightbulb"
        acoes={
          <Botao
            rotulo="Gerar de novo"
            icone="sparkles"
            carregando={generating}
            disabled={generating}
            onClick={() => void regenerate()}
          />
        }
      >
        Depois de cada coleta, o sistema testa combinações de chuva × rendimento e guarda só as relações que passam no
        filtro estatístico. A IA recebe os números prontos e escreve a interpretação, as hipóteses e as próximas perguntas.
      </CabecalhoPagina>

      {report.error && <Alerta severidade="err" titulo="Não foi possível carregar" mensagem={report.error.message} />}

      {report.data === null && (
        <Vazio
          titulo="Ainda não há descobertas"
          descricao="Elas aparecem depois da primeira coleta completa de chuva e produção de um município."
          icone="lightbulb"
        >
          <Botao rotulo="Cadastrar município" icone="map-pin" onClick={() => navigate('/municipios')} />
        </Vazio>
      )}

      {r && (
        <>
          {generating && <Alerta severidade="info" titulo="A IA está interpretando as descobertas…" />}
          {r.status === 'erro' && (
            <Alerta
              severidade="warn"
              titulo="Os números estão abaixo, mas a IA não conseguiu interpretar"
              mensagem={r.error_message ?? ''}
            />
          )}
          <Card
            titulo="Resumo da IA"
            subtitulo={`${formatDataHoraBr(new Date(r.created_at))} · modelo ${r.model} · ${r.tests} relações testadas`}
          >
            <p className="app-texto">{r.summary ?? (generating ? 'Gerando…' : 'Sem resumo.')}</p>
            {r.next_questions.length > 0 && (
              <>
                <h3 className="app-subtitulo">Próximas perguntas</h3>
                <ul className="app-perguntas">
                  {r.next_questions.map((q) => (
                    <li key={q}>
                      <span>{q}</span>
                      <Botao rotulo="Perguntar" icone="message-square" tamanho="pequeno" severidade="secundario" onClick={() => ask(q)} />
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>

          {r.discoveries.map((d) => (
            <Card key={d.id} titulo={d.title} subtitulo={`${KIND_LABEL[d.kind]} · ${d.municipality_name}`}>
              <div className="app-descoberta">
                <div className="app-descoberta-texto">
                  <p className="app-fato">
                    <strong>Fato calculado:</strong> {d.fact}
                  </p>
                  {d.kind === 'correlacao' && (
                    <div className="app-chips">
                      <Chip rotulo={`r = ${stat(d.stats.r, 2)}`} />
                      <Chip rotulo={`q = ${stat(d.stats.q, 3)}`} />
                      <Chip rotulo={`${stat(d.stats.n, 0)} safras`} />
                    </div>
                  )}
                  {d.interpretation && (
                    <p className="app-texto">
                      <strong>Interpretação da IA:</strong> {d.interpretation}
                    </p>
                  )}
                  {d.hypothesis && (
                    <p className="app-texto app-hipotese">
                      <strong>Hipótese:</strong> {d.hypothesis}
                    </p>
                  )}
                </div>
                {d.chart && <ChartView spec={d.chart} altura={240} />}
              </div>
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
``````

`frontend/src/pages/ForecastPage.tsx`:

``````tsx
import {
  Alerta,
  Botao,
  CabecalhoPagina,
  Card,
  CampoSelect,
  Chip,
  Escolha,
  Indicador,
  Indicadores,
  Tabela,
  Vazio,
  formatDataHoraBr,
  useToast,
} from '@celke/kole-react';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { ChartView } from '../components/ChartView';
import { usePolling } from '../hooks/usePolling';
import { ApiError, api } from '../services/api';
import type { CropKey, ForecastView, SeasonForecast } from '../types/api';
import { CROP_OPTIONS, formatIsoDate, formatNumber } from '../utils/format';

const pct = (v: number) => `${v > 0 ? '+' : ''}${v.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;

function ForecastCard({ f, cropName }: { f: SeasonForecast; cropName: string }) {
  const title =
    f.status === 'em_andamento'
      ? `Safra ${f.season_year} (em andamento, chuva até ${formatIsoDate(f.rain_until)})`
      : `Safra ${f.season_year} (chuva completa, aguardando o IBGE)`;
  return (
    <Card titulo={title} subtitulo={`Rendimento ${cropName.toLowerCase() === 'soja' ? 'da soja' : 'do milho'} previsto pelo modelo`}>
      <Indicadores>
        <Indicador
          rotulo="Previsto"
          valor={formatNumber(f.predicted_kg_ha, 'kg/ha')}
          descricao={`Faixa: ${formatNumber(f.low_kg_ha)} a ${formatNumber(f.high_kg_ha)} kg/ha`}
          variacao={f.vs_trend_pct}
          cor="var(--pri)"
        />
        <Indicador rotulo="Só a tendência" valor={formatNumber(f.trend_kg_ha, 'kg/ha')} descricao="Com a chuva na média" />
        <Indicador
          rotulo="Estimativa do IBGE (UF)"
          valor={formatNumber(f.ibge_state_kg_ha, 'kg/ha')}
          descricao={f.ibge_period_label ? `LSPA de ${f.ibge_period_label}, média da UF` : 'Sem estimativa desta safra'}
        />
        <Indicador rotulo="Chuva da janela" valor={formatNumber(f.rain_mm, 'mm')} descricao={f.status === 'em_andamento' ? 'Até agora' : 'Janela completa'} />
      </Indicadores>
    </Card>
  );
}

export function ForecastPage() {
  const toast = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const municipalities = usePolling(api.municipalities, 0);
  const list = municipalities.data ?? [];
  const code = Number(params.get('municipio')) || list[0]?.code;
  const crop = (params.get('cultura') as CropKey) || 'milho';
  const [view, setView] = useState<ForecastView>();
  const [error, setError] = useState<string>();

  async function load() {
    if (!code) return;
    try {
      setView(await api.forecast(code, crop));
      setError(undefined);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Não foi possível carregar a previsão.');
    }
  }

  useEffect(() => {
    setView(undefined);
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, crop]);

  // Enquanto treina, atualiza sozinho.
  useEffect(() => {
    if (!view?.training) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view?.training]);

  async function retrain() {
    try {
      await api.trainForecasts();
      toast.info('Treinando o modelo', 'Leva alguns segundos; a explicação da IA chega logo depois.');
      setView((v) => (v ? { ...v, training: true } : v));
    } catch (e) {
      toast.err('Não foi possível treinar', e instanceof ApiError ? e.message : undefined);
    }
  }

  const choose = (next: { municipio?: number; cultura?: CropKey }) =>
    setParams({ municipio: String(next.municipio ?? code), cultura: next.cultura ?? crop }, { replace: true });

  if (municipalities.data && !list.length) {
    return (
      <div className="app-pagina">
        <CabecalhoPagina titulo="Previsão da safra" icone="brain" />
        <Vazio titulo="Nenhum município cadastrado" descricao="O modelo é treinado com a chuva e a produção dos municípios cadastrados." icone="map-pin">
          <Botao rotulo="Cadastrar município" icone="plus" onClick={() => navigate('/municipios')} />
        </Vazio>
      </div>
    );
  }

  const latest = view?.latest;
  const r = latest?.result;

  return (
    <div className="app-pagina">
      <CabecalhoPagina
        titulo="Previsão da safra"
        icone="brain"
        acoes={
          <Botao rotulo="Treinar de novo" icone="refresh-cw" carregando={view?.training} disabled={view?.training} onClick={() => void retrain()} />
        }
      >
        Aqui a IA é treinada de verdade: um modelo aprende, com as safras passadas, como o rendimento responde ao ano
        (tecnologia) e à chuva. Antes de ser usado, ele é testado prevendo cada safra sem tê-la visto. O treino roda
        sozinho depois de cada coleta.
      </CabecalhoPagina>

      <div className="app-filtros">
        <CampoSelect<number>
          rotulo="Município"
          opcoes={list.map((m) => ({ valor: m.code, rotulo: `${m.name} (${m.state})` }))}
          valor={code ?? null}
          aoMudar={(v) => v && choose({ municipio: v })}
          comBusca
        />
        <Escolha<CropKey> rotulo="Cultura" opcoes={CROP_OPTIONS} valor={crop} aoMudar={(v) => choose({ cultura: v })} />
      </div>

      {error && <Alerta severidade="err" titulo="Não foi possível carregar" mensagem={error} />}
      {view && !latest && (
        <Vazio
          titulo={view.training ? 'Treinando…' : 'Ainda não há modelo treinado'}
          descricao="O treino precisa de safras com chuva e produção. Ele roda depois das coletas e pelo botão Treinar de novo."
          icone="brain"
        />
      )}

      {r && latest && (
        <>
          <Card
            titulo="O que o modelo aprendeu"
            subtitulo={`Treinado em ${formatDataHoraBr(new Date(latest.trained_at))} · ${latest.trigger === 'coleta' ? 'depois de uma coleta' : 'pelo botão'}`}
          >
            <div className="app-pagina">
              <Indicadores>
                <Indicador rotulo="Safras de treino" valor={String(r.seasons_used)} descricao={`${r.first_year} a ${r.last_year}`} icone="database" />
                <Indicador rotulo="Modelos testados" valor={String(r.candidates)} descricao="Tendência e combinações de até 2 variáveis de chuva" icone="sparkles" />
                <Indicador
                  rotulo="Erro do modelo"
                  valor={formatNumber(r.error_kg_ha, 'kg/ha')}
                  descricao={`${r.error_pct.toLocaleString('pt-BR')}% em média, safra a safra`}
                  cor="var(--pri)"
                />
                <Indicador
                  rotulo="Erro só com a tendência"
                  valor={formatNumber(r.baseline_error_kg_ha, 'kg/ha')}
                  descricao={r.uses_rain ? `A chuva reduziu o erro em ${pct(r.gain_pct).replace('+', '')}` : 'A chuva não melhorou a previsão'}
                />
              </Indicadores>
              <div className="app-chips">
                {r.features.length ? (
                  r.features.map((f) => <Chip key={f.key} rotulo={`${f.label}: ${f.coefficient.toLocaleString('pt-BR')} kg/ha por ${f.unit}`} />)
                ) : (
                  <Chip rotulo="Só a tendência: nenhuma variável de chuva reduziu o erro" />
                )}
                <Chip rotulo={`Tendência: ${r.year_coefficient.toLocaleString('pt-BR')} kg/ha por ano`} />
              </div>
              <p className="app-fato">
                <strong>Equação treinada:</strong> {r.equation}
              </p>
              {latest.explanation ? (
                <p className="app-texto">
                  <strong>Explicação da IA:</strong> {latest.explanation}
                </p>
              ) : (
                <p className="app-texto app-pensando">A IA está escrevendo a explicação…</p>
              )}
            </div>
          </Card>

          {r.charts[0] && (
            <Card>
              <ChartView spec={r.charts[0]} altura={300} />
            </Card>
          )}

          {r.forecasts.map((f) => (
            <ForecastCard key={f.season_year} f={f} cropName={r.crop_name} />
          ))}
          {r.charts.slice(1).map((chart) => (
            <Card key={chart.titulo}>
              <ChartView spec={chart} altura={240} />
            </Card>
          ))}

          <Card titulo="Histórico de treinos" subtitulo="O modelo muda quando chegam dados novos">
            <Tabela
              rotulo="Histórico de treinos"
              registros={view?.history ?? []}
              chave={(h) => h.id}
              colunas={[
                { campo: 'trained_at', rotulo: 'Quando', formato: (v) => formatDataHoraBr(new Date(String(v))) },
                { campo: 'trigger', rotulo: 'Origem', formato: (v) => (v === 'coleta' ? 'Coleta' : 'Botão') },
                { campo: 'seasons_used', rotulo: 'Safras', alinhamento: 'direita' },
                { campo: 'features', rotulo: 'Variáveis de chuva', formato: (v) => ((v as string[]).length ? (v as string[]).join(', ') : 'nenhuma') },
                { campo: 'error_pct', rotulo: 'Erro', alinhamento: 'direita', formato: (v) => `${(v as number).toLocaleString('pt-BR')}%` },
                { campo: 'baseline_error_pct', rotulo: 'Só tendência', alinhamento: 'direita', formato: (v) => `${(v as number).toLocaleString('pt-BR')}%` },
              ]}
            />
          </Card>
        </>
      )}
    </div>
  );
}
``````

`frontend/src/pages/MunicipalitiesPage.tsx`:

``````tsx
import {
  AcaoLinha,
  Alerta,
  Botao,
  CabecalhoPagina,
  CampoCidade,
  CampoUf,
  Card,
  Tabela,
  useConfirmacao,
  useToast,
  type Municipio,
} from '@celke/kole-react';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { MunicipalityStatusLabel } from '../components/StatusLabel';
import { usePolling } from '../hooks/usePolling';
import { ApiError, api } from '../services/api';
import type { Municipality } from '../types/api';
import { formatIsoDate } from '../utils/format';

export function MunicipalitiesPage() {
  const toast = useToast();
  const confirmar = useConfirmacao();
  const navigate = useNavigate();
  const [uf, setUf] = useState<string>('');
  const [city, setCity] = useState<Municipio | string | null>(null);
  const [saving, setSaving] = useState(false);
  const [collecting, setCollecting] = useState(false);
  // Enquanto algum município coleta, a tabela se atualiza sozinha.
  const list = usePolling(api.municipalities, 3000);
  const busy = list.data?.some((m) => m.status === 'coletando');

  async function register() {
    if (!city || typeof city === 'string') return;
    setSaving(true);
    try {
      const m = await api.createMunicipality(Number(city.id));
      toast.ok(`${m.name} (${m.state}) cadastrado`, 'O histórico de chuva e produção está sendo baixado.');
      setCity(null);
      await list.reload();
    } catch (e) {
      toast.err('Não foi possível cadastrar', e instanceof ApiError ? e.message : undefined);
    } finally {
      setSaving(false);
    }
  }

  async function collectRain() {
    setCollecting(true);
    try {
      await api.collect('chuva');
      toast.info('Coleta de chuva iniciada', 'Acompanhe em Status e coletas.');
    } catch (e) {
      toast.err('Não foi possível coletar', e instanceof ApiError ? e.message : undefined);
    } finally {
      setCollecting(false);
    }
  }

  async function remove(m: Municipality) {
    const ok = await confirmar.remover({
      titulo: 'Excluir município?',
      mensagem: `${m.name} (${m.state}) sai das análises. A chuva e a produção dele são apagadas, a não ser que ele seja referência da média da UF de outro município cadastrado.`,
    });
    if (!ok) return;
    try {
      await api.deleteMunicipality(m.code);
      toast.ok('Município excluído');
      await list.reload();
    } catch (e) {
      toast.err('Não foi possível excluir', e instanceof ApiError ? e.message : undefined);
    }
  }

  return (
    <div className="app-pagina">
      <CabecalhoPagina titulo="Municípios" icone="map-pin">
        Ao cadastrar, o sistema baixa a chuva diária desde o primeiro ano configurado e a produção de soja e milho
        do IBGE. Também escolhe os municípios que mais plantam soja na UF para calcular a chuva média do estado.
      </CabecalhoPagina>

      <Card titulo="Cadastrar município">
        <div className="app-cadastro">
          <CampoUf rotulo="UF" valor={uf || null} aoMudar={(v) => setUf(v ?? '')} />
          <CampoCidade
            rotulo="Município"
            uf={uf}
            valor={city}
            aoMudar={setCity}
            buscarPorUf={(sigla) => api.stateMunicipalities(sigla).then((l) => l.map((m) => ({ id: m.code, nome: m.name })))}
            placeholder={uf ? 'Digite o nome' : 'Escolha a UF primeiro'}
            disabled={!uf}
          />
          <Botao
            rotulo="Cadastrar"
            icone="plus"
            carregando={saving}
            disabled={!city || typeof city === 'string'}
            onClick={() => void register()}
          />
        </div>
      </Card>

      {list.error && <Alerta severidade="err" titulo="Não foi possível carregar os municípios" mensagem={list.error.message} />}

      <Card
        titulo="Municípios cadastrados"
        subtitulo={busy ? 'Coletando… a tabela se atualiza sozinha' : undefined}
        acoes={
          <Botao
            rotulo="Coletar chuva agora"
            icone="cloud-rain"
            severidade="secundario"
            tamanho="pequeno"
            carregando={collecting}
            disabled={!list.data?.length}
            onClick={() => void collectRain()}
          />
        }
      >
        <Tabela<Municipality>
          rotulo="Municípios cadastrados"
          registros={list.data ?? []}
          carregando={list.loading}
          chave={(m) => m.code}
          vazioTitulo="Nenhum município cadastrado"
          vazioDescricao="Escolha a UF e o município acima."
          vazioIcone="map-pin"
          colunas={[
            { campo: 'name', rotulo: 'Município', destaque: true, render: (m) => `${m.name} (${m.state})` },
            {
              campo: 'status',
              rotulo: 'Situação',
              render: (m) => (
                <div className="app-situacao">
                  <MunicipalityStatusLabel status={m.status} />
                  {m.status_message && <small>{m.status_message}</small>}
                </div>
              ),
            },
            {
              campo: 'rain_first_day',
              rotulo: 'Chuva',
              render: (m) => (m.rain_days ? `${formatIsoDate(m.rain_first_day)} a ${formatIsoDate(m.rain_last_day)}` : '–'),
            },
            { campo: 'production_last_year', rotulo: 'Produção até', formato: (v) => (v as number | null) ?? '–' },
          ]}
          acoes={(m) => (
            <>
              <AcaoLinha
                icone="chart-line"
                rotulo="Ver análises"
                disabled={m.status === 'coletando'}
                onClick={() => navigate(`/?municipio=${m.code}`)}
              />
              <AcaoLinha icone="trash-2" rotulo="Excluir" severidade="err" onClick={() => void remove(m)} />
            </>
          )}
        />
      </Card>
    </div>
  );
}
``````

`frontend/src/pages/NotFoundPage.tsx`:

``````tsx
import { Botao, Vazio } from '@celke/kole-react';
import { useNavigate } from 'react-router';

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <Vazio titulo="Página não encontrada" descricao="O endereço não existe nesta aplicação." icone="circle-question-mark">
      <Botao rotulo="Ir para as análises" icone="chart-line" onClick={() => navigate('/')} />
    </Vazio>
  );
}
``````

`frontend/src/pages/StatusPage.tsx`:

``````tsx
import { Alerta, Botao, CabecalhoPagina, Card, Tabela, formatDataHoraBr, useToast } from '@celke/kole-react';
import { useState } from 'react';
import { OnlineStatus, RunStatusLabel, TRIGGER_LABEL } from '../components/StatusLabel';
import { usePolling } from '../hooks/usePolling';
import { ApiError, api } from '../services/api';
import type { CollectionRun, CollectionSource } from '../types/api';

const SOURCE_LABEL: Record<CollectionSource, string> = {
  chuva: 'Chuva',
  producao: 'Produção',
  estimativa: 'Estimativa',
};

export function StatusPage() {
  const toast = useToast();
  const status = usePolling(api.status, 10000);
  const collections = usePolling(api.collections, 4000);
  const [starting, setStarting] = useState<CollectionSource>();
  const s = status.data;

  async function collect(source: CollectionSource) {
    setStarting(source);
    try {
      await api.collect(source);
      toast.info('Coleta iniciada', 'O resultado aparece no registro abaixo.');
      await collections.reload();
    } catch (e) {
      toast.err('Não foi possível coletar', e instanceof ApiError ? e.message : undefined);
    } finally {
      setStarting(undefined);
    }
  }

  return (
    <div className="app-pagina">
      <CabecalhoPagina titulo="Status e coletas" icone="activity">
        Serviços, fontes de dados e o registro de cada coleta. A chuva é coletada todo dia; a produção e a estimativa da
        safra, uma vez por mês. Use "Buscar agora" quando precisar do dado na hora.
      </CabecalhoPagina>

      {s && !s.ollama.online && (
        <Alerta severidade="err" titulo="Ollama desconectado" mensagem={s.ollama.error ?? 'Veja: docker compose logs ollama'} />
      )}
      {s?.ollama.online && !s.ollama.chat_model.installed && (
        <Alerta
          severidade="warn"
          titulo="Modelo ainda não instalado"
          mensagem="O download inicial pode levar alguns minutos. Acompanhe com: docker compose logs -f ollama-init"
        />
      )}
      {s?.ollama.chat_model.tools === false && (
        <Alerta
          severidade="err"
          titulo="O modelo não aceita ferramentas"
          mensagem="O chat precisa de um modelo com tool calling (etiqueta tools no Ollama). Troque CHAT_MODEL no .env."
        />
      )}

      <div className="app-fontes">
        {(collections.data?.sources ?? []).map((src) => (
          <Card
            key={src.source}
            titulo={src.name}
            subtitulo={src.provider}
            acoes={
              <Botao
                rotulo={src.running ? 'Coletando…' : 'Buscar agora'}
                icone="refresh-cw"
                tamanho="pequeno"
                carregando={src.running || starting === src.source}
                disabled={src.running}
                onClick={() => void collect(src.source)}
              />
            }
          >
            <dl className="app-dados">
              <dt>Último dado</dt>
              <dd>{src.last_data ?? '–'}</dd>
              <dt>Agendamento</dt>
              <dd>{src.schedule}</dd>
              <dt>Última coleta</dt>
              <dd>
                {src.last_run ? (
                  <>
                    <RunStatusLabel status={src.last_run.status} /> {formatDataHoraBr(new Date(src.last_run.started_at))}
                  </>
                ) : (
                  '–'
                )}
              </dd>
            </dl>
          </Card>
        ))}
      </div>

      <Card titulo="Registro das coletas" subtitulo="As 50 mais recentes">
        <Tabela<CollectionRun>
          rotulo="Registro das coletas"
          registros={collections.data?.runs ?? []}
          carregando={collections.loading}
          erro={collections.error?.message}
          chave={(r) => r.id}
          vazioTitulo="Nenhuma coleta ainda"
          vazioDescricao="Cadastre um município para começar."
          vazioIcone="database"
          colunas={[
            { campo: 'started_at', rotulo: 'Quando', formato: (v) => formatDataHoraBr(new Date(String(v))) },
            { campo: 'source', rotulo: 'Fonte', destaque: true, formato: (v) => SOURCE_LABEL[v as CollectionSource] },
            { campo: 'trigger', rotulo: 'Origem', formato: (v) => TRIGGER_LABEL[v as CollectionRun['trigger']] },
            { campo: 'status', rotulo: 'Situação', render: (r) => <RunStatusLabel status={r.status} /> },
            { campo: 'records', rotulo: 'Registros', alinhamento: 'direita' },
            { campo: 'message', rotulo: 'Mensagem', formato: (v) => (v as string | null) ?? '' },
          ]}
        />
      </Card>

      <Card titulo="Serviços" subtitulo="Atualizado a cada 10 segundos">
        {status.error ? (
          <Alerta severidade="err" titulo="Backend indisponível" mensagem={status.error.message} />
        ) : (
          <ul className="app-lista-servicos">
            <li>
              <span>Backend (API)</span>
              <OnlineStatus online={!!s?.backend.online} rotulo={s ? undefined : 'Verificando'} />
            </li>
            <li>
              <span>Ollama</span>
              <OnlineStatus online={!!s?.ollama.online} rotulo={s ? undefined : 'Verificando'} />
            </li>
            <li>
              <span>
                Modelo <code>{s?.ollama.chat_model.name}</code>
              </span>
              <OnlineStatus
                online={!!s?.ollama.chat_model.installed}
                rotulo={s?.ollama.chat_model.installed ? (s.ollama.chat_model.tools ? 'Instalado, com ferramentas' : 'Instalado') : 'Ausente'}
              />
            </li>
            <li>
              <span>PostgreSQL (dados, coletas e conversas)</span>
              <OnlineStatus online={!!s?.database.online} rotulo={s ? undefined : 'Verificando'} />
            </li>
            <li>
              <span>Agendador ({s?.scheduler.timezone})</span>
              <OnlineStatus online={!!s?.scheduler.enabled} rotulo={s?.scheduler.enabled ? 'Ligado' : 'Desligado'} />
            </li>
          </ul>
        )}
      </Card>
    </div>
  );
}
``````

`frontend/src/router.tsx`:

``````tsx
import { createBrowserRouter } from 'react-router';
import { AppLayout } from './layouts/AppLayout';
import { AlertsPage } from './pages/AlertsPage';
import { AnalysesPage } from './pages/AnalysesPage';
import { ChatPage } from './pages/ChatPage';
import { DiscoveriesPage } from './pages/DiscoveriesPage';
import { ForecastPage } from './pages/ForecastPage';
import { MunicipalitiesPage } from './pages/MunicipalitiesPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { StatusPage } from './pages/StatusPage';

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <AnalysesPage /> },
      { path: '/previsao', element: <ForecastPage /> },
      { path: '/descobertas', element: <DiscoveriesPage /> },
      { path: '/alertas', element: <AlertsPage /> },
      { path: '/chat', element: <ChatPage /> },
      { path: '/municipios', element: <MunicipalitiesPage /> },
      { path: '/status', element: <StatusPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
``````

`frontend/src/services/api.ts`:

``````ts
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
  trainForecasts: () => request<void>('/forecasts/train', { method: 'POST' }),
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
``````

`frontend/src/services/sse.test.ts`:

``````ts
import { describe, expect, it } from 'vitest';
import { parseSseBlock, readSse } from './sse';

function stream(parts: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      parts.forEach((p) => controller.enqueue(encoder.encode(p)));
      controller.close();
    },
  });
}

describe('parseSseBlock', () => {
  it('lê os eventos das ferramentas e do gráfico', () => {
    expect(parseSseBlock('event: tool_call\ndata: {"name":"consultar_chuva","arguments":{"municipio":"Rio Verde"}}')).toEqual({
      type: 'tool_call',
      name: 'consultar_chuva',
      arguments: { municipio: 'Rio Verde' },
    });
    const result = parseSseBlock('event: tool_result\ndata: {"name":"x","ok":true,"summary":"ok","source":null,"arguments":{}}');
    expect(result).toMatchObject({ type: 'tool_result', result: { name: 'x', ok: true } });
    expect(parseSseBlock('event: chart\ndata: {"tipo":"linha","titulo":"T"}')).toEqual({
      type: 'chart',
      chart: { tipo: 'linha', titulo: 'T' },
    });
  });

  it('lê erro e ignora evento desconhecido', () => {
    expect(parseSseBlock('event: error\ndata: {"codigo":"x","mensagem":"Falhou"}')).toEqual({
      type: 'error',
      code: 'x',
      message: 'Falhou',
    });
    expect(parseSseBlock('event: outro\ndata: {}')).toBeNull();
  });
});

describe('readSse', () => {
  it('junta blocos partidos entre pedaços', async () => {
    const events = [];
    for await (const e of readSse(stream(['event: token\ndata: {"te', 'xt":"Olá"}\n\nevent: done\ndata: {}\n\n']))) {
      events.push(e);
    }
    expect(events).toEqual([{ type: 'token', text: 'Olá' }, { type: 'done' }]);
  });
});
``````

`frontend/src/services/sse.ts`:

``````ts
import type { ChartSpec, ChatEvent, ToolCallRecord } from '../types/api';

/** Converte um bloco `event: x\ndata: {...}` num evento do chat (ou `null` se não reconhecido). */
export function parseSseBlock(block: string): ChatEvent | null {
  let event = 'message';
  const data: string[] = [];
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  const payload = JSON.parse(data.join('\n'));
  switch (event) {
    case 'conversation':
      return { type: 'conversation', id: String(payload.id), title: String(payload.title ?? '') };
    case 'thinking':
      return { type: 'thinking' };
    case 'tool_call':
      return { type: 'tool_call', name: String(payload.name), arguments: payload.arguments ?? {} };
    case 'tool_result':
      return { type: 'tool_result', result: payload as ToolCallRecord };
    case 'chart':
      return { type: 'chart', chart: payload as ChartSpec };
    case 'token':
      return { type: 'token', text: String(payload.text ?? '') };
    case 'done':
      return { type: 'done' };
    case 'error':
      return { type: 'error', code: String(payload.codigo ?? 'erro'), message: String(payload.mensagem ?? 'Erro') };
    default:
      return null;
  }
}

/**
 * Lê um stream SSE em pedaços. Os blocos podem chegar partidos entre dois
 * pedaços; o que sobra fica guardado até o próximo.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n');
      let end = buffer.indexOf('\n\n');
      while (end !== -1) {
        const parsed = parseSseBlock(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        if (parsed) yield parsed;
        end = buffer.indexOf('\n\n');
      }
      if (done) break;
    }
    if (buffer.trim()) {
      const parsed = parseSseBlock(buffer);
      if (parsed) yield parsed;
    }
  } finally {
    reader.releaseLock();
  }
}
``````

`frontend/src/styles.css`:

``````css
/* Ajustes do app sobre o Kole: só tokens do tema (tokens.css), sem cores fixas. */

/* Espaço igual entre os blocos da página (cabeçalho, alertas, indicadores, cards). */
.app-pagina {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.app-lista-servicos {
  list-style: none;
  margin: 0;
  padding: 0;
}

.app-lista-servicos li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.625rem 0;
  border-bottom: var(--hairline) solid var(--border);
  color: var(--t2);
}

.app-lista-servicos li:last-child {
  border-bottom: 0;
}

.app-lista-servicos code {
  color: var(--t3);
  overflow-wrap: anywhere;
}

/*
 * O chat ocupa exatamente a área de conteúdo da Estrutura: cabeçalho e
 * documentos ficam sempre visíveis e só a Conversa rola.
 */
.lp-content:has(> .lp-content-inner > .app-chat) {
  display: flex;
  flex-direction: column;
}

.lp-content-inner:has(> .app-chat) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.app-chat {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.app-chat > * {
  flex: none;
}

.app-chat > .app-chat-conversa {
  flex: 1;
  display: flex;
  flex-direction: column;
  /* janela muito baixa: a página volta a rolar em vez de esmagar a conversa */
  min-height: 16rem;
  border: var(--hairline) solid var(--border);
  border-radius: var(--r-card);
  background: var(--surface);
  overflow: hidden;
}

.app-chat-conversa > * {
  flex: 1;
  min-height: 0;
}

/* Título da conversa em até 2 linhas; sem espaço ao lado dele, os botões descem para a linha de baixo. */
.app-chat-cabecalho .lp-cab-topo {
  flex-wrap: wrap;
}

.app-chat-cabecalho .lp-cab-titulos {
  flex: 1 1 14rem;
}

.app-chat-cabecalho .lp-cab-titulo {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
}

@media (max-width: 40rem) {
  .app-chat-cabecalho.lp-cab {
    padding: 1rem;
  }

  .app-chat-cabecalho .lp-cab-topo {
    gap: 0.75rem;
  }

  .app-chat-cabecalho .lp-cab-tile {
    width: 2.25rem;
    height: 2.25rem;
  }

  .app-chat-cabecalho .lp-cab-titulos {
    flex-basis: 0;
  }

  .app-chat-cabecalho .lp-cab-titulo {
    font-size: var(--fs-corpo);
    font-weight: 700;
  }

  .app-chat-cabecalho .lp-cab-acoes {
    flex-basis: 100%;
  }
}

.app-campo-opcoes {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  min-width: 0;
}

.app-avatar-ia {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: var(--pri-bg);
  color: var(--pri);
  font-size: var(--fs-caption);
  font-weight: 800;
}

.app-pensando {
  color: var(--t3);
  font-style: italic;
}

.app-filtros {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
}

.app-filtros > :first-child {
  flex: 1 1 18rem;
  min-width: 0;
}

.app-graficos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr));
  gap: 1rem;
}

.app-grafico-largo {
  grid-column: 1 / -1;
}

.app-cadastro {
  display: grid;
  grid-template-columns: minmax(10rem, 16rem) minmax(12rem, 1fr) auto;
  align-items: end;
  gap: 0.75rem;
}

@media (max-width: 40rem) {
  .app-cadastro {
    grid-template-columns: 1fr;
  }
}

.app-situacao {
  display: grid;
  gap: 0.25rem;
  justify-items: start;
}

.app-situacao small {
  color: var(--t3);
  font-size: var(--fs-caption);
  overflow-wrap: anywhere;
}

.app-notas {
  margin: 0;
  padding-left: 1.25rem;
  display: grid;
  gap: 0.5rem;
  color: var(--t2);
}

.app-texto {
  margin: 0;
  color: var(--t2);
  line-height: 1.55;
}

.app-subtitulo {
  margin: 1rem 0 0.5rem;
  font-size: var(--fs-corpo);
  color: var(--t2);
}

.app-perguntas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.5rem;
}

.app-perguntas li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0;
  border-bottom: var(--hairline) solid var(--border);
  color: var(--t2);
}

.app-perguntas li:last-child {
  border-bottom: 0;
}

.app-descoberta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
  gap: 1rem;
  align-items: start;
}

.app-descoberta-texto {
  display: grid;
  gap: 0.75rem;
}

.app-fato {
  margin: 0;
  padding: 0.75rem;
  border-radius: var(--r-card);
  background: var(--surf-2);
  color: var(--t2);
  line-height: 1.55;
}

.app-hipotese {
  font-style: italic;
}

.app-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.app-fontes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
  gap: 1rem;
}

.app-dados {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.375rem 0.75rem;
  margin: 0;
  color: var(--t2);
}

.app-dados dt {
  color: var(--t3);
  font-size: var(--fs-caption);
}

.app-dados dd {
  margin: 0;
}

.app-exemplos {
  display: grid;
  gap: 0.5rem;
  justify-items: center;
}

.app-resposta-extra {
  display: grid;
  gap: 0.75rem;
}

.app-grafico-chat {
  min-width: min(100%, 30rem);
}
``````

`frontend/src/types/api.ts`:

``````ts
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

export interface SystemStatus {
  backend: { online: boolean; error: string | null };
  ollama: {
    online: boolean;
    chat_model: { name: string; installed: boolean; tools: boolean | null };
    error: string | null;
  };
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
``````

`frontend/src/utils/format.ts`:

``````ts
const NUMBER = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });

export function formatNumber(value: number | null | undefined, unit = ''): string {
  if (value === null || value === undefined) return '–';
  return NUMBER.format(value) + (unit ? ` ${unit}` : '');
}

/** "2024-12-14" → "14/12/2024", sem passar por fuso horário. */
export function formatIsoDate(iso: string | null | undefined): string {
  if (!iso) return '–';
  const [year, month, day] = iso.slice(0, 10).split('-');
  return `${day}/${month}/${year}`;
}

export const CROP_OPTIONS = [
  { valor: 'soja' as const, rotulo: 'Soja' },
  { valor: 'milho' as const, rotulo: 'Milho' },
];
``````

`frontend/tsconfig.json`:

``````json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vite/client"]
  },
  "include": ["src"]
}
``````

`frontend/vite.config.ts`:

``````ts
/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Em desenvolvimento (npm run dev), o Vite repassa /api para o backend.
// No Docker, quem faz isso é o nginx (nginx.conf).
export default defineConfig({
  plugins: [react()],
  resolve: { dedupe: ['react', 'react-dom'] },
  server: {
    proxy: {
      '/api': { target: process.env.VITE_API_PROXY ?? 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: { environment: 'node' },
});
``````

Por último, gere o `frontend/package-lock.json` sem exigir Node no computador. Rode na raiz do projeto, trocando
`<pasta frontend absoluta>` pelo caminho real (no Git Bash do Windows, prefixe o comando com `MSYS_NO_PATHCONV=1`):

```bash
docker run --rm -v "<pasta frontend absoluta>:/app" -w /app node:24-alpine sh -c "apk add --no-cache git > /dev/null && npm install --package-lock-only --no-audit --no-fund"
```

## Verificação

```bash
docker compose --profile test run --rm --build frontend-tests
./scripts/iniciar.sh                                        # no Windows: powershell -ExecutionPolicy Bypass -File scripts\iniciar.ps1
docker compose ps                                           # todos healthy; só o frontend com porta
curl -s http://localhost:<porta>/api/status                 # backend, ollama e banco online; modelo com ferramentas
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:<porta>/previsao   # 200
```

Use a porta de `docs/configuracao.md`. No Windows PowerShell, escreva `curl.exe`.

## Depois de executar

```bash
git add frontend
git commit -m "feat: cria o frontend com análises, previsão, chat, descobertas e alertas"
```

## Orientação ao terminar

> **Pronto:** a aplicação já abre em http://localhost:<porta>, mas ainda vou testar tudo. Continue sem fazer nada.
