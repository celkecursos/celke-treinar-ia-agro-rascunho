import type { ChartSpec } from '../types/api';

/** `eixo_y_direito` → `eixoYDireito`: as opções do backend usam os mesmos nomes das props do Kole, em snake_case. */
export function camelKey(key: string): string {
  return key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

/** Props do componente do Kole a partir da especificação do backend (sem o `tipo`). */
export function chartProps(spec: ChartSpec): Record<string, unknown> {
  const props: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(spec)) {
    if (key === 'tipo' || value === null || value === undefined) continue;
    props[camelKey(key)] = value;
  }
  return props;
}
