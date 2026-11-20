"""
Permission-Gated In-Game Chat System.
Security Invariant:
- AI is NEVER allowed to send messages directly into the game chat without explicit user approval.
- Draft messages are shown on the Overlay and Web Dashboard.
- Only when user clicks 'Approve' or says 'Send this to team chat' will it safely type the text.
"""

import sys
import time
import threading
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class ChatDraft:
    draft_id: str
    target_channel: str # 'team' or 'all'
    content: str
    created_at: float = field(default_factory=time.time)
    status: str = "PENDING" # PENDING, APPROVED, REJECTED, SENT


class PermissionGatedChatManager:
    """Manages chat message drafts with human-in-the-loop authorization."""

    def __init__(self):
        self.pending_drafts: Dict[str, ChatDraft] = {}
        self.current_active_draft: Optional[ChatDraft] = None
        self._lock = threading.Lock()
        self.on_draft_created_cbs = []
        self.on_draft_status_changed_cbs = []

    def register_draft_created(self, cb: Callable[[ChatDraft], None]):
        self.on_draft_created_cbs.append(cb)

    def register_status_changed(self, cb: Callable[[ChatDraft], None]):
        self.on_draft_status_changed_cbs.append(cb)

    def propose_chat(self, content: str, target_channel: str = "team") -> ChatDraft:
        """AI proposes a message to send. Status starts strictly as PENDING."""
        import uuid
        draft = ChatDraft(
            draft_id=str(uuid.uuid4())[:8],
            target_channel=target_channel,
            content=content.strip(),
            status="PENDING"
        )
        with self._lock:
            self.pending_drafts[draft.draft_id] = draft
            self.current_active_draft = draft

        print(f"[ChatGate] Draft proposed [{draft.draft_id}]: '{draft.content}' -> Awaiting user permission")
        for cb in self.on_draft_created_cbs:
            try:
                cb(draft)
            except Exception as e:
                print(f"[ChatGate] Callback error: {e}")
        return draft

    def approve_and_send(self, draft_id: str) -> bool:
        """User explicitly authorizes sending this message."""
        draft = None
        with self._lock:
            draft = self.pending_drafts.get(draft_id)
            if not draft or draft.status != "PENDING":
                return False
            draft.status = "APPROVED"

        print(f"[ChatGate] User APPROVED draft [{draft_id}]. Dispatching to in-game chat...")
        success = self._send_to_game(draft)
        with self._lock:
            draft.status = "SENT" if success else "FAILED"
            if self.current_active_draft and self.current_active_draft.draft_id == draft_id:
                self.current_active_draft = None

        for cb in self.on_draft_status_changed_cbs:
            try:
                cb(draft)
            except Exception as e:
                print(f"[ChatGate] Callback error: {e}")
        return success

    def reject(self, draft_id: str) -> bool:
        """User rejects the draft."""
        with self._lock:
            draft = self.pending_drafts.get(draft_id)
            if not draft:
                return False
            draft.status = "REJECTED"
            if self.current_active_draft and self.current_active_draft.draft_id == draft_id:
                self.current_active_draft = None

        print(f"[ChatGate] Draft [{draft_id}] REJECTED by user.")
        for cb in self.on_draft_status_changed_cbs:
            try:
                cb(draft)
            except Exception as e:
                print(f"[ChatGate] Callback error: {e}")
        return True

    def _send_to_game(self, draft: ChatDraft) -> bool:
        """Simulates keypress sequence safely on Windows.
        1. Press Enter (opens team chat) or Shift+Enter (all chat)
        2. Types / pastes content
        3. Press Enter to dispatch
        """
        if sys.platform != "win32":
            print(f"[ChatGate Simulation] (Non-Windows test) Sent: '{draft.content}' to {draft.target_channel} chat.")
            return True

        try:
            import pyautogui
            # Try to copy to clipboard for non-ASCII (Vietnamese / special chars) support
            import pyperclip
            pyperclip.copy(draft.content)

            # Open chat
            if draft.target_channel.lower() == "all":
                pyautogui.hotkey("shift", "enter")
            else:
                pyautogui.press("enter")

            time.sleep(0.08)
            # Paste text
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.08)
            # Send
            pyautogui.press("enter")
            return True
        except Exception as e:
            print(f"[ChatGate] Error sending keystrokes: {e}")
            return False


# Global instance
chat_manager = PermissionGatedChatManager()
