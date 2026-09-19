"""What the relay hands the post-call pipeline when a call ends (Phase 8, D14).

A plain in-memory holder that `run_call` fills as the call runs. **Agent speech only**: caller speech
is never transcribed in this project, so this never holds it (D14). Every method is synchronous and
does nothing but append or assign -- the relay cannot be made to wait on it, which is what exit
criterion 4 (the pipeline never affects B4 or B5) rests on. Nothing here is persisted; the pipeline
that reads it redacts before writing anywhere (ADR-007).
"""


class CallCapture:
    def __init__(self):
        self.agent_turns = []
        self._current = []
        self.correlation_id = None
        self.end_reason = None
        self.auth_state = None
        self.turn_count = None
        self.duration_ms = None

    def add_delta(self, text):
        self._current.append(text)

    def end_turn(self):
        """A response finished. A response with no words (a tool-call-only one) adds no entry."""
        if self._current:
            self.agent_turns.append("".join(self._current))
            self._current = []

    def finish(self, correlation_id, end_reason, auth_state, turn_count, duration_ms):
        """The call is over. Words still in flight (the caller hung up mid-sentence) are kept."""
        self.end_turn()
        self.correlation_id = correlation_id
        self.end_reason = end_reason
        self.auth_state = auth_state
        self.turn_count = turn_count
        self.duration_ms = duration_ms
