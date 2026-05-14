# hass-edl21

A HACS-installable drop-in replacement for the Home Assistant Core
`edl21` integration with three changes:

1. **serialx instead of pyserial-asyncio-fast.** The integration calls
   [`serialx.patch_pyserial()`](https://github.com/puddly/serialx)
   at startup so pysml's transitive serial backend is redirected to
   [puddly/serialx](https://github.com/puddly/serialx), which is the
   library Home Assistant Core is migrating to (see
   [Serious about serial][serialx-blog]).
2. **Configurable scan interval.** Adds an options-flow knob
   (Settings → Devices & Services → EDL21 → **Configure**) that
   overrides Core's hard-coded 60-second update throttle. Default is
   **10 seconds**; minimum 1 s, maximum 3600 s.
3. **pysml buffer fix.** Bundles a runtime patch on
   `pysml.asyncio.SmlSerialProtocol.data_received` that bounds the
   receive buffer and forces a reconnect on a stuck parser —
   workaround for [home-assistant/core#169980][issue-169980].

The integration registers under the same domain as core (`edl21`),
so installing it will cause Home Assistant to log

> Detected that custom integration `edl21` is overriding a core
> integration.

That's expected. While the custom version is on disk Home Assistant
ignores the core one. To go back to core, remove the integration via
HACS (or delete `custom_components/edl21/`) and restart.

## Installation

### HACS (recommended)

1. In HACS → three-dot menu → **Custom repositories**, add
   `https://github.com/palana/edl21` with category
   **Integration**.
2. Install the **EDL21 (custom interval)** entry.
3. Restart Home Assistant.
4. **Settings → Devices & Services → + Add Integration → EDL21**
   and enter your IR-head serial path (`/dev/serial/by-id/usb-…` or
   `socket://host:port` for ser2net).
5. After the entry is created, click **Configure** to change the
   scan interval.

### Manual

```sh
# In your Home Assistant config directory:
cd config
mkdir -p custom_components
# Copy the custom_components/edl21 folder from this repo into config/custom_components/
```

Then restart Home Assistant and proceed from step 4 above.

## Configuration

This integration is set up entirely through the UI. After adding the
integration, the **Configure** button on the device card exposes:

| Option | Default | Notes |
| --- | --- | --- |
| Scan interval (seconds) | 10 | Per-entity update throttle. Smaller values give more detail but a larger recorder history table. |

The serial port is set in the initial add step and can be changed by
removing and re-adding the integration.

## How the three changes work

### serialx swap

The integration imports `serialx` and calls `patch_pyserial()` at the
top of its `__init__.py`, **before** anything imports
`sml.asyncio`. From that point on, any code that does
`import serial_asyncio_fast` (including pysml's internals) actually
gets serialx. `serialx` is added as an explicit requirement in
`manifest.json`; `pysml`'s own dependency on `pyserial-asyncio-fast`
is left in place but unused at runtime.

### Configurable scan interval

Core hard-codes `MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)` in
`sensor.py` and feeds it into the per-entity dispatcher throttle.
This fork removes the constant, reads `scan_interval_seconds` from
the config entry's options, and passes the resulting `timedelta`
down to each `EDL21Entity` at construction time. The integration
reloads itself on option changes so the new value takes effect
without a restart.

### pysml buffer fix

[home-assistant/core#169980][issue-169980] reports the integration
silently stops dispatching telegrams after a few hours, with logs
showing `Skipped <N> bytes at offset 0` and unbounded buffer growth.
The root cause is in `pysml.asyncio.SmlSerialProtocol.data_received`:
the buffer is regex-scanned on every chunk and never shortened when
no complete frame is found, so growth turns into `O(n²)` work and
the watchdog's reconnect reuses the same protocol instance (and
buffer). The patch in `pysml_patch.py` wraps `data_received` so that:

- the buffer is hard-capped at 16 KB;
- on a parser miss with the buffer over 4 KB and no telegram
  dispatched in the last 30 s, the buffer is trimmed back to the
  last plausible SML start marker (`1B 1B 1B 1B 01 01 01 01`), or
  cleared entirely if no marker is present;
- `self._last_update` is reset to `0` so pysml's watchdog tears
  down and rebuilds the connection on its next tick.

The patch is idempotent and is a no-op if pysml is not installed.

## Compatibility

- Minimum Home Assistant Core: **2024.4.0**.
- Supported pysml: **0.1.5** (pinned in `manifest.json`).
- Supported serialx: **>= 1.0.0**.

## Credits and derivation

The integration code is derived from
[`home-assistant/core/homeassistant/components/edl21`][core-edl21]
(Apache 2.0). The configurable scan-interval idea is taken from
[fuslwusl/homeassistant-edl21-custom-interval][fuslwusl] (also
Apache 2.0). The pysml runtime patch is adapted from a community
comment on [issue #169980][issue-169980].

This is not an official Home Assistant integration and is not
maintained by the Home Assistant project, pysml, or serialx.

## License

Apache License 2.0. See [LICENSE](LICENSE).

[serialx-blog]: https://developers.home-assistant.io/blog/2026/04/27/pyserial-to-serialx/
[issue-169980]: https://github.com/home-assistant/core/issues/169980
[core-edl21]: https://github.com/home-assistant/core/tree/dev/homeassistant/components/edl21
[fuslwusl]: https://github.com/fuslwusl/homeassistant-edl21-custom-interval
