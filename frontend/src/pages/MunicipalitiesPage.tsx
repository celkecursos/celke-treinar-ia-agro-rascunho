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
