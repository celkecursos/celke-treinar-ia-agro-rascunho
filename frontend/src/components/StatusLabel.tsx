import { Status } from '@celke/kole-react';
import type { CollectionRun, Municipality } from '../types/api';

type Severidade = 'ok' | 'info' | 'warn' | 'err' | 'neutral';

const MUNICIPALITY: Record<Municipality['status'], { rotulo: string; severidade: Severidade }> = {
  coletando: { rotulo: 'Coletando', severidade: 'info' },
  pronto: { rotulo: 'Pronto', severidade: 'ok' },
  erro: { rotulo: 'Erro', severidade: 'err' },
};

const RUN: Record<CollectionRun['status'], { rotulo: string; severidade: Severidade }> = {
  executando: { rotulo: 'Executando', severidade: 'info' },
  concluida: { rotulo: 'Concluída', severidade: 'ok' },
  sem_novidade: { rotulo: 'Sem novidade', severidade: 'neutral' },
  erro: { rotulo: 'Erro', severidade: 'err' },
};

export const TRIGGER_LABEL: Record<CollectionRun['trigger'], string> = {
  agendada: 'Agendada',
  botao: 'Botão',
  cadastro: 'Cadastro',
};

export function MunicipalityStatusLabel({ status }: { status: Municipality['status'] }) {
  return <Status {...MUNICIPALITY[status]} />;
}

export function RunStatusLabel({ status }: { status: CollectionRun['status'] }) {
  return <Status {...RUN[status]} />;
}

export function OnlineStatus({ online, rotulo }: { online: boolean; rotulo?: string }) {
  return <Status rotulo={rotulo ?? (online ? 'Conectado' : 'Desconectado')} severidade={online ? 'ok' : 'err'} />;
}
