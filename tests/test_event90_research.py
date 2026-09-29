import io
import unittest
import zipfile

from research.event90.experiment import merge_rows,read_daily,parse_ban
from research.event90.report import assert_parity,rank_bounds


class EventExtensionTests(unittest.TestCase):
    def test_ban_record_requires_date_and_explicit_contents(self):
        body='Securities in Ban For Trade Date 22-JUN-2026:\n1,KAYNES\n'
        self.assertEqual(parse_ban(body,'2026-06-22'),['KAYNES'])
        with self.assertRaises(ValueError):parse_ban(body,'2026-06-23')
        with self.assertRaises(ValueError):parse_ban(body.splitlines()[0],'2026-06-22')
        self.assertEqual(parse_ban(body.splitlines()[0]+'\nNIL','2026-06-22'),[])

    def test_archive_must_match_requested_trade_date(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:z.writestr('archive.csv','TradDt,TckrSymb\n2026-06-22,TEST\n')
        self.assertEqual(read_daily(stream.getvalue(),'2026-06-22')[0]['TckrSymb'],'TEST')
        with self.assertRaises(ValueError):read_daily(stream.getvalue(),'2026-06-23')

    def test_candle_merge_rejects_conflicting_provider_observations(self):
        row=['2026-06-22T09:15:00+05:30',100,102,99,101,1000,100]
        self.assertEqual(merge_rows([row,row]),[row])
        conflict=list(row);conflict[4]=102
        with self.assertRaises(ValueError):merge_rows([row,conflict])

    def test_unresolved_controls_widen_rank_bounds(self):
        paths=[{'terminal_conditional_cash':'12000'}, {'terminal_conditional_cash':'5000'},
               {'terminal_conditional_cash':None}]
        rank=rank_bounds('10000',paths)
        self.assertEqual(rank['lower'],.5)
        self.assertEqual(rank['upper'],.75)
        self.assertIsNone(rank_bounds(None,paths))

    def test_parity_checks_signal_identity_and_cash_not_just_profit(self):
        ref={'ledger':[{'signal':{'id':'A'},'status':'NO_ORDER','cash_before':'9411.18'}],
             'last_resolved_cash':'9411.18'}
        fast={'ledger':[{'id':'A','status':'NO_ORDER','cash_before':'9411.18'}],
              'last_resolved_cash':'9411.18'}
        assert_parity(ref,fast)
        fast['ledger'][0]['id']='B'
        with self.assertRaises(ValueError):assert_parity(ref,fast)


if __name__=='__main__':unittest.main()
