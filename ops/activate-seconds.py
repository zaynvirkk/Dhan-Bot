#!/usr/bin/env python3
"""Operator-run activation of the five experimental seconds strategies."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dhan_cas_bot.config import load_config
from dhan_cas_bot.seconds_strategies import NAMES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--extra-route-attempt-on',default=None)
    args=parser.parse_args();cfg=load_config('/etc/sablestone-dhan/production.toml')
    scanned=list(dict.fromkeys([*cfg['strategies'],*NAMES]))
    funded=list(dict.fromkeys([*cfg.get('funded_strategies',cfg['strategies']),*NAMES]))
    command=[sys.executable,str(ROOT/'ops/activate-profit-exit.py'),'--retain',str(cfg.get('profit_exit_retain','0.50')),
             '--scan-only',*scanned,'--funded-only',*funded]
    if args.apply:command.append('--apply')
    if args.extra_route_attempt_on:command.extend(['--extra-route-attempt-on',args.extra_route_attempt_on])
    raise SystemExit(subprocess.run(command,cwd=ROOT).returncode)


if __name__=='__main__':main()
