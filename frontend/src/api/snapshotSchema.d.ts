declare module './snapshotSchema.js' {
  export class PublicApiError extends Error { kind: string; }
  export function optionalText(v: any): any;
  export function optionalNumber(v: any): any;
  export function parseRows(data: any): any;
  export function parseAggregate(raw: any, coverage: string): any;
  export function validateSnapshot(raw: any): any;
  export function parseSnapshot(raw: any): any;
  export function parseStaticSnapshot(raw: any): any;
  export function loadBundledSnapshot(): Promise<any>;
  export function loadStaticSnapshot(): Promise<any>;
}
