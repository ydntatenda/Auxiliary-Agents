import { Bell, CheckCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  Notification,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/client";

type Props = {
  onOpenWorkflow: (workflowId: string) => void;
};

const POLL_MS = 30_000;

function timeAgo(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const seconds = Math.max(1, Math.round((Date.now() - then) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.round(hours / 24);
    return `${days}d ago`;
  } catch {
    return iso;
  }
}

export default function NotificationBell({ onOpenWorkflow }: Props) {
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const list = await getNotifications();
        if (alive) setItems(list);
      } catch {
        // Non-fatal; the next poll retries.
      }
    }
    void poll();
    const handle = window.setInterval(poll, POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(handle);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    function onClickAway(event: MouseEvent) {
      if (!wrapper.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onClickAway);
    return () => window.removeEventListener("mousedown", onClickAway);
  }, [open]);

  const unread = items.length;

  async function handleGo(notification: Notification) {
    try {
      await markNotificationRead(notification.id);
    } catch {
      // Non-fatal; we still navigate.
    }
    setItems((current) => current.filter((item) => item.id !== notification.id));
    setOpen(false);
    onOpenWorkflow(notification.workflow_id);
  }

  async function handleReadAll() {
    try {
      await markAllNotificationsRead();
    } catch {
      // Non-fatal; the next poll will reconcile.
    }
    setItems([]);
  }

  return (
    <div className="bell" ref={wrapper}>
      <button
        type="button"
        className={`bell-btn${unread > 0 ? " has-unread" : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-label={`Notifications${unread > 0 ? `, ${unread} unread` : ""}`}
      >
        <Bell size={16} />
        {unread > 0 && <span className="bell-dot" />}
      </button>
      {open && (
        <div className="bell-dropdown">
          <div className="bell-head">
            <span className="label-mono">{unread} unread</span>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-ghost btn-tight"
                onClick={handleReadAll}
              >
                <CheckCheck size={12} />
                Mark all read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <div className="bell-empty">No new notifications.</div>
          ) : (
            <ul className="bell-list">
              {items.map((item) => (
                <li key={item.id} className="bell-item">
                  <div className="bell-msg">{item.message}</div>
                  <div className="bell-foot">
                    <span className="label-mono">{timeAgo(item.created_at)}</span>
                    <button
                      type="button"
                      className="btn btn-ghost btn-tight"
                      onClick={() => handleGo(item)}
                    >
                      Go to workflow
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
