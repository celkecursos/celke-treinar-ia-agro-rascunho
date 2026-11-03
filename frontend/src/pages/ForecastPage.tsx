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
