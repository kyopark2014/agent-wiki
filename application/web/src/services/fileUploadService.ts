import { api } from "../api";

/** Normalize any thrown value into an Error with a safe, user-facing message. */
function toUploadError(context: string, cause: unknown): Error {
  // Never forward raw exception text (stack fragments, SDK internals) to the UI.
  const error = new Error(context);
  if (cause instanceof Error) {
    (error as Error & { cause?: unknown }).cause = cause;
  }
  return error;
}

/** Service layer for file uploads — keeps hooks free of direct API calls. */
export const fileUploadService = {
  async uploadImage(file: File): Promise<{ url: string; file_name: string }> {
    try {
      return await api.uploadFile(file);
    } catch (cause) {
      throw toUploadError("Image upload failed", cause);
    }
  },

  async uploadToRag(file: File): Promise<{ message: string }> {
    try {
      return await api.uploadToRag(file);
    } catch (cause) {
      throw toUploadError("RAG upload failed", cause);
    }
  },

  async uploadToWiki(files: File[]): Promise<{ message: string }> {
    try {
      const result = await api.uploadWikiRawFiles(files);
      const names = (result.saved || []).map((s) => s.name).join(", ");
      let message =
        `문서 ${result.count}개를 wiki/raw에 업로드했습니다` +
        (names ? ` (${names})` : "") +
        ".";
      try {
        const sync = await api.syncWiki(false);
        if (sync.status === "error") {
          message += ` Wiki Sync 실패: ${sync.error || "알 수 없는 오류"}`;
        } else if (sync.status === "unchanged") {
          message += " 변경된 파일이 없습니다.";
        } else {
          message += " Wiki Sync를 시작합니다.";
        }
      } catch (syncErr) {
        const detail =
          syncErr instanceof Error ? syncErr.message : String(syncErr);
        message += ` Wiki Sync 시작 실패: ${detail}`;
      }
      return { message };
    } catch (cause) {
      throw toUploadError("Wiki upload failed", cause);
    }
  },
};
