import type { Painting } from '../types';

export function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat('en-US').format(value ?? 0);
}

export function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function centralityValue(value: number, metric: string) {
  if (metric === 'weightedDegree') {
    return formatNumber(Math.round(value));
  }
  return value.toFixed(4);
}

export function paintingSearchText(painting: Painting) {
  return [
    painting.title,
    painting.artist,
    painting.year,
    painting.date,
    painting.nationality,
    painting.genre,
    painting.media,
    painting.motifs.join(' '),
  ]
    .join(' ')
    .toLowerCase();
}

export function pickDeterministic<T>(items: T[], salt: string) {
  if (!items.length) {
    return undefined;
  }
  let total = 0;
  for (let index = 0; index < salt.length; index += 1) {
    total += salt.charCodeAt(index) * (index + 1);
  }
  return items[total % items.length];
}

