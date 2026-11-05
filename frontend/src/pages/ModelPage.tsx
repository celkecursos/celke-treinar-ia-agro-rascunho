import { Alerta, Botao, CabecalhoPagina } from '@celke/kole-react';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { GpuCard } from '../components/GpuCard';
import { ModelCard } from '../components/ModelCard';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';

/** Onde o modelo de linguagem roda (este computador ou a GPU externa), qual modelo usar e o servidor da GPU externa. */
export function ModelPage() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  // durante o download de um modelo ou a conexão com a GPU externa, a tela se atualiza a cada 2 segundos
  const status = usePolling(api.status, busy ? 2000 : 10000);
  const s = status.data;
  const isBusy =
    !!s?.ollama.servers.some((server) => server.pull?.status === 'baixando') || s?.gpu.state === 'conectando';
  if (isBusy !== busy) setBusy(isBusy);

  return (
    <div className="app-pagina">
      <CabecalhoPagina
        titulo="Modelo de IA"
        icone="cpu"
        acoes={
          <Botao
            rotulo="Status e coletas"
            icone="arrow-left"
            aparencia="contorno"
            tamanho="pequeno"
            onClick={() => navigate('/status')}
          />
        }
      >
        Onde o modelo de linguagem roda e qual modelo usar no chat, nas descobertas, nos alertas e na explicação da
        previsão. A troca vale na hora, sem reiniciar nada.
      </CabecalhoPagina>

      {status.error && <Alerta severidade="err" titulo="Backend indisponível" mensagem={status.error.message} />}
      <ModelCard ollama={s?.ollama} onChange={status.reload} />
      <GpuCard gpu={s?.gpu} onChange={status.reload} />
    </div>
  );
}
