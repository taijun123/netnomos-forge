import { useRef, useState, type ChangeEvent } from "react";
import { uploadDataSource, type DataSourceUploadResult } from "../lib/apiClient";
import type { Scenario } from "../types/api";

export interface UploadedDataSource extends DataSourceUploadResult {
  filename: string;
}

function formatBytes(value?: number): string {
  if (!value || value <= 0) return "size n/a";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function DataSourceUploadBox({
  scenario,
  title,
  description,
  accept,
  note,
  uploaded,
  onUploaded,
}: {
  scenario: Scenario;
  title: string;
  description: string;
  accept: string;
  note: string;
  uploaded: UploadedDataSource | null;
  onUploaded: (dataSource: UploadedDataSource) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const uploadStatus = uploading ? "uploading" : error ? "error" : uploaded ? "uploaded" : "idle";
  const uploadStatusText =
    uploadStatus === "uploading"
      ? `上传中${selectedFileName ? `：${selectedFileName}` : ""}`
      : uploadStatus === "uploaded"
        ? "已上传并登记"
        : uploadStatus === "error"
          ? "上传失败"
          : "等待选择文件";

  const chooseFile = () => {
    if (uploading) return;
    inputRef.current?.click();
  };

  const onFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    setSelectedFileName(file.name);
    setError(null);
    try {
      const result = await uploadDataSource(scenario, file, note);
      onUploaded({
        ...result,
        filename: result.filename || file.name,
        size: result.size ?? file.size,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="datasource-upload">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="visually-hidden"
        onChange={onFileChange}
      />
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <button type="button" className="btn btn-outline" disabled={uploading} onClick={chooseFile}>
        {uploading ? "上传中…" : uploaded ? "重新选择资料" : "选择并上传资料"}
      </button>
      <div className={`upload-status is-${uploadStatus}`}>
        <span>状态</span>
        <strong>{uploadStatusText}</strong>
      </div>
      {uploaded && (
        <div className="uploaded-file-pill">
          <span>{uploaded.filename}</span>
          <dl>
            <div>
              <dt>dataSourceId</dt>
              <dd>{uploaded.dataSourceId}</dd>
            </div>
            <div>
              <dt>文件大小</dt>
              <dd>{formatBytes(uploaded.size)}</dd>
            </div>
            {uploaded.path && (
              <div className="upload-path">
                <dt>保存路径</dt>
                <dd>{uploaded.path}</dd>
              </div>
            )}
          </dl>
        </div>
      )}
      {error && <div className="upload-error">{error}</div>}
    </div>
  );
}
