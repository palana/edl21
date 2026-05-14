"""Runtime patch for ``pysml.asyncio.SmlSerialProtocol``.

Workaround for `home-assistant/core#169980
<https://github.com/home-assistant/core/issues/169980>`_.

pysml 0.1.5 lets the receive buffer of ``SmlSerialProtocol`` grow
without bound whenever the parser can't extract a complete SML frame
— for example because the serial line is delivering garbage during a
reconnect, the meter is currently in ``InF=Off`` mode, or a frame is
truncated. The internal regex scans the whole buffer with
``re.DOTALL`` on every incoming chunk, so unbounded growth turns into
``O(n^2)`` work and the integration eventually stops dispatching
telegrams. The reconnect watchdog also reuses the same protocol
instance and therefore the same buffer, so a reconnect doesn't
actually recover from the stuck state.

The patch does three things to ``data_received``:

1. caps the buffer at :data:`MAX_BUFFER` bytes;
2. on a ``find_frame`` miss with no telegrams dispatched for
   :data:`STALE_TIMEOUT` seconds, trims the buffer back to the last
   plausible SML start marker (or clears it entirely if no marker is
   present);
3. resets ``self._last_update`` to ``0`` after a stale-buffer reset
   so the pysml watchdog forces a reconnect on its next tick.

The patch is idempotent: a second call returns ``True`` without
re-wrapping ``data_received``. It is a no-op if ``pysml`` cannot be
imported.
"""

from __future__ import annotations

import logging
import time

_LOGGER = logging.getLogger(__name__)

# At 9600 baud (the typical IR-head rate) a 16 KB buffer corresponds
# to roughly 17 seconds of continuous data. A complete SML frame is
# usually well under 1 KB, so the cap is very generous in practice
# and only fires on pathological growth.
MAX_BUFFER = 16 * 1024

# Stale-buffer detection thresholds. When the buffer exceeds
# ``STALE_THRESHOLD`` bytes AND no telegram has been dispatched for
# ``STALE_TIMEOUT`` seconds, the parser is assumed to be stuck.
STALE_THRESHOLD = 4 * 1024
STALE_TIMEOUT = 30.0

# SML start marker: 4× ESC followed by 4× 0x01.
_SML_START = b"\x1b\x1b\x1b\x1b\x01\x01\x01\x01"


def install_pysml_buffer_patch() -> bool:
    """Install the buffer-bounding patch on ``SmlSerialProtocol``.

    Returns ``True`` if the patch is in place after the call (either
    just installed or already installed by a previous call) and
    ``False`` if ``pysml`` could not be imported.
    """
    try:
        # ``sml`` is the module name pysml installs under; not a typo.
        from sml.asyncio import SmlSerialProtocol  # type: ignore[import-untyped]
    except ImportError:
        _LOGGER.warning("pysml not importable; buffer patch skipped")
        return False

    if getattr(SmlSerialProtocol, "_edl21_buffer_patch_applied", False):
        return True

    original_data_received = SmlSerialProtocol.data_received

    def patched_data_received(self, data: bytes) -> None:
        """Drop-in replacement for ``SmlSerialProtocol.data_received``."""
        self._buf += data
        now = time.time()
        while True:
            end, frame = self.find_frame(self._buf)
            buf_before = len(self._buf)
            self._buf = self._buf[end:]

            if not frame:
                last_dispatch = getattr(
                    self, "_edl21_last_dispatch", self._last_update
                )
                stale = (
                    len(self._buf) > STALE_THRESHOLD
                    and (now - last_dispatch) > STALE_TIMEOUT
                )
                if stale or len(self._buf) > MAX_BUFFER:
                    idx = self._buf.rfind(_SML_START)
                    if idx > 0:
                        dropped = idx
                        self._buf = self._buf[idx:]
                    elif idx == 0 and len(self._buf) > STALE_THRESHOLD:
                        # An ESC marker is at offset 0 but no frame has
                        # been completable for a long time — the frame
                        # is broken. Keep only the marker so the next
                        # bytes can start a fresh frame.
                        dropped = len(self._buf) - len(_SML_START)
                        self._buf = self._buf[: len(_SML_START)]
                    else:
                        dropped = len(self._buf) - len(_SML_START)
                        self._buf = self._buf[-len(_SML_START) :]
                    _LOGGER.warning(
                        "pysml stale buffer (%d B, no dispatch for %.1fs) — "
                        "dropped %d B, resetting watchdog",
                        buf_before,
                        now - last_dispatch,
                        dropped,
                    )
                    # Force the pysml watchdog to reconnect on the next
                    # tick by zeroing the last-update timestamp.
                    self._last_update = 0
                break

            for msg in frame:
                body = msg.get("messageBody")
                if body:
                    self._dispatch(body)
            self._last_update = now
            self._edl21_last_dispatch = now  # type: ignore[attr-defined]

    SmlSerialProtocol.data_received = patched_data_received  # type: ignore[method-assign]
    SmlSerialProtocol._edl21_buffer_patch_applied = True  # type: ignore[attr-defined]
    SmlSerialProtocol._edl21_buffer_patch_original = (  # type: ignore[attr-defined]
        original_data_received
    )
    return True
