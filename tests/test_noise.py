from datetime import timedelta
from decimal import Decimal as D
import pytest
from research.noise.direction import holm,clustered
from research.noise.compile import adapted
from research.noise.filings import classify,extract
from research.noise.content import content_records

def test_holm_accounts_for_all_nine_prespecified_families():
    result=holm({'a':.004,'b':.007,'c':.3,'missing':None})
    assert result['a']==pytest.approx(.036)
    assert result['b']==pytest.approx(.056)
    assert result['c']==1 and 'missing' not in result

def test_clustering_does_not_treat_same_day_events_as_independent():
    rows=[{'day':'2026-07-20','signed_return':.01} for _ in range(100)]
    assert clustered(rows)['days']==1 and clustered(rows)['p'] is None
    rows.append({'day':'2026-07-21','signed_return':-.01})
    result=clustered(rows,draws=100)
    assert result['days']==2 and result['mean_signed_return']==0

def test_flip_preserves_information_time_and_does_not_mutate_original():
    s={'id':'a','at':'2026-07-20T10:00:00+05:30','reference':'100','extreme':'110','side':'CE','contract_key':'x'}
    other=adapted(s,'PE')
    assert other['at']==s['at'] and other['extreme']=='90'
    assert 'contract_key' not in other and s['contract_key']=='x'
    assert adapted(s,'CE')['contract_key']=='x'

def test_sast_share_purchase_is_not_business_acquisition():
    text='Disclosure under Regulation 29 of SEBI Substantial Acquisition of Shares Regulations. '+('Details of acquisition of shares in the company and holdings of the promoter. '*5)
    result=classify(text)
    assert result['ownership_notice'] if result['status']=='CATEGORY_MATCH' else result['status']=='OWNERSHIP_NOTICE'
    assert 'BUSINESS_ACQUISITION' not in result['categories']

def test_scanned_unreadable_content_is_unknown():
    assert classify('')['status']=='UNKNOWN_UNREADABLE'

def test_actual_results_and_acquisition_are_separate_categories():
    results=classify('Statement of audited financial results for the quarter ended June 30. '+('Revenue and profit tables are enclosed. '*10))
    assert 'FINANCIAL_RESULTS' in results['categories']
    acquisition=classify('The board approved acquisition of the industrial explosives business from an independent seller. '+('The acquired business is located overseas. '*8))
    assert 'BUSINESS_ACQUISITION' in acquisition['categories']

def test_attachment_reclassification_preserves_time_and_unknowns():
    rows={'X':[
        {'id':'a','at':'2026-07-20T10:03:01+05:30','quality':'UNKNOWN_MATERIALITY','url':'a'},
        {'id':'b','at':'2026-07-20T11:03:01+05:30','quality':'QUALIFYING_TEXT','url':'missing'},
        {'id':'c','at':'2026-07-20T12:03:01+05:30','quality':'QUALIFYING_TEXT','url':'ownership'}]}
    docs=[{'url':'a','status':'CATEGORY_MATCH','categories':['FINANCIAL_RESULTS']},
          {'url':'ownership','status':'OWNERSHIP_NOTICE','categories':[]}]
    changed=content_records(rows,docs)['X']
    assert [r['quality'] for r in changed]==['QUALIFYING_TEXT','UNKNOWN_MATERIALITY','OTHER']
    assert [r['at'] for r in changed]==[r['at'] for r in rows['X']]
    assert rows['X'][0]['quality']=='UNKNOWN_MATERIALITY'

def test_archive_members_cannot_write_outside_working_paths(tmp_path):
    import zipfile
    raw=tmp_path/'disclosure.zip';txt=tmp_path/'disclosure.txt'
    with zipfile.ZipFile(raw,'w') as z:
        z.writestr('../../escaped.xml','<event><type>Resignation of chief executive officer</type></event>')
    body,errors=extract(raw,txt)
    assert 'Resignation of chief executive officer' in body and not errors
    assert sorted(p.name for p in tmp_path.iterdir())==['disclosure.txt','disclosure.zip']

def test_archive_member_limit_fails_closed(tmp_path):
    import zipfile
    raw=tmp_path/'too_many.zip'
    with zipfile.ZipFile(raw,'w') as z:
        for i in range(101):z.writestr(str(i)+'.xml','<x/>')
    with pytest.raises(ValueError,match='bound'):extract(raw,tmp_path/'out.txt')

def test_strict_bankroll_stops_at_unknown_instead_of_returning_start_cash():
    from research.noise.paths import Runner
    from datetime import datetime
    s={'id':'missing','side':'CE','symbol':'X','at':'2026-07-20T10:00:00+05:30',
       'materiality':'NOT_REQUIRED','futures_confirmation':'NOT_REQUIRED'}
    r=Runner.__new__(Runner);r.engine='TEST';r.source={'signals':[s]}
    r.bans={'2026-07-20':{'status':'VERIFIED_DATE','symbols':[]}}
    r.items={(s['id'],'CE'):{'signal':s,'at':datetime.fromisoformat(s['at']),
                              'error':'missing historical contract','contracts':[]}}
    strict=r.run(strict=True)
    assert strict['stopped'] and strict['terminal_conditional_cash'] is None
    assert strict['last_resolved_cash']=='9411.18' and strict['gaps']==1
    conditional=r.run()
    assert not conditional['stopped'] and conditional['gaps']==1
    assert conditional['terminal_conditional_cash']=='9411.18'

def test_explicit_merger_category_is_collected_despite_old_metadata_filter():
    from research.noise.universe import relevant
    r={'id':'merger','at':'2026-07-20T10:30:01+05:30','quality':'OTHER',
       'category':'Amalgamation/Merger','url':'primary_attachment'}
    assert relevant(r)
    docs=[{'url':r['url'],'status':'CATEGORY_MATCH','categories':['BUSINESS_ACQUISITION']}]
    revised=content_records({'X':[r]},docs)['X'][0]
    assert revised['quality']=='QUALIFYING_TEXT' and revised['at']==r['at']
    assert not relevant({'quality':'OTHER','category':'Copy of Newspaper Publication'})
