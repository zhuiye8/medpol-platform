import { useState, useCallback, useRef } from "react";

interface FileUploadProps {
  accept?: string;
  maxSizeMB?: number;
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
  hint?: string;
}

export function FileUpload({
  accept = ".xlsx,.xls",
  maxSizeMB = 10,
  onUpload,
  disabled = false,
  hint,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const maxSizeBytes = maxSizeMB * 1024 * 1024;

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);

      // Validate file size
      if (file.size > maxSizeBytes) {
        setError(`文件过大，最大 ${maxSizeMB}MB`);
        return;
      }

      // Validate file type
      const validExtensions = accept.split(",").map((ext) => ext.trim().toLowerCase());
      const fileExt = "." + file.name.split(".").pop()?.toLowerCase();
      if (!validExtensions.includes(fileExt)) {
        setError(`不支持的文件格式，请上传 ${accept} 格式`);
        return;
      }

      setUploading(true);
      try {
        await onUpload(file);
      } catch (err) {
        setError((err as Error).message || "上传失败");
      } finally {
        setUploading(false);
      }
    },
    [accept, maxSizeBytes, maxSizeMB, onUpload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      if (disabled || uploading) return;

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [disabled, uploading, handleFile]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled && !uploading) {
        setIsDragging(true);
      }
    },
    [disabled, uploading]
  );

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
      // Reset input value to allow re-selecting the same file
      e.target.value = "";
    },
    [handleFile]
  );

  const handleClick = useCallback(() => {
    if (!disabled && !uploading) {
      fileInputRef.current?.click();
    }
  }, [disabled, uploading]);

  return (
    <div>
      <div
        className={`upload-zone ${isDragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        style={{
          border: "2px dashed #cbd5e1",
          borderRadius: 8,
          padding: "32px 24px",
          textAlign: "center",
          cursor: disabled || uploading ? "not-allowed" : "pointer",
          background: isDragging ? "#f0f9ff" : disabled ? "#f8fafc" : "#fff",
          transition: "all 0.2s ease",
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          style={{ display: "none" }}
          disabled={disabled || uploading}
        />
        <div style={{ fontSize: 36, marginBottom: 12, color: "#94a3b8" }}>
          {uploading ? "..." : "+"}
        </div>
        <div style={{ fontSize: 16, color: "#334155", marginBottom: 8 }}>
          {uploading ? "上传中..." : "点击或拖拽文件到此处"}
        </div>
        <div style={{ fontSize: 13, color: "#94a3b8" }}>
          {hint || `支持 ${accept} 格式，最大 ${maxSizeMB}MB`}
        </div>
      </div>
      {error && (
        <div style={{ color: "#dc2626", fontSize: 13, marginTop: 8 }}>
          {error}
        </div>
      )}
    </div>
  );
}
