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
