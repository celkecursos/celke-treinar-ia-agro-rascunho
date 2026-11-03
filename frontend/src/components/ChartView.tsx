import {
  GraficoBarras,
  GraficoCombinado,
  GraficoDispersao,
  GraficoLinha,
  MapaCalor,
  type GraficoBarrasProps,
  type GraficoCombinadoProps,
  type GraficoDispersaoProps,
  type GraficoLinhaProps,
  type MapaCalorProps,
} from '@celke/kole-react';
import type { ChartSpec } from '../types/api';
import { chartProps } from './chartProps';

/** Desenha com o Kole o gráfico que o backend montou (as contas já vêm feitas). */
export function ChartView({ spec, altura }: { spec: ChartSpec; altura?: number }) {
  const props = { ...chartProps(spec), altura };
  switch (spec.tipo) {
    case 'linha':
      return <GraficoLinha {...(props as unknown as GraficoLinhaProps)} />;
    case 'barras':
      return <GraficoBarras {...(props as unknown as GraficoBarrasProps)} />;
    case 'combinado':
      return <GraficoCombinado {...(props as unknown as GraficoCombinadoProps)} />;
    case 'dispersao':
      return <GraficoDispersao {...(props as unknown as GraficoDispersaoProps)} />;
    case 'mapa_calor':
      return <MapaCalor {...(props as unknown as MapaCalorProps)} />;
    default:
      return null;
  }
}
