#!/usr/bin/env python3
"""Operator-run activation on the dedicated VM; --check-only never enables."""
import argparse
import asyncio
from dataclasses import replace
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import pwd
import shlex
import subprocess
import sys
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dhan_cas_bot.auth import session_token
from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.commissioning import normalize_whitelist
from dhan_cas_bot.config import load_config, load_mandate
from dhan_cas_bot.domain import ContractError, json_safe
from dhan_cas_bot.egress import require_expected_egress
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.release import current_verification, source_digest


def command(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def atomic(path, text, mode, owner=None):
    temporary=path.with_name(path.name+".activation-tmp")
    descriptor=os.open(temporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,mode)
    with os.fdopen(descriptor,"w") as stream:
        stream.write(text); stream.flush(); os.fsync(stream.fileno())
    temporary.chmod(mode)
    if owner: os.chown(temporary,*owner)
    temporary.replace(path)
    descriptor=os.open(path.parent,os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


async def checks(config, state, capital):
    if not current_verification(ROOT,state):
        raise ContractError("current deployed source must pass dhan-cas verify first")
    await require_expected_egress(config["expected_egress_ip"])
    token=await session_token(config,state)
    broker=DhanBroker(config["account_id"],token,config["dhan_api_base"],allow_writes=False)
    try:
        profile=await broker._request("GET","/profile")
        if str(profile.get("dhanClientId")) != config["account_id"] or profile.get("dataPlan")!="Active" or "Derivative" not in profile.get("activeSegment",""):
            raise ContractError("Dhan account identity, derivatives permission or data entitlement failed")
        ips=normalize_whitelist(await broker._request("GET","/ip/getIP"))
        if config["expected_egress_ip"] not in {ips["primary_ip"],ips["secondary_ip"]}:
            raise ContractError("set Dhan primary IP to "+config["expected_egress_ip"]+" before activation")
        if not os.environ.get("UPSTOX_ANALYTICS_TOKEN"):
            raise ContractError("Upstox Analytics Token is missing")
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            response=await client.get(config["upstox_authorize_url"],headers={"Authorization":"Bearer "+os.environ["UPSTOX_ANALYTICS_TOKEN"]})
            response.raise_for_status()
            if not response.json().get("data",{}).get("authorized_redirect_uri"):
                raise ContractError("Upstox feed authorization unavailable")
        funds=await broker.funds()
        if funds.broker_account!=config["account_id"]:
            raise ContractError("cash belongs to another account")
        amount=funds.spendable_cash if capital=="available" else Decimal(capital)
        if not amount.is_finite() or amount<=0 or amount>funds.spendable_cash or amount!=amount.quantize(Decimal("0.01")):
            raise ContractError("allocation must be positive exact paise within current reusable cash")
        positions=await broker.positions()
        orders=await broker.orders()
        if any(int(p.get("netQty",p.get("netQuantity",0))) for p in positions) or any(o.get("orderStatus") not in {"TRADED","CANCELLED","REJECTED","EXPIRED"} for o in orders):
            raise ContractError("first activation requires reconciled flat account and no pending orders")
        return amount
    finally: await broker.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital",required=True,help="exact rupees or 'available' for current reusable broker cash")
    parser.add_argument("--check-only",action="store_true")
    args=parser.parse_args()
    if os.geteuid()!=0 or ROOT != Path("/opt/sablestone-dhan-cas-bot"):
        raise ContractError("run with sudo on the dedicated GCP VM")
    for raw in Path("/etc/sablestone-dhan/secrets.env").read_text().splitlines():
        fields=shlex.split(raw,comments=True)
        if not fields: continue
        if len(fields)!=1 or "=" not in fields[0]: raise ContractError("invalid secrets.env assignment")
        key,value=fields[0].split("=",1); os.environ[key]=value
    config_path=Path("/etc/sablestone-dhan/production.toml")
    config=load_config(config_path); state=Path(config["state_dir"])
    mandate_path=state/"mandate.json"; mandate=load_mandate(mandate_path)
    if config["live_order_authority"] or mandate.live_order_authority:
        raise ContractError("already configured for live authority; use status/disarm, never reset the mandate")
    if not os.environ.get("DHAN_PIN") or not os.environ.get("DHAN_TOTP_SECRET") or os.environ.get("DHAN_ACCESS_TOKEN"):
        raise ContractError("unattended service requires PIN/TOTP with DHAN_ACCESS_TOKEN empty")
    db=sqlite3.connect(f"file:{state / 'ledger.sqlite3'}?mode=ro",uri=True)
    try:
        if db.execute("SELECT 1 FROM intents LIMIT 1").fetchone() or db.execute("SELECT 1 FROM lifecycles LIMIT 1").fetchone():
            raise ContractError("existing trading history cannot be reset by first-activation helper")
    finally: db.close()
    account=pwd.getpwnam("sablestone")
    owner=(account.pw_uid,account.pw_gid)
    try:
        amount=asyncio.run(checks(config,state,args.capital))
    finally:
        for name in ("dhan_token.json","token.lock"):
            if (state/name).exists(): os.chown(state/name,*owner)
    if args.check_only:
        print(json.dumps({"activation_checks_passed":True,"allocated_capital":str(amount),"source_digest":source_digest(ROOT),"enabled":False,"orders_sent":0}))
        return
    # All following effects occur only when the operator runs this command.
    command("systemctl","stop","dhan-cas.service")
    descriptor=os.open(state/"writer.lock",os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        amended=replace(mandate,allocated_capital=amount,live_order_authority=True)
        amended.validate()
        data=json.loads(mandate_path.read_text())
        data.update(allocated_capital=str(amount),live_order_authority=True)
        atomic(mandate_path,json.dumps(data,indent=2)+"\n",0o600,owner)
        lines=config_path.read_text().splitlines()
        lines=["live_order_authority = true" if line.strip().startswith("live_order_authority =") else line for line in lines]
        atomic(config_path,"\n".join(lines)+"\n",0o640,(0,account.pw_gid))
        ledger=Ledger(state/"ledger.sqlite3")
        try:
            ledger.put_mandate(amended)
            ledger.put_metadata("disarmed",False)
            ledger.put_metadata("activation",{"source_digest":source_digest(ROOT),"allocated_capital":str(amount)})
        finally: ledger.close()
        override=Path("/etc/systemd/system/dhan-cas.service.d")
        override.mkdir(parents=True,exist_ok=True)
        atomic(override/"90-operator-live.conf","[Service]\nUnsetEnvironment=DHAN_BROKER_READ_ONLY\n",0o644)
    finally: os.close(descriptor)
    command("systemctl","disable","--now","dhan-cas-session-refresh.timer")
    command("systemctl","daemon-reload")
    command("systemctl","reset-failed","dhan-cas.service")
    command("systemctl","enable","--now","dhan-cas.service")
    print(json.dumps({"enabled":True,"allocated_capital":str(amount),"automatic_probe":"expiry day 15:05–15:19:30 IST", "route_proof":"required before entries"}))


if __name__=="__main__":
    try: main()
    except Exception as exc:
        # Provider exceptions may contain URL credentials; print only the class.
        print(str(exc) if isinstance(exc,ContractError) else type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
