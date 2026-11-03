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
