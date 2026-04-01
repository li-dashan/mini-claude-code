"""Terminal buddy system for mini-claude-code.

Each user is permanently assigned one companion, determined deterministically
from username + hostname so the same environment always gets the same buddy.
"""

from __future__ import annotations

import hashlib
import socket
from dataclasses import dataclass, field

from rich.panel import Panel


@dataclass
class BuddyState:
    """Compact terminal pet state."""

    mood: str = "idle"
    energy: int = 80
    trust: int = 50
    tool_calls: int = 0
    tool_errors: int = 0
    last_event: str = "Ready to help"


@dataclass
class BuddyProfile:
    """Visual and narrative identity for a buddy."""

    key: str
    name: str
    style: str
    trait: str
    story: str
    faces: dict[str, str]
    thinking_frames: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)  # speed/courage/curiosity/stamina/focus/luck 0-100


@dataclass
class BuddyCompanion:
    """A complete buddy unit with profile and mutable state."""

    profile: BuddyProfile
    state: BuddyState
    frame_index: int = 0


class TerminalBuddy:
    """A lightweight electronic buddy for terminal sessions."""

    def __init__(self) -> None:
        profiles = self._build_profiles()
        self._companions: dict[str, BuddyCompanion] = {
            profile.key: BuddyCompanion(profile=profile, state=BuddyState())
            for profile in profiles
        }
        self._order = [profile.key for profile in profiles]
        self._active_key = self._assign_buddy_key(profiles)

    @property
    def state(self) -> BuddyState:
        """State of the currently active buddy."""
        return self._active.state

    @property
    def _active(self) -> BuddyCompanion:
        return self._companions[self._active_key]

    @property
    def active_name(self) -> str:
        return self._active.profile.name

    def list_profiles(self) -> list[str]:
        """Short roster lines for buddy zone display."""
        lines = []
        for key in self._order:
            companion = self._companions[key]
            marker = "▶" if key == self._active_key else "·"
            lines.append(
                f"{marker} {companion.profile.name} [{companion.profile.style}]"
            )
        return lines

    def on_user_message(self, text: str) -> None:
        state = self._active.state
        state.energy = max(0, state.energy - 2)
        if "!" in text:
            state.mood = "excited"
        else:
            state.mood = "idle"
        state.last_event = "Listening"

    def on_thinking(self) -> None:
        companion = self._active
        companion.state.mood = "thinking"
        companion.state.energy = max(0, companion.state.energy - 1)
        companion.state.last_event = "Thinking"
        companion.frame_index = 0

    def tick_animation(self) -> None:
        """Advance animation frame while buddy is thinking."""
        companion = self._active
        if companion.state.mood == "thinking":
            frames = companion.profile.thinking_frames
            if frames:
                companion.frame_index = (companion.frame_index + 1) % len(frames)

    def on_response(
        self,
        success: bool,
        response_text: str,
        tool_calls: int = 0,
        tool_errors: int = 0,
    ) -> None:
        state = self._active.state
        state.tool_calls = tool_calls
        state.tool_errors = tool_errors

        if not success:
            state.mood = "error"
            state.trust = max(0, state.trust - 3)
            state.last_event = "Oops, something failed"
            return

        if tool_calls > 0:
            state.energy = max(0, state.energy - min(8, tool_calls))
            if tool_errors > 0:
                error_rate = tool_errors / tool_calls
                state.trust = max(0, state.trust - min(8, tool_errors * 2))
                if error_rate >= 0.5:
                    state.mood = "error"
                    state.last_event = "Tool chain got messy"
                    return
                state.mood = "sleepy"
                state.last_event = "Recovered from tool hiccups"
                return

            state.trust = min(100, state.trust + min(6, tool_calls))
            state.mood = "excited"
            state.last_event = f"Used {tool_calls} tools cleanly"
            return

        if len(response_text.strip()) > 120:
            state.mood = "happy"
            state.trust = min(100, state.trust + 2)
            state.last_event = "Great answer delivered"
        elif state.energy < 20:
            state.mood = "sleepy"
            state.last_event = "Need a tiny break"
        else:
            state.mood = "idle"
            state.last_event = "Ready for next task"

    def pet(self) -> str:
        companion = self._active
        companion.state.trust = min(100, companion.state.trust + 6)
        companion.state.energy = min(100, companion.state.energy + 3)
        companion.state.mood = "happy"
        companion.state.last_event = "Purr... morale boosted"
        return f"{companion.profile.name} seems happier."

    def feed(self) -> str:
        companion = self._active
        companion.state.energy = min(100, companion.state.energy + 15)
        if companion.state.energy > 60:
            companion.state.mood = "excited"
        companion.state.last_event = "Snack acquired"
        return f"{companion.profile.name} energy restored."

    def render_line(self) -> str:
        companion = self._active
        state = companion.state
        face_lines = self._current_face().split("\n")
        compact = face_lines[1].strip() if len(face_lines) > 1 else face_lines[0].strip()
        return (
            f"{companion.profile.name} {compact}  "
            f"mood={state.mood}  energy={state.energy:>3}%  trust={state.trust:>3}%  "
            f"tools={state.tool_calls}/{state.tool_errors}"
        )

    def render_panel(self) -> Panel:
        companion = self._active
        profile = companion.profile
        state = companion.state
        face = self._current_face()
        return Panel(
            f"{face}\n\n"
            f"[bold]{profile.name}[/bold] · [dim]{profile.style}[/dim]\n"
            f"trait: [italic]{profile.trait}[/italic]\n\n"
            f"mood: {state.mood}  energy: {state.energy}%  trust: {state.trust}%\n"
            f"tools: {state.tool_calls} calls, {state.tool_errors} errors\n"
            f"last: {state.last_event}\n\n"
            f"[dim italic]{profile.story}[/dim italic]",
            title="Buddy Dock",
            expand=False,
        )

    def render_profile_card(self) -> Panel:
        """Full intro page with ASCII art and stat bars."""
        companion = self._active
        profile = companion.profile
        face = profile.faces.get("idle", self._current_face())

        _STAT_META = [
            ("speed",     "⚡", "yellow"),
            ("courage",   "⚔ ", "red"),
            ("curiosity", "◉ ", "cyan"),
            ("stamina",   "♦ ", "green"),
            ("focus",     "◎ ", "blue"),
            ("luck",      "✦ ", "magenta"),
        ]

        def _bar(val: int, width: int = 12) -> str:
            filled = round(val / 100 * width)
            return "█" * filled + "░" * (width - filled)

        stat_rows = []
        for i in range(0, len(_STAT_META), 2):
            n1, ic1, c1 = _STAT_META[i]
            n2, ic2, c2 = _STAT_META[i + 1]
            v1 = profile.stats.get(n1, 0)
            v2 = profile.stats.get(n2, 0)
            stat_rows.append(
                f"  {ic1}[{c1}]{n1:<10}[/{c1}] [{c1}]{_bar(v1)}[/{c1}] [{c1}]{v1:>3}[/{c1}]  "
                f"{ic2}[{c2}]{n2:<10}[/{c2}] [{c2}]{_bar(v2)}[/{c2}] [{c2}]{v2:>3}[/{c2}]"
            )

        content = "\n".join([
            face,
            "",
            f"[bold cyan]{profile.name.upper()}[/bold cyan]   [dim]{profile.style}[/dim]",
            "",
            f'[italic yellow]"{profile.story}"[/italic yellow]',
            f"[bold]Trait:[/bold] [green]{profile.trait}[/green]",
            "",
            "[bold dim]── Stats ──────────────────────────────────────────────[/bold dim]",
            "",
            *stat_rows,
            "",
            "[dim]Your companion is assigned permanently based on your identity.[/dim]",
        ])

        return Panel(
            content,
            title=f"[bold cyan]◈ {profile.name} Profile[/bold cyan]",
            border_style="cyan",
            expand=False,
        )

    def render_buddy_card(self) -> str:
        """Multi-line Rich-markup string for the TUI buddy_card widget."""
        companion = self._active
        profile = companion.profile
        state = companion.state
        face = self._current_face()
        return (
            f"{face}\n"
            "[dim]──────────────────[/dim]\n"
            f"[bold cyan]{profile.name}[/bold cyan]  [dim]{profile.style}[/dim]\n"
            f"[red]♥[/red] {state.trust:>3}%  [yellow]⚡[/yellow] {state.energy:>3}%  "
            f"[dim]{state.mood}[/dim]\n"
            f"[dim]tools {state.tool_calls}/{state.tool_errors} · {state.last_event}[/dim]"
        )

    def _current_face(self) -> str:
        companion = self._active
        if companion.state.mood == "thinking":
            frames = companion.profile.thinking_frames
            if frames:
                return frames[companion.frame_index % len(frames)]
        return companion.profile.faces[companion.state.mood]

    @staticmethod
    def _assign_buddy_key(profiles: list[BuddyProfile]) -> str:
        """Deterministic assignment: same username+hostname always gets same buddy."""
        try:
            import getpass
            user = getpass.getuser()
        except Exception:
            user = "user"
        try:
            host = socket.gethostname()
        except Exception:
            host = "host"
        seed = f"{user}@{host}"
        index = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(profiles)
        return profiles[index].key

    def _build_profiles(self) -> list[BuddyProfile]:  # noqa: PLR0914
        # ── Capybara (Kapi) ───────────────────────────────────────
        _ct = '  .-""-.  '
        _cm = ' (  __  ) '
        _cb = "  '----'  "
        kapi_faces = {
            "idle":     f"{_ct}\n ( ō  ō)~ \n{_cm}\n{_cb}",
            "thinking": f"{_ct}\n ( -  -)? \n{_cm}\n{_cb}",
            "happy":    f"{_ct}\n ( ^  ^)♪ \n ( uu uu )\n{_cb}",
            "excited":  f"{_ct}\n ( >  <)! \n ( uu uu )\n{_cb}",
            "sleepy":   f"{_ct}\n (-.  .-)z \n{_cm}\n{_cb}",
            "error":    f"{_ct}\n ( x  x)! \n{_cm}\n{_cb}",
        }
        kapi_thinking = [
            f"{_ct}\n ( -  -)? \n{_cm}\n{_cb}",
            f"{_ct}\n ( .  .).. \n{_cm}\n{_cb}",
            f"{_ct}\n ( ō  ō).. \n{_cm}\n{_cb}",
            f"{_ct}\n ( .  .).. \n{_cm}\n{_cb}",
        ]

        # ── Raccoon (Tanuki) ─────────────────────────────────────
        _rr = "  /\\_/\\  "
        _rm = " (  --  ) "
        _rb = "  '----'  "
        tanuki_faces = {
            "idle":     f"{_rr}\n (#ō  ō#) \n{_rm}\n{_rb}",
            "thinking": f"{_rr}\n (#-  -#)?\n{_rm}\n{_rb}",
            "happy":    f"{_rr}\n (#^  ^#)♪\n ( ww ww )\n{_rb}",
            "excited":  f"{_rr}\n (#>  <#)!\n ( ww ww )\n{_rb}",
            "sleepy":   f"{_rr}\n (#-..-#)z\n{_rm}\n{_rb}",
            "error":    f"{_rr}\n (#x  x#)!\n{_rm}\n{_rb}",
        }
        tanuki_thinking = [
            f"{_rr}\n (#-  -#)?\n{_rm}\n{_rb}",
            f"{_rr}\n (#.  .#)..\n{_rm}\n{_rb}",
            f"{_rr}\n (#ō  ō#)..\n{_rm}\n{_rb}",
            f"{_rr}\n (#.  .#)..\n{_rm}\n{_rb}",
        ]

        # ── Panda (Bao) ──────────────────────────────────────────
        _pt = " (@)  (@) "
        _pm = " (   --  ) "
        _pb = "  '-----' "
        bao_faces = {
            "idle":     f"{_pt}\n ( ô  ô  )\n{_pm}\n{_pb}",
            "thinking": f"{_pt}\n ( -  -  )?\n{_pm}\n{_pb}",
            "happy":    f"{_pt}\n ( ^  ^  )♪\n ( uu uu )\n{_pb}",
            "excited":  f"{_pt}\n ( >  <  )!\n ( uu uu )\n{_pb}",
            "sleepy":   f"{_pt}\n (-.    .-) \n{_pm}\n{_pb}",
            "error":    f"{_pt}\n ( x  x  )!\n{_pm}\n{_pb}",
        }
        bao_thinking = [
            f"{_pt}\n ( -  -  )?\n{_pm}\n{_pb}",
            f"{_pt}\n ( .  .  )..\n{_pm}\n{_pb}",
            f"{_pt}\n ( ô  ô  )..\n{_pm}\n{_pb}",
            f"{_pt}\n ( .  .  )..\n{_pm}\n{_pb}",
        ]

        # ── Red Fox (Ember) ──────────────────────────────────────
        _ft = "  /\\  /\\ "
        _fm = " (  ~~  ) "
        _fb = "  >----<  "
        ember_faces = {
            "idle":     f"{_ft}\n (>ō  ō<) \n{_fm}\n{_fb}",
            "thinking": f"{_ft}\n (>-  -<)?\n{_fm}\n{_fb}",
            "happy":    f"{_ft}\n (>^  ^<)♪\n ( uu uu )\n{_fb}",
            "excited":  f"{_ft}\n (>>  <<)!\n ( uu uu )\n{_fb}",
            "sleepy":   f"{_ft}\n (>-..-<)z\n{_fm}\n{_fb}",
            "error":    f"{_ft}\n (>x  x<)!\n{_fm}\n{_fb}",
        }
        ember_thinking = [
            f"{_ft}\n (>-  -<)?\n{_fm}\n{_fb}",
            f"{_ft}\n (>.- -.< )\n{_fm}\n{_fb}",
            f"{_ft}\n (>ō  ō<)..\n{_fm}\n{_fb}",
            f"{_ft}\n (>.- -.<) \n{_fm}\n{_fb}",
        ]

        return [
            BuddyProfile(
                key="kapi",
                name="Kapi",
                style="capybara",
                trait="peaceful and unhurried",
                story="A capybara who tends forest code with absolute calm.",
                faces=kapi_faces,
                thinking_frames=kapi_thinking,
                stats={"speed": 30, "courage": 65, "curiosity": 80, "stamina": 95, "focus": 85, "luck": 70},
            ),
            BuddyProfile(
                key="tanuki",
                name="Tanuki",
                style="raccoon",
                trait="clever and mischievous",
                story="A masked raccoon who raids tool caches in the night.",
                faces=tanuki_faces,
                thinking_frames=tanuki_thinking,
                stats={"speed": 88, "courage": 60, "curiosity": 85, "stamina": 55, "focus": 50, "luck": 90},
            ),
            BuddyProfile(
                key="bao",
                name="Bao",
                style="panda",
                trait="methodical and serene",
                story="A bamboo-chewing panda who indexes every snippet twice.",
                faces=bao_faces,
                thinking_frames=bao_thinking,
                stats={"speed": 40, "courage": 55, "curiosity": 90, "stamina": 80, "focus": 92, "luck": 60},
            ),
            BuddyProfile(
                key="ember",
                name="Ember",
                style="red fox",
                trait="bold and persistent",
                story="A fox who was once a cockpit AI; never backs from hard tasks.",
                faces=ember_faces,
                thinking_frames=ember_thinking,
                stats={"speed": 78, "courage": 95, "curiosity": 70, "stamina": 72, "focus": 65, "luck": 45},
            ),
        ]