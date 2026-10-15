from datetime import datetime,timezone
from dhan_cas_bot.seconds_events import latest_event

NOW=datetime(2026,10,15,8,tzinfo=timezone.utc)

def test_old_future_unrelated_or_unofficial_events_are_not_live_catalysts():
    def row(t,symbol='TEST',url='https://nsearchives.nseindia.com/corporate/results.pdf'):
        return {'symbol':symbol,'desc':'Financial Results','an_dt':t,'attchmntFile':url}
    assert latest_event([row('15-Oct-2026 13:29:50')],{'TEST'},NOW)['received_at']==NOW.isoformat()
    for r in [row('15-Oct-2026 13:31:00'),row('15-Oct-2026 12:00:00'),
              row('15-Oct-2026 13:29:50','OTHER'),row('15-Oct-2026 13:29:50',url='https://example.com/fake')]:
        assert latest_event([r],{'TEST'},NOW) is None
