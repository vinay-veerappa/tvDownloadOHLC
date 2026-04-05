export type V3Meta = {
  symbol: string;
  asOf: string;
  freshnessMs: number;
  source: string;
  computeVersion: string;
  adapterVersion: string;
};

export type V3Envelope<T> = {
  success: boolean;
  data: T | null;
  meta: V3Meta;
  warnings: string[];
  error: string | null;
};

export type V3ModuleStub<TData extends object = Record<string, unknown>> = {
  implemented: boolean;
  module: string;
  symbol: string;
} & TData;
