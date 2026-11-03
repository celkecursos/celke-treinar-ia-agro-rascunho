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
        <Alerta
          severidade="err"
          titulo={s.ollama.location === 'externo' ? 'GPU externa desconectada' : 'Ollama desconectado'}
          mensagem={s.ollama.error ?? 'Veja: docker compose logs ollama'}
        />
      )}
      {s?.ollama.online && !s.ollama.chat_model.installed && (
        <Alerta
          severidade="warn"
          titulo="Modelo ainda não instalado"
          mensagem={
            s.ollama.location === 'externo'
              ? `Baixe o modelo no servidor da GPU: ollama pull ${s.ollama.chat_model.name}`
              : 'O download inicial pode levar alguns minutos. Acompanhe com: docker compose logs -f ollama-init'
          }
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
              <span>
                Ollama{' '}
                {s && (s.ollama.location === 'externo' ? '(GPU externa, pelo túnel SSH)' : '(neste computador)')}
              </span>
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
