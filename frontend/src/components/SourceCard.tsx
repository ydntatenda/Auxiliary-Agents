import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  FileText,
  Image,
  Loader2,
  MessageSquare,
  Mic,
  MonitorUp,
  Pencil,
  Plug,
  RefreshCw,
  Trash2,
  Type,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Source, SourceStatus } from "../api/client";

type Props = {
  source: Source;
  isFirst: boolean;
  isLast: boolean;
  canEdit: boolean;
  onRemove: () => void;
  onRetry: () => void;
  onLabelChange: (label: string) => void;
  onMove: (direction: "up" | "down") => void;
};

const READ_ONLY_TITLE =
  "Only the person who added this source, or the workflow owner, can change it.";

const MODALITY_ICON: Record<string, typeof Type> = {
  text: Type,
  voice: Mic,
  screen: MonitorUp,
  document: FileText,
  image: Image,
  chat: MessageSquare,
  connector: Plug,
};

const STATUS_COPY: Record<SourceStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

const PREVIEW_LIMIT = 120;

function modalityLabel(modality: string): string {
  return modality.charAt(0).toUpperCase() + modality.slice(1);
}

function displayLabel(source: Source): string {
  if (source.label && source.label.trim()) return source.label;
  return modalityLabel(source.modality);
}

function preview(text: string | null): string {
  if (!text) return "";
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length <= PREVIEW_LIMIT ? flat : flat.slice(0, PREVIEW_LIMIT).trimEnd() + "...";
}

export default function SourceCard({
  source,
  isFirst,
  isLast,
  canEdit,
  onRemove,
  onRetry,
  onLabelChange,
  onMove,
}: Props) {
  const Icon = MODALITY_ICON[source.modality] ?? Type;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(source.label ?? "");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const readOnlyTitle = canEdit ? undefined : READ_ONLY_TITLE;

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  useEffect(() => {
    setDraft(source.label ?? "");
  }, [source.label]);

  function commit() {
    const next = draft.trim();
    setEditing(false);
    if (next === (source.label ?? "")) return;
    onLabelChange(next);
  }

  function cancel() {
    setDraft(source.label ?? "");
    setEditing(false);
  }

  return (
    <div className={`source-card status-${source.status}`}>
      <div className="sc-order">
        <button
          type="button"
          className="sc-arrow"
          onClick={() => onMove("up")}
          disabled={isFirst || !canEdit}
          aria-label="Move source up"
          title={readOnlyTitle}
        >
          <ArrowUp size={12} />
        </button>
        <span className="sc-order-num">{source.order + 1}</span>
        <button
          type="button"
          className="sc-arrow"
          onClick={() => onMove("down")}
          disabled={isLast || !canEdit}
          aria-label="Move source down"
          title={readOnlyTitle}
        >
          <ArrowDown size={12} />
        </button>
      </div>

      <div className="sc-icon">
        <Icon size={16} />
      </div>

      <div className="sc-body">
        <div className="sc-head">
          {editing ? (
            <div className="sc-label-edit">
              <input
                ref={inputRef}
                className="sc-label-input"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") commit();
                  if (event.key === "Escape") cancel();
                }}
                onBlur={commit}
                placeholder={modalityLabel(source.modality)}
              />
              <button
                type="button"
                className="sc-iconbtn"
                onMouseDown={(event) => event.preventDefault()}
                onClick={commit}
                aria-label="Save label"
              >
                <Check size={12} />
              </button>
              <button
                type="button"
                className="sc-iconbtn"
                onMouseDown={(event) => event.preventDefault()}
                onClick={cancel}
                aria-label="Cancel"
              >
                <X size={12} />
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="sc-label"
              onClick={() => {
                if (canEdit) setEditing(true);
              }}
              disabled={!canEdit}
              title={canEdit ? "Click to rename" : readOnlyTitle}
            >
              <span>{displayLabel(source)}</span>
              {canEdit && <Pencil size={11} className="sc-pencil" />}
            </button>
          )}
          <span className="sc-modality">{modalityLabel(source.modality)}</span>
        </div>

        <div className="sc-foot">
          <StatusPill status={source.status} />
          {source.status === "ready" && source.assembled_text && (
            <span className="sc-preview">{preview(source.assembled_text)}</span>
          )}
          {source.status === "failed" && source.error && (
            <span className="sc-error">{source.error}</span>
          )}
        </div>
      </div>

      <div className="sc-actions">
        {source.status === "failed" && (
          <button
            type="button"
            className="sc-iconbtn"
            onClick={onRetry}
            aria-label="Retry source"
            title={canEdit ? "Retry ingestion" : readOnlyTitle}
            disabled={!canEdit}
          >
            <RefreshCw size={14} />
          </button>
        )}
        <button
          type="button"
          className="sc-iconbtn danger"
          onClick={onRemove}
          aria-label="Remove source"
          title={canEdit ? "Remove" : readOnlyTitle}
          disabled={!canEdit}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: SourceStatus }) {
  const Icon =
    status === "processing" ? Loader2 : status === "ready" ? ChevronDown : null;
  return (
    <span className={`sc-pill pill-${status}`}>
      {Icon && (
        <Icon
          size={10}
          className={status === "processing" ? "spin" : undefined}
        />
      )}
      {STATUS_COPY[status]}
    </span>
  );
}
