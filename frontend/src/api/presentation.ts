import type { Language } from '../i18n/translations';
export const riskLabels = {
  it: {major: 'Rischio elevato', moderate: 'Rischio moderato', regular: 'Rischio contenuto'},
  en: {major: 'High risk', moderate: 'Moderate risk', regular: 'Low risk'},
};
export function riskClass(p: number, threshold = 0.35): 'major' | 'moderate' | 'regular' {
  return p >= threshold ? 'major' : p >= 0.20 ? 'moderate' : 'regular';
}
export function riskLabel(p: number, threshold: number, language: Language): string {
  return riskLabels[language][riskClass(p, threshold)];
}
export function observedDelay(seconds: number | null | undefined, language: Language): string {
  if (seconds == null || !Number.isFinite(seconds)) return language === 'it' ? 'Non disponibile' : 'Unavailable';
  const whole = Math.round(Math.abs(seconds));
  return `${seconds < 0 ? '-' : '+'}${Math.floor(whole / 60)}m ${whole % 60}s`;
}
