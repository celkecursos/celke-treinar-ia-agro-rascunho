import { describe, expect, it } from 'vitest';
import { parseSseBlock, readSse } from './sse';

function stream(parts: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      parts.forEach((p) => controller.enqueue(encoder.encode(p)));
      controller.close();
    },
  });
}

describe('parseSseBlock', () => {
  it('lê os eventos das ferramentas e do gráfico', () => {
    expect(parseSseBlock('event: tool_call\ndata: {"name":"consultar_chuva","arguments":{"municipio":"Rio Verde"}}')).toEqual({
      type: 'tool_call',
      name: 'consultar_chuva',
      arguments: { municipio: 'Rio Verde' },
    });
    const result = parseSseBlock('event: tool_result\ndata: {"name":"x","ok":true,"summary":"ok","source":null,"arguments":{}}');
    expect(result).toMatchObject({ type: 'tool_result', result: { name: 'x', ok: true } });
    expect(parseSseBlock('event: chart\ndata: {"tipo":"linha","titulo":"T"}')).toEqual({
      type: 'chart',
      chart: { tipo: 'linha', titulo: 'T' },
    });
  });

  it('lê erro e ignora evento desconhecido', () => {
    expect(parseSseBlock('event: error\ndata: {"codigo":"x","mensagem":"Falhou"}')).toEqual({
      type: 'error',
      code: 'x',
      message: 'Falhou',
    });
    expect(parseSseBlock('event: outro\ndata: {}')).toBeNull();
  });
});

describe('readSse', () => {
  it('junta blocos partidos entre pedaços', async () => {
    const events = [];
    for await (const e of readSse(stream(['event: token\ndata: {"te', 'xt":"Olá"}\n\nevent: done\ndata: {}\n\n']))) {
      events.push(e);
    }
    expect(events).toEqual([{ type: 'token', text: 'Olá' }, { type: 'done' }]);
  });
});
