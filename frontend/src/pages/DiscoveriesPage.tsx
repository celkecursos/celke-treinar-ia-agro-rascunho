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
