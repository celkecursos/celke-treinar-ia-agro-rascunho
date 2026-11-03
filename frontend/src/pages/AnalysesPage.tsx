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
