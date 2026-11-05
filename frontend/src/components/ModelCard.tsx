import { Alerta, Botao, CampoSelect, CampoTexto, Card, Escolha, Progresso, useToast } from '@celke/kole-react';
import { useState } from 'react';
import { ApiError, api } from '../services/api';
import type { OllamaLocation, OllamaServer, OllamaStatus } from '../types/api';

function modelLabel(m: OllamaServer['models'][number]): string {
  const details = [m.parameter_size, m.size_gb ? `${m.size_gb} GB` : null].filter(Boolean).join(' · ');
  return details ? `${m.name} (${details})` : m.name;
}

/**
 * Onde roda o modelo de linguagem (este computador ou a GPU externa) e qual modelo usar. Vale para o chat, as
 * descobertas, os alertas e a explicação da previsão, sem reiniciar nada. Também baixa modelos no Ollama escolhido.
 */
export function ModelCard({ ollama, onChange }: { ollama?: OllamaStatus; onChange: () => Promise<void> }) {
  const toast = useToast();
  const [draftLocation, setDraftLocation] = useState<OllamaLocation>();
  const [draftModel, setDraftModel] = useState<string | null>();
  const [pullName, setPullName] = useState('');
  const [busy, setBusy] = useState<'usar' | 'baixar'>();

  const location = draftLocation ?? ollama?.location ?? 'local';
  const server = ollama?.servers.find((s) => s.location === location);
  const external = ollama?.servers.find((s) => s.location === 'externo');
  const model = draftModel !== undefined ? draftModel : (server?.chat_model ?? null);
  const inUse = ollama?.location === location && ollama.chat_model.name === model;
  const pulling = server?.pull?.status === 'baixando';

  function chooseLocation(value: OllamaLocation) {
    setDraftLocation(value);
    setDraftModel(undefined);
  }

  async function use() {
    if (!model) return;
    setBusy('usar');
    try {
      await api.selectModel(location, model);
      toast.ok('Modelo trocado', `${model} (${server?.label.toLowerCase()}) em uso a partir da próxima pergunta.`);
      setDraftLocation(undefined);
      setDraftModel(undefined);
      await onChange();
    } catch (e) {
      toast.err('Não foi possível trocar o modelo', e instanceof ApiError ? e.message : undefined);
    } finally {
      setBusy(undefined);
    }
  }

  async function pull() {
    const name = pullName.trim();
    if (!name) return;
    setBusy('baixar');
    try {
      await api.pullModel(location, name);
      toast.info('Download iniciado', 'O andamento aparece aqui. Modelos grandes levam alguns minutos.');
      setPullName('');
      await onChange();
    } catch (e) {
      toast.err('Não foi possível baixar', e instanceof ApiError ? e.message : undefined);
    } finally {
      setBusy(undefined);
    }
  }

  return (
    <Card
      titulo="Modelo de IA"
      subtitulo={
        ollama
          ? `Em uso: ${ollama.chat_model.name}, ${ollama.servers.find((s) => s.location === ollama.location)?.label.toLowerCase()}`
          : 'Verificando'
      }
    >
      <div className="app-modelo">
        <Escolha<OllamaLocation>
          rotulo="Onde o modelo roda"
          opcoes={(ollama?.servers ?? []).map((s) => ({
            valor: s.location,
            rotulo: s.label,
            desabilitada: !s.configured,
          }))}
          valor={location}
          aoMudar={chooseLocation}
          dica={
            external && !external.configured
              ? 'Para usar a GPU externa, cadastre o servidor no card "GPU externa" abaixo.'
              : 'A GPU externa é cobrada por hora enquanto a instância estiver ligada.'
          }
        />

        {server && !server.online && server.configured && (
          <Alerta severidade="err" titulo={`${server.label}: desconectado`} mensagem={server.error ?? undefined} />
        )}

        {/* As dicas ficam fora da linha: dentro do campo, empurram o botão para baixo da caixa. */}
        <div>
          <div className="app-filtros">
            <CampoSelect<string>
              rotulo="Modelo"
              opcoes={(server?.models ?? []).map((m) => ({
                valor: m.name,
                rotulo: modelLabel(m),
              }))}
              valor={model}
              aoMudar={(v) => setDraftModel(v)}
              placeholder={server?.online ? 'Escolha um modelo instalado' : 'Ollama indisponível'}
              disabled={!server?.online}
              comBusca
            />
            <Botao
              rotulo={inUse ? 'Em uso' : 'Usar este modelo'}
              icone="check"
              carregando={busy === 'usar'}
              disabled={inUse || !model || !server?.online || busy !== undefined}
              onClick={() => void use()}
            />
          </div>
          <p className="app-modelo-passo">
            Modelo maior responde melhor, mas pede mais memória: na CPU, até 8B; GPU de 12 GB, 14B; GPU externa de 24 GB
            ou mais, 32B.
          </p>
        </div>

        <div>
          <div className="app-filtros">
            <CampoTexto
              rotulo={`Baixar modelo ${location === 'externo' ? 'no servidor da GPU' : 'neste computador'}`}
              valor={pullName}
              aoMudar={setPullName}
              placeholder="qwen3:14b"
              disabled={!server?.online || pulling}
            />
            <Botao
              rotulo="Baixar"
              icone="download"
              aparencia="contorno"
              carregando={busy === 'baixar' || pulling}
              disabled={!pullName.trim() || !server?.online || pulling || busy !== undefined}
              onClick={() => void pull()}
            />
          </div>
          <p className="app-modelo-passo">
            Nome como no site do Ollama (ollama.com/library). O chat precisa de um modelo com a etiqueta tools.
          </p>
        </div>

        {server?.pull?.status === 'baixando' && (
          <div>
            <Progresso
              valor={server.pull.percent ?? 0}
              rotulo={`Download do modelo ${server.pull.model}`}
              etiqueta={server.pull.model}
              mostrarValor="fim"
              aparencia="listrado"
              animado
            />
            <p className="app-modelo-passo">{server.pull.message}</p>
          </div>
        )}
        {server?.pull?.status === 'concluido' && (
          <Alerta
            severidade="ok"
            titulo={`${server.pull.model} baixado`}
            mensagem='Escolha o modelo na lista e clique em "Usar este modelo".'
          />
        )}
        {server?.pull?.status === 'erro' && (
          <Alerta
            severidade="err"
            titulo={`Erro ao baixar ${server.pull.model}`}
            mensagem={server.pull.message ?? undefined}
          />
        )}
      </div>
    </Card>
  );
}
