"""Real OMS/ledger regressions for historical order summaries, synthetic account."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from dhan_cas_bot.domain import Fill, Intent, ContractError
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.orders import OrderManager
from tests.acceptance.cas.support import instrument
from tests.conftest import FakeBroker


def setup(tmp_path):
    ledger=Ledger(tmp_path/'ledger.sqlite3');broker=FakeBroker();inst=instrument()
    stamp=datetime.now(timezone.utc)-timedelta(days=1)
    ledger.db.execute('INSERT INTO lifecycles VALUES(?,?,?,?,?,?)',('closed','session',inst.security_id,'9411.18','CLOSED','{}'))
    for side,order,price in [('BUY','buy','11'),('SELL','sell','14')]:
        intent=Intent(side,side,inst,130,D(price),side,stamp,'closed')
        ledger.create_intent(intent,D(2000) if side=="BUY" else D(0));row={'orderId':order,'orderStatus':'TRADED','filledQty':130}
        ledger.record_order(order,side,'TEST','TRADED',row)
        fills=[('b1',65,'10'),('b2',65,'12')] if side=='BUY' else [('s1',130,'14')]
        for ident,q,p in fills:ledger.record_fill_once(Fill(ident,order,inst.security_id,q,D(p),D(0),stamp),side,{})
        ledger.set_intent_state(side,'FILLED')
    rows=[{'dhanClientId':'TEST','orderId':order,'exchangeTradeId':'summary-'+order,
           'securityId':inst.security_id,'transactionType':side,'exchangeSegment':'NSE_FNO',
           'productType':'MARGIN','tradedQuantity':130,'tradedPrice':price,'brokerageCharges':fee,
           **{key:'0' for key in ('sebiTax','stt','serviceTax','exchangeTransactionCharges','stampDuty')}}
          for side,order,price,fee in [('BUY','buy','11','35'),('SELL','sell','14','40')]]
    async def historical(*args):return rows
    broker.historical_trades=historical
    return ledger,broker,rows


def test_historical_summary_confirms_existing_partial_fills_without_minting_more(tmp_path):
    async def run():
        ledger,broker,_=setup(tmp_path);oms=OrderManager(ledger,broker)
        await oms.reconcile();await oms.reconcile()
        assert ledger.db.execute('SELECT count(*) FROM fills').fetchone()[0]==3
        assert ledger.lifecycle_totals('closed')['quantity']==0
        assert ledger.lifecycle_totals('closed')['entry_debit']==D('1465')
        assert ledger.lifecycle_totals('closed')['sale_credit']==D('1780')
        assert ledger.db.execute('SELECT count(*) FROM order_charges').fetchone()[0]==2
        assert broker.requests==[]
    asyncio.run(run())


@pytest.mark.parametrize('field,value',[('securityId','foreign'),('dhanClientId','foreign'),
    ('transactionType','SELL'),('tradedQuantity',65),('tradedPrice','10'),('brokerageCharges','NaN'),('brokerageCharges','-1')])
def test_historical_summary_cannot_override_conflicting_economic_or_account_identity(tmp_path,field,value):
    async def run():
        ledger,broker,rows=setup(tmp_path);rows[0][field]=value
        with pytest.raises((ContractError,ValueError,ArithmeticError)):await OrderManager(ledger,broker).reconcile()
        assert ledger.db.execute('SELECT count(*) FROM fills').fetchone()[0]==3
        assert ledger.db.execute('SELECT count(*) FROM order_charges').fetchone()[0]==0
        assert broker.requests==[]
    asyncio.run(run())


def test_late_lower_fee_receipt_cannot_restore_spent_cash(tmp_path):
    async def run():
        ledger,broker,rows=setup(tmp_path);oms=OrderManager(ledger,broker)
        await oms.reconcile();before=ledger.lifecycle_totals('closed')
        rows[0]['brokerageCharges']='0';rows[1]['brokerageCharges']='0'
        await oms.reconcile()
        assert ledger.lifecycle_totals('closed')==before
    asyncio.run(run())


def test_reported_order_fees_do_not_replace_stricter_existing_cost_estimates(tmp_path):
    async def run():
        ledger,broker,rows=setup(tmp_path)
        rows[0]['brokerageCharges']='1';rows[1]['brokerageCharges']='1'
        before=ledger.lifecycle_totals('closed')
        await OrderManager(ledger,broker).reconcile()
        assert ledger.lifecycle_totals('closed')==before
    asyncio.run(run())


def test_successful_account_reconciliation_clears_only_its_previous_failure(tmp_path):
    from dhan_cas_bot.account_refresh import AccountRefresh
    from tests.test_streaming_runtime import runtime_at
    async def run():
        runtime=runtime_at(tmp_path/'runtime',FakeBroker())
        worker=AccountRefresh(runtime,asyncio.Event(),busy=lambda:False)
        runtime.status.reason='RECOVERY_REQUIRED:ACCOUNT_READ_FAILED'
        await worker.refresh()
        assert runtime.status.reason=='' and runtime.status.current_account_funded
        runtime.status.reason='EXTERNAL_UNMANAGED_POSITION'
        await worker.refresh()
        assert runtime.status.reason=='EXTERNAL_UNMANAGED_POSITION'
    asyncio.run(run())


def test_dashboard_net_result_requires_complete_order_fee_receipts(tmp_path):
    from dhan_cas_bot.dashboard.data import ledger_view
    async def run():
        ledger,broker,_=setup(tmp_path)
        before=ledger_view(ledger.path)['cash_reconciliation']
        assert before['status']=='CHARGES_PENDING' and before['net_after_reported_charges'] is None
        await OrderManager(ledger,broker).reconcile()
        after=ledger_view(ledger.path)['cash_reconciliation']
        assert after['status']=='REPORTED_CHARGES_COMPLETE'
        assert after['gross_pnl']=='390.00' and after['reported_charges']=='75.00'
        assert after['net_after_reported_charges']=='315.00'
        assert after['executed_orders']==after['orders_with_complete_charges']==2
        assert 'summary-buy' not in str(after)
    asyncio.run(run())
