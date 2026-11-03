import { describe, expect, it } from 'vitest';
import { camelKey, chartProps } from './chartProps';

describe('chartProps', () => {
  it('troca snake_case pelos nomes das props do Kole', () => {
    expect(camelKey('eixo_y_direito')).toBe('eixoYDireito');
    expect(camelKey('chave_destaque')).toBe('chaveDestaque');
    expect(camelKey('titulo')).toBe('titulo');
  });

  it('tira o tipo e os valores vazios', () => {
    const props = chartProps({
      tipo: 'dispersao',
      titulo: 'Chuva × rendimento',
      chave_x: 'x',
      eixo_x: { rotulo: 'Chuva', unidade: 'mm' },
      nota: null,
    });
    expect(props).toEqual({ titulo: 'Chuva × rendimento', chaveX: 'x', eixoX: { rotulo: 'Chuva', unidade: 'mm' } });
  });
});
