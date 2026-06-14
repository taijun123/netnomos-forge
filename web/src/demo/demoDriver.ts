// 一键演示的命令式编排原语：节奏延迟、可中止 delay、Gate(把"等一个 WorkflowLog 跑完"变可 await)、
// 自动上传。网络/财务正式演示必须走真实后端，不再回落本地 mock 结果。
import { uploadDataSource } from "../lib/apiClient";
import type { UploadedDataSource } from "../components/DataSourceUploadBox";
import { makeDemoFile, type DemoScenario } from "./demoAssets";

// 各步停留节奏（毫秒），像真人在操作；一处调参
export const DEMO_PACING = {
  stepBeat: 850,
  afterUpload: 1700,
  afterLearn: 2200,
  beforeValidate: 1400,
  afterValidate: 2200,
  beforeDual: 1500,
  afterDual: 2400,
  reportDwell: 3500,
  gateTimeout: 120000,
  networkGateTimeout: 300000,
  networkReportGateTimeout: 480000,
};

export type Delay = (ms: number) => Promise<void>;

// AbortController 守护的 delay：abort 时 reject(AbortError)，供脚本 catch 静默退出
export function makeAbortableDelay(signal: AbortSignal): Delay {
  return (ms: number) =>
    new Promise<void>((resolve, reject) => {
      if (signal.aborted) return reject(new DOMException("aborted", "AbortError"));
      const t = setTimeout(resolve, ms);
      signal.addEventListener(
        "abort",
        () => {
          clearTimeout(t);
          reject(new DOMException("aborted", "AbortError"));
        },
        { once: true }
      );
    });
}

export interface Gate<T> {
  promise: Promise<T>;
  resolve: (v: T) => void;
  reject: (e: unknown) => void;
}

export function createGate<T>(): Gate<T> {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((rs, rj) => {
    resolve = rs;
    reject = rj;
  });
  return { promise, resolve, reject };
}

// 等 gate（一个 WorkflowLog 完成 onResult resolve）；超时/失败即抛错，不能用假结果顶替。
export async function awaitGate<T>(
  gate: Gate<T>,
  delay: Delay,
  label: string,
  ms: number = DEMO_PACING.gateTimeout
): Promise<T> {
  return Promise.race<T>([
    gate.promise,
    delay(ms).then<T>(() => {
      throw new Error(`${label} did not return a real backend result within ${Math.round(ms / 1000)}s`);
    }),
  ]);
}

// 模拟真人上传：构造内联 demo File，走与手动上传完全相同的 apiClient.uploadDataSource。
// 上传失败必须暴露给页面，不能回落 mock dataSource。
export async function autoUpload(scenario: DemoScenario): Promise<UploadedDataSource> {
  const apiScenario = scenario === "network" ? "network_cidds" : "finance_v1";
  const file = makeDemoFile(scenario);
  const r = await uploadDataSource(apiScenario, file, `${scenario}-demo-auto`);
  return { ...r, filename: r.filename || file.name, size: r.size ?? file.size };
}
