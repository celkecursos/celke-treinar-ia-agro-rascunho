const NUMBER = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });

export function formatNumber(value: number | null | undefined, unit = ''): string {
  if (value === null || value === undefined) return '–';
  return NUMBER.format(value) + (unit ? ` ${unit}` : '');
}

/** "2024-12-14" → "14/12/2024", sem passar por fuso horário. */
export function formatIsoDate(iso: string | null | undefined): string {
  if (!iso) return '–';
  const [year, month, day] = iso.slice(0, 10).split('-');
  return `${day}/${month}/${year}`;
}

export const CROP_OPTIONS = [
  { valor: 'soja' as const, rotulo: 'Soja' },
  { valor: 'milho' as const, rotulo: 'Milho' },
];
