from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace

from dhan_cas_bot.domain import Instrument, OptionBook, OptionType, Segment, Level
from dhan_cas_bot.seconds_strategies import NAMES, SecondsTape, opportunity, entry_candidate

NOW = datetime(2026, 10, 15, 8, tzinfo=timezone.utc)


def book(at=NOW, bid='99.9', ask='100', quantity=650):
    inst = Instrument('1', 'NIFTY', Segment.NSE_FNO, NOW.date(), OptionType.CE,
                      D(23000), 65, D('.05'), 3510)
    return OptionBook(inst, (Level(D(bid), quantity),), (Level(D(ask), quantity),),
                      'm1', int(at.timestamp()*1e9))


def test_no_missing_future_event_or_warmup_can_generate_signal():
    tape = SecondsTape()
    samples = tape.evaluate(NOW, {'1': book()}, (), None)
    assert set(samples) == set(NAMES)
    assert all(v.state != 'SIGNAL' for v in samples.values())
    assert samples['SECONDS_EVENT_IMPULSE'].reason == 'EVENT_FEED_UNAVAILABLE'


def test_negative_edge_stale_crossed_thin_or_unaffordable_quotes_cannot_enter():
    sample = opportunity(NAMES[0], NOW, book(), D('105'), D(23000), 'episode')
    assert entry_candidate(sample, {'1': book()}, D(7805), NOW) is not None
    for bad in (replace(book(), received_ns=book().received_ns-3_000_000_000),
                book(bid='101', ask='100'), book(quantity=1)):
        assert entry_candidate(sample, {'1': bad}, D(7805), NOW) is None
    assert entry_candidate(sample, {'1': book()}, D(100), NOW) is None
    assert entry_candidate(replace(sample, details={**sample.details, 'target_price': '100.1'}),
                           {'1': book()}, D(7805), NOW) is None


def test_future_receipt_and_market_epoch_are_not_replayed():
    tape = SecondsTape()
    tape.future_tick(D(23000), int(NOW.timestamp()*1e9), 'm1')
    tape.future_tick(D(24000), int(NOW.timestamp()*1e9)-1, 'm1')
    assert tape.future[-1][1] == D(23000)
    tape.reset()
    assert not tape.future and not tape.options


def test_event_publication_without_receipt_and_source_is_not_a_signal():
    tape = SecondsTape()
    invalid = {'published_at': NOW.isoformat(), 'direction': 'CE', 'token': 'PRIVATE'}
    samples = tape.evaluate(NOW, {'1': book()}, (), None, event=invalid)
    assert samples['SECONDS_EVENT_IMPULSE'].state == 'UNKNOWN'


def seeded_tape():
    from datetime import timedelta
    from tests.test_session_strategies import calendar
    tape=SecondsTape();end=NOW
    rows={}
    for sec in range(66):
        at=end-timedelta(seconds=65-sec)
        future=D(23000)+D(sec)/5
        tape.future_tick(future,int(at.timestamp()*1e9),'m1')
        rows={}
        for ident,strike,base in [('1',23000,110),('2',23050,85),('3',23100,65)]:
            b=book(at,bid=str(D(base)+D(sec)/10-D('.05')),ask=str(D(base)+D(sec)/10+D('.05')))
            b=replace(b,instrument=replace(b.instrument,security_id=ident,strike=D(strike)))
            rows[ident]=b
        tape.ingest(rows,at)
    cal=SimpleNamespace(fresh=lambda now:True,is_open=lambda now:True,closes=NOW+timedelta(hours=2))
    return tape,rows,cal


def test_catchup_and_curvature_rules_use_only_prior_fit():
    from datetime import timedelta
    tape,rows,cal=seeded_tape();at=NOW+timedelta(seconds=1)
    tape.future_tick(D('23030'),int(at.timestamp()*1e9),'m1')
    fresh={key:replace(b,received_ns=int(at.timestamp()*1e9)) for key,b in rows.items()}
    out=tape.evaluate(at,fresh,(),cal)
    assert out[NAMES[0]].state=='SIGNAL'
    assert D(out[NAMES[0]].details['response_beta'])==D('.5')
    # Both neighbours move; the middle strike's pre-event curvature is fixed.
    def up(b):return replace(b,bids=(Level(b.top_bid.price+10,650),),asks=(Level(b.top_ask.price+10,650),))
    fresh['1']=up(fresh['1']);fresh['3']=up(fresh['3'])
    out=tape.evaluate(at,fresh,(),cal)
    assert out[NAMES[3]].state=='SIGNAL'
    assert out[NAMES[3]].details['security_id']=='2'
    # Adding a future-dated favourable quote cannot improve current signals.
    ahead={k:replace(b,received_ns=int((at+timedelta(seconds=10)).timestamp()*1e9)) for k,b in fresh.items()}
    assert all(s.state!='SIGNAL' for s in tape.evaluate(at,ahead,(),cal).values())


def test_unexpected_epoch_cannot_replace_current_history():
    tape=SecondsTape();stamp=int(NOW.timestamp()*1e9)
    tape.future_tick(D(23000),stamp,'current')
    tape.future_tick(D(24000),stamp+1_000_000_000,'foreign')
    assert tape.epoch=='current' and tape.future[-1][1]==D(23000)


def test_event_signal_requires_public_event_and_post_receipt_market_response():
    from datetime import timedelta
    tape,rows,cal=seeded_tape();at=NOW+timedelta(seconds=1)
    tape.future_tick(D(23030),int(at.timestamp()*1e9),'m1')
    fresh={key:replace(b,received_ns=int(at.timestamp()*1e9)) for key,b in rows.items()}
    event={'published_at':(NOW-timedelta(seconds=3)).isoformat(),
           'received_at':(NOW-timedelta(seconds=2)).isoformat(),
           'underlying':'NIFTY','source_url':'https://nsearchives.nseindia.com/corporate/filing.pdf'}
    assert tape.evaluate(at,fresh,(),cal,event=event)[NAMES[4]].state=='SIGNAL'
    event['received_at']=(at+timedelta(seconds=1)).isoformat()
    assert tape.evaluate(at,fresh,(),cal,event=event)[NAMES[4]].state!='SIGNAL'


def test_flow_signal_requires_trade_volume_not_just_a_large_bid():
    from datetime import timedelta
    tape,rows,cal=seeded_tape()
    for sec in (1,2,3):
        at=NOW+timedelta(seconds=sec)
        tape.future_tick(D(23020+sec*5),int(at.timestamp()*1e9),'m1')
        b=replace(rows['1'],received_ns=int(at.timestamp()*1e9),
            bids=(Level(D(116+sec*3),1300),),asks=(Level(D('116.1')+sec*3,130),),
            statistics=SimpleNamespace(volume=sec*10000))
        tape.ingest({'1':b},at)
    sample=tape.evaluate(at,{'1':b},(),cal)[NAMES[2]]
    assert sample.state=='SIGNAL'
    tape.options['1']=__import__('collections').deque([(t,p,None,bq,aq) for t,p,v,bq,aq in tape.options['1']],maxlen=600)
    assert tape.evaluate(at,{'1':b},(),cal)[NAMES[2]].state!='SIGNAL'


def test_failed_breakout_requires_return_inside_the_preexisting_range():
    from datetime import timedelta
    tape=SecondsTape();end=NOW;inst=replace(book().instrument,option_type=OptionType.PE)
    for sec in range(66):
        at=end-timedelta(seconds=65-sec)
        f=D(23000)+D(sec);price=D(120)-D(sec)/2
        tape.future_tick(f,int(at.timestamp()*1e9),'m1')
        b=replace(book(at,bid=str(price-D('.05')),ask=str(price+D('.05'))),instrument=inst)
        tape.ingest({'1':b},at)
    cal=SimpleNamespace(fresh=lambda now:True,is_open=lambda now:True,closes=NOW+timedelta(hours=2))
    for sec,f in [(1,D(23080)),(2,D(23075)),(3,D(23050))]:
        at=NOW+timedelta(seconds=sec);tape.future_tick(f,int(at.timestamp()*1e9),'m1')
    b=replace(b,received_ns=int(at.timestamp()*1e9),bids=(Level(D('94.95'),650),),asks=(Level(D('95.05'),650),))
    assert tape.evaluate(at,{'1':b},(),cal)[NAMES[1]].state=='SIGNAL'


def test_brief_stale_option_cannot_erase_prior_fit_or_be_traded():
    from datetime import timedelta
    tape, rows, cal = seeded_tape()
    old_count = len(tape.options['1'])
    gap = NOW + timedelta(seconds=2)
    tape.future_tick(D('23020'), int(gap.timestamp()*1e9), 'm1')
    others = {k: replace(b, received_ns=int(gap.timestamp()*1e9))
              for k, b in rows.items() if k != '1'}
    tape.evaluate(gap, {**others, '1': rows['1']}, (), cal)
    assert len(tape.options.get('1', ())) == old_count
    sample = opportunity(NAMES[0], gap, rows['1'], D(150), D(23020), 'stale')
    assert entry_candidate(sample, rows, D(7805), gap) is None
    at = gap + timedelta(seconds=1)
    tape.future_tick(D('23040'), int(at.timestamp()*1e9), 'm1')
    fresh = {k: replace(b, received_ns=int(at.timestamp()*1e9)) for k, b in rows.items()}
    assert tape.evaluate(at, fresh, (), cal)[NAMES[0]].state == 'SIGNAL'
    # A real epoch loss must still discard the old fit completely.
    tape.reset()
    assert not tape.options and not tape.future


def test_missing_option_books_are_unknown_not_a_completed_no_signal():
    tape, rows, cal = seeded_tape()
    out = tape.evaluate(NOW, {}, (), cal)
    assert all(out[n].state == 'UNKNOWN' for n in NAMES[:4])
    assert all(out[n].reason == 'OPTIONS_FEED_UNAVAILABLE' for n in NAMES[:4])


def test_execution_rejections_expose_exact_cash_depth_spread_and_net_reason():
    from dhan_cas_bot.seconds_strategies import entry_assessment
    sample = opportunity(NAMES[0], NOW, book(), D(105), D(23000), 'episode')
    assert entry_assessment(sample, {'1': book()}, D(100), NOW).reason == 'SECONDS_UNAFFORDABLE'
    assert entry_assessment(sample, {'1': book(quantity=65)}, D(7805), NOW).reason == 'SECONDS_DEPTH_TOO_THIN'
    assert entry_assessment(sample, {'1': book(bid='97')}, D(7805), NOW).reason == 'SECONDS_SPREAD_TOO_WIDE'
    cheap = replace(sample, details={**sample.details, 'target_price': '100.1'})
    rejected = entry_assessment(cheap, {'1': book()}, D(7805), NOW)
    assert rejected.reason == 'SECONDS_NET_EDGE_TOO_SMALL'
    assert D(rejected.details['net_at_target']) < D(rejected.details['minimum_net_edge'])
    assert entry_assessment(sample, {'1': book()}, D(7805), NOW).candidate is not None


def test_invalid_future_blocks_entry_without_destroying_valid_prior_observations():
    from datetime import timedelta
    tape, rows, cal = seeded_tape()
    size = len(tape.future)
    tape.invalidate_future()
    assert not tape.future_current(NOW)
    assert len(tape.future) == size
    assert all(tape.evaluate(NOW, rows, (), cal)[n].state != 'SIGNAL' for n in NAMES)
    at = NOW + timedelta(seconds=1)
    tape.future_tick(D('23030'), int(at.timestamp()*1e9), 'm1')
    fresh = {k: replace(b, received_ns=int(at.timestamp()*1e9)) for k, b in rows.items()}
    assert tape.future_current(at)
    assert tape.evaluate(at, fresh, (), cal)[NAMES[0]].state == 'SIGNAL'


def test_retained_option_history_expires_and_cannot_grow_without_bound():
    from datetime import timedelta
    tape, rows, cal = seeded_tape()
    for n in range(120):
        b = replace(rows['1'], instrument=replace(rows['1'].instrument, security_id=str(n+10)))
        tape.ingest({b.instrument.security_id:b}, NOW)
    assert len(tape.options) <= 96
    assert len(tape.selected) <= 24
    tape.ingest({}, NOW + timedelta(seconds=91))
    assert not tape.options and not tape.selected
