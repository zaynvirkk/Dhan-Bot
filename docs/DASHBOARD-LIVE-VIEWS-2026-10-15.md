# Compact dashboard, 15 October

The operator found the monitoring page noisy, unintuitive and excessively long.
The authenticated page measured 20,010 CSS pixels high on a 943-pixel desktop
viewport before this change. All anchor links previously led into that same page.

The dashboard now has three actual views:

- **Live:** available cash with source age, reported closed-trade net P&L after
  reported fees, open positions and a short current decision. Two collapsed
  strategy rows show eligibility, recorded inputs and the reason for waiting.
  An existing position remains visible with its recorded exit information.
- **History:** actual per-strategy results and completed trades, including holding
  duration and net P&L. Broker order attempts/route checks, monitoring samples
  and technical activity are separate collapsed disclosures.
- **System:** live connections, diagnostics, detailed strategy/input information,
  account accounting and existing operator instructions.

This is a presentation change. It does not change money allocation, strategy
signals, order submission, route checks, exits, broker credentials or authority.
The qualified funded process must not be restarted for this deployment.

The compact overview preserves exact money strings. Missing fees remain pending,
not zero profit. A truncated execution list cannot establish zero trades today.
Zero-fill attempts are not counted as completed trades. Cached decision metrics
are dated and separated from the newest market quote; unknown inputs are not
made into zero percent or passed conditions. The current trading state takes
precedence over an old no-signal explanation. The full detail remains accessible
without populating the Live view with it.

The browser regression suite checks pane isolation, stale permission, unknown
inputs/fees, route qualification versus standing permission, retained dated
checks, expanded disclosures and incomplete history. Existing authentication,
streaming, source-age, account-failure and actual-history checks remain in place.

First signed-in browser pass verified HTTP200, isolated views, all17 actual
completed trades and zero horizontal overflow at1440px and390px. Live measured
1012px on a1000px desktop viewport and869px on an844px phone viewport, compared
with20,010px before. The final bounded refinement prioritizes today’s eligible
engine, uses a flex page to remove spare vertical overflow, compresses history
rows and shows a three-column strategy summary. Accounting, individual fees
and full position/exit information remain in disclosures. No browser fixture
was presented as a real held position; held/unknown states use DOM fixtures.
