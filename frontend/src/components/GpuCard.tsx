import {
  Alerta,
  Botao,
  CampoInteiro,
  CampoSenha,
  CampoTexto,
  Card,
  Status,
  useConfirmacao,
  useToast,
} from '@celke/kole-react';
import { useState } from 'react';
import { ApiError, api } from '../services/api';
import type { GpuStatus } from '../types/api';

type Severidade = 'ok' | 'info' | 'warn' | 'err' | 'neutral';

const STATE: Record<GpuStatus['state'], { rotulo: string; severidade: Severidade }> = {
  nao_configurado: { rotulo: 'Não cadastrada', severidade: 'neutral' },
  desconectado: { rotulo: 'Desconectada', severidade: 'neutral' },
  conectando: { rotulo: 'Conectando', severidade: 'info' },
  conectado: { rotulo: 'Conectada', severidade: 'ok' },
  erro: { rotulo: 'Erro', severidade: 'err' },
};

/**
 * Servidor da GPU externa, todo pelo painel: endereço, chave SSH gerada pelo backend (só a pública aparece aqui),
 * instalação da chave com a senha do servidor e o túnel SSH, que o backend abre e mantém.
 */
export function GpuCard({ gpu, onChange }: { gpu?: GpuStatus; onChange: () => Promise<void> }) {
  const toast = useToast();
  const confirmar = useConfirmacao();
  const [host, setHost] = useState<string>();
  const [port, setPort] = useState<number | null>();
  const [user, setUser] = useState<string>();
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState<string>();

  const hostValue = host ?? gpu?.host ?? '';
  const portValue = port !== undefined ? port : (gpu?.port ?? 22);
  const userValue = user ?? gpu?.user ?? 'root';
  const changed = hostValue !== (gpu?.host ?? '') || portValue !== gpu?.port || userValue !== gpu?.user;

  async function run(action: string, call: () => Promise<unknown>, success?: string) {
    setBusy(action);
    try {
      await call();
      if (success) toast.ok(success);
      await onChange();
      return true;
    } catch (e) {
      toast.err('Não foi possível concluir', e instanceof ApiError ? e.message : undefined);
      return false;
    } finally {
      setBusy(undefined);
    }
  }

  async function save() {
    const ok = await run('salvar', () => api.saveGpu(hostValue.trim(), portValue ?? 22, userValue.trim()));
    if (ok) {
      setHost(undefined);
      setPort(undefined);
      setUser(undefined);
    }
  }

  async function installKey() {
    const ok = await run('chave', () => api.installGpuKey(password), 'Chave instalada no servidor');
    if (ok) setPassword('');
  }

  async function remove() {
    const ok = await confirmar.remover({
      titulo: 'Remover a GPU externa?',
      mensagem:
        'O túnel é fechado e o endereço é apagado. Se ela estava em uso, o modelo volta para este computador. ' +
        'A instância continua no provedor: desligue ou apague lá para parar a cobrança.',
    });
    if (ok) await run('remover', api.removeGpu, 'GPU externa removida');
  }

  async function copyKey() {
    try {
      await navigator.clipboard.writeText(gpu?.public_key ?? '');
      toast.ok('Chave pública copiada');
    } catch {
      toast.err('Não foi possível copiar', 'Selecione a chave e copie com Ctrl+C.');
    }
  }

  const state = gpu ? STATE[gpu.state] : undefined;
  const connected = gpu?.state === 'conectado';
  const active = gpu?.state === 'conectado' || gpu?.state === 'conectando';

  return (
    <Card
      titulo="GPU externa"
      subtitulo="Ollama num servidor alugado por hora (ex.: GPU da Hostinger com o app Ollama), pelo túnel SSH do backend"
      ferramentas={state && <Status {...state} />}
    >
      <div className="app-modelo">
        {/* As dicas ficam fora da linha: dentro do campo, desalinham os campos e o botão. */}
        <div>
          <div className="app-filtros">
            <CampoTexto rotulo="Endereço do servidor" valor={hostValue} aoMudar={setHost} placeholder="203.0.113.10" />
            <CampoInteiro rotulo="Porta SSH" valor={portValue} aoMudar={setPort} className="app-campo-curto" />
            <CampoTexto rotulo="Usuário" valor={userValue} aoMudar={setUser} className="app-campo-curto" />
            <Botao
              rotulo={gpu?.configured ? 'Salvar e conectar' : 'Cadastrar e conectar'}
              icone="link"
              carregando={busy === 'salvar'}
              disabled={!hostValue.trim() || !userValue.trim() || busy !== undefined || (gpu?.configured && !changed)}
              onClick={() => void save()}
            />
          </div>
          <p className="app-modelo-passo">Endereço: o IP ou o nome que o painel do provedor mostra.</p>
        </div>

        {gpu?.configured && gpu.message && (
          <Alerta
            severidade={gpu.state === 'erro' ? 'err' : connected ? 'ok' : 'info'}
            titulo={state?.rotulo ?? ''}
            mensagem={gpu.message}
          />
        )}
        {gpu?.host_key_mismatch && (
          <div>
            <Botao
              rotulo="Aceitar a chave nova do servidor"
              icone="key"
              aparencia="contorno"
              carregando={busy === 'aceitar'}
              disabled={busy !== undefined}
              onClick={() => void run('aceitar', api.acceptGpuHostKey)}
            />
          </div>
        )}

        <div>
          <p className="app-modelo-passo">
            Chave pública desta aplicação. Cadastre no painel do provedor (chaves SSH) antes de criar a instância, ou
            instale abaixo com a senha do servidor. A chave privada fica só no volume do backend.
          </p>
          <div className="app-chave">
            <code>{gpu?.public_key ?? '…'}</code>
            <Botao rotulo="Copiar" icone="copy" tamanho="pequeno" aparencia="texto" onClick={() => void copyKey()} />
          </div>
          {gpu?.host_key_fingerprint && (
            <p className="app-modelo-passo">Chave do servidor aceita: {gpu.host_key_fingerprint}</p>
          )}
        </div>

        {gpu?.configured && !connected && (
          <div>
            <div className="app-filtros">
              <CampoSenha
                rotulo={`Senha de ${gpu.user} no servidor`}
                valor={password}
                aoMudar={setPassword}
                autoComplete="off"
              />
              <Botao
                rotulo="Instalar a chave"
                icone="key"
                aparencia="contorno"
                carregando={busy === 'chave'}
                disabled={!password || busy !== undefined}
                onClick={() => void installKey()}
              />
            </div>
            <p className="app-modelo-passo">A senha é usada uma vez para instalar a chave e não fica guardada.</p>
          </div>
        )}

        {gpu?.configured && (
          <div className="app-acoes">
            {active ? (
              <Botao
                rotulo="Desconectar"
                icone="log-out"
                aparencia="contorno"
                carregando={busy === 'desconectar'}
                disabled={busy !== undefined}
                onClick={() => void run('desconectar', api.disconnectGpu)}
              />
            ) : (
              <Botao
                rotulo="Conectar"
                icone="link"
                carregando={busy === 'conectar'}
                disabled={busy !== undefined}
                onClick={() => void run('conectar', api.connectGpu)}
              />
            )}
            <Botao
              rotulo="Remover servidor"
              icone="trash-2"
              aparencia="texto"
              disabled={busy !== undefined}
              onClick={() => void remove()}
            />
          </div>
        )}
      </div>
    </Card>
  );
}
