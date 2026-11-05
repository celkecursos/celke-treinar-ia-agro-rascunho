import type { ChartSpec, ChatEvent, ToolCallRecord } from '../types/api';

/** Converte um bloco `event: x\ndata: {...}` num evento do chat (ou `null` se não reconhecido). */
export function parseSseBlock(block: string): ChatEvent | null {
  let event = 'message';
  const data: string[] = [];
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  const payload = JSON.parse(data.join('\n'));
  switch (event) {
    case 'conversation':
      return { type: 'conversation', id: String(payload.id), title: String(payload.title ?? '') };
    case 'thinking':
      return { type: 'thinking' };
    case 'tool_call':
      return { type: 'tool_call', name: String(payload.name), arguments: payload.arguments ?? {} };
    case 'tool_result':
      return { type: 'tool_result', result: payload as ToolCallRecord };
    case 'chart':
      return { type: 'chart', chart: payload as ChartSpec };
    case 'token':
      return { type: 'token', text: String(payload.text ?? '') };
    case 'discard':
      return { type: 'discard' };
    case 'done':
      return { type: 'done' };
    case 'error':
      return { type: 'error', code: String(payload.codigo ?? 'erro'), message: String(payload.mensagem ?? 'Erro') };
    default:
      return null;
  }
}

/**
 * Lê um stream SSE em pedaços. Os blocos podem chegar partidos entre dois
 * pedaços; o que sobra fica guardado até o próximo.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n');
      let end = buffer.indexOf('\n\n');
      while (end !== -1) {
        const parsed = parseSseBlock(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        if (parsed) yield parsed;
        end = buffer.indexOf('\n\n');
      }
      if (done) break;
    }
    if (buffer.trim()) {
      const parsed = parseSseBlock(buffer);
      if (parsed) yield parsed;
    }
  } finally {
    reader.releaseLock();
  }
}
