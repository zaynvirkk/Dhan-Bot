from datetime import timedelta
from decimal import Decimal as D
from dataclasses import replace

from dhan_cas_bot.seconds_paper import PaperLab
from dhan_cas_bot.seconds_strategies import NAMES, opportunity
from tests.test_seconds_strategies import NOW, book


def test_delayed_market_cannot_create_a_fill_at_the_old_ask():
    lab=PaperLab(D(7805),delay_seconds=1)
    sample=opportunity(NAMES[0],NOW,book(),D(105),D(23000),'one')
    lab.step(NOW,{NAMES[0]:sample},{'1':book()},D(23000))
    assert lab.rows[NAMES[0]]['entries']==0
    later=NOW+timedelta(seconds=1)
    lab.step(later,{NAMES[0]:sample},{'1':book(later,bid='101.9',ask='102')},D(23000))
    assert lab.rows[NAMES[0]]['entries']==0
    assert lab.rows[NAMES[0]]['missed']==1


def test_simulated_entry_and_exit_deduct_costs_and_are_not_broker_fills():
    lab=PaperLab(D(7805),delay_seconds=1)
    sample=opportunity(NAMES[0],NOW,book(),D(105),D(23000),'one')
    lab.step(NOW,{NAMES[0]:sample},{'1':book()},D(23000))
    at=NOW+timedelta(seconds=1)
    lab.step(at,{NAMES[0]:sample},{'1':book(at)},D(23000))
    assert lab.rows[NAMES[0]]['entries']==1
    at+=timedelta(seconds=1)
    lab.step(at,{}, {'1':book(at,bid='105',ask='105.1')},D(23000))
    at+=timedelta(seconds=1)
    lab.step(at,{}, {'1':book(at,bid='105',ask='105.1')},D(23000))
    row=lab.rows[NAMES[0]]
    assert row['closed']==1 and D(row['net'])>0
    assert D(row['net'])<D('4.9')*65
    assert lab.view()['writes_to_broker'] is False
