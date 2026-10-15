const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const sandbox=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dhan_cas_bot/dashboard/static/stream.js'),'utf8'),sandbox);
const Stream=vm.runInContext('DashboardStream',sandbox);
let now=0,refreshes=0,signedOut=0,messages=0;
const connections=[];
const source=()=>{const c={closed:false,addEventListener(name,fn){this[name]=fn;},close(){this.closed=true;}};connections.push(c);return c;};
const stream=new Stream({source,now:()=>now,refresh:()=>refreshes++,signIn:()=>signedOut++,onData:()=>messages++});
stream.start();stream.start();assert.equal(connections.length,1);assert.equal(refreshes,1);
for(let i=1;i<=15;i++){now=i*1000;connections[0].onmessage({data:'{"available":true}'});stream.tick();}
assert.equal(refreshes,1,'Healthy push replaces 5-second polls');
assert.equal(messages,15);
now=22000;stream.tick();assert.equal(refreshes,2,'Silent stream falls back');
connections[0].onerror();assert.equal(refreshes,2,'Errors are rate limited');
now=28000;connections[0].onmessage({data:'broken'});assert.equal(refreshes,3);
stream.stop();now=40000;stream.tick();assert.equal(refreshes,3);assert.equal(connections[0].closed,true);
stream.start();assert.equal(connections.length,2);assert.equal(refreshes,4);
connections[0].onmessage({data:'{"available":true}'});assert.equal(messages,15,'Closed stream cannot overwrite newer state');
connections[1]['auth-required']();assert.equal(signedOut,1);assert.equal(stream.running,false);
const fallback=new Stream({source:()=>{throw new Error('No EventSource');},now:()=>now,refresh:()=>refreshes++,signIn:()=>{},onData:()=>{}});
fallback.start();now+=6000;fallback.tick();assert.equal(refreshes,6,'Polling works without EventSource');
console.log('SSE browser lifecycle: push, rate-limited fallback, pause/resume, expiry verified');
// Execute the actual page script with a small DOM boundary, including the
// unknown/stale path. No browser/network process is required by this test.
class Element {
 constructor(){this.textContent='';this.children=[];this.value='all';this.dataset={};this.classList={add(){},remove(){}};}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=[...children];}
 addEventListener(){}
 setAttribute(){}
 removeAttribute(){}
 querySelectorAll(selector){
  assert.equal(selector,'details.strategy-family[open]');
  const out=[];const visit=n=>{if((n.className||'').split(' ').includes('strategy-family')&&n.open)out.push(n);for(const c of n.children||[])visit(c);};
  for(const n of this.children)visit(n);return out;
 }
}
const ids={};
const html=fs.readFileSync(path.join(__dirname,'../dhan_cas_bot/dashboard/static/index.html'),'utf8');
for(const match of html.matchAll(/id="([^"]+)"/g))ids[match[1]]=new Element();
let failFetch;
const browser=vm.createContext({console,Intl,Date,BigInt,Node:Element,structuredClone,
 document:{hidden:true,getElementById(id){assert.ok(ids[id],`Missing HTML ID ${id}`);return ids[id];},createElement(){return new Element();},querySelectorAll(){return [];},addEventListener(){}},
 window:{addEventListener(){},location:{replace(){}}},navigator:{},setInterval(){},setTimeout(){},AbortSignal:{timeout(){}},
 fetch:()=>new Promise((resolve,reject)=>{failFetch=reject;})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dhan_cas_bot/dashboard/static/stream.js'),'utf8'),browser);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dhan_cas_bot/dashboard/static/app.js'),'utf8'),browser);
assert.equal(vm.runInContext("details({name:'dhan_account',status:'PASS',facts:{positions:2,open_positions:0,orders:66}})",browser), '0 open positions · 2 position records · 66 orders');
assert.equal(vm.runInContext("details({name:'dhan_account',status:'PASS',facts:{positions:2,orders:66}})",browser), 'Open-position count unavailable · 2 position records · 66 orders');
vm.runInContext('render({available:false})',browser);
assert.equal(ids.authority.textContent,'Trading status unknown');
vm.runInContext(`render({available:true,server_time:'2026-10-01T09:00:00Z',collector:{fresh:true},account_read_ok:true,
 runtime:{fresh:true,authority:'ENABLED',telemetry:{latency:{http_ack_ms:{p95:'12.00',samples:3}},decision_counts:{EMPTY_BOOK:4}}},
 account:{fresh:true,available_cash:'9411.18',positions:[],orders:[]}})`,browser);
assert.equal(ids.cash.textContent,'₹9,411.18');assert.equal(ids.timings.children.length,1);
// A delayed failed GET must not erase a newer stream observation.
vm.runInContext('refresh()',browser);
vm.runInContext(`render({available:true,server_time:'2026-10-01T09:00:01Z',collector:{fresh:true},account_read_ok:true,runtime:{fresh:true,authority:'ENABLED'}})`,browser);
const authority=ids.authority.textContent;
failFetch(new Error('Delayed GET failure'));
setImmediate(()=>{assert.equal(ids.authority.textContent,authority);console.log('Page rendering and out-of-order status recovery verified');});
setImmediate(()=>{
// Historical diagnostics must not be mistaken for live feed health.
const stamp='2026-10-01T09:01:00Z';
const current={available:true,server_time:stamp,collector:{fresh:true},account_read_ok:true,
 runtime:{fresh:true,authority:'ENABLED',monitoring_mode:'IDLE',feed_health:{}},
 connections:{fresh:false,observed_at:'2026-09-29T09:20:00Z',checks:[{name:'dhan_market_feed',status:'FAIL'}]}};
for(const name of ['signal','market','order'])current.runtime.feed_health[name]={connected:true,reconnects:0,pending_messages:0,last_received_at:null,last_usable_at:null};
let viewTime=Date.parse(stamp);
function show(value){viewTime+=1000;browser.fixture={...value,server_time:new Date(viewTime).toISOString()};vm.runInContext('render(fixture)',browser);}
show(current);
assert.match(ids.notice.textContent,/idle session/);
assert.ok(!ids.notice.textContent.includes('Connection checks are old'));
assert.equal(ids['live-connections'].children.length,3);
const diagnostics=ids.connections.children[0];
show({...current,server_time:'2026-10-01T09:01:01Z'});
assert.equal(ids.connections.children[0],diagnostics,'Unchanged diagnostics preserve DOM');
show({...current,runtime:{...current.runtime,monitoring_mode:'ACTIVE'}});
assert.match(ids.notice.textContent,/Waiting for fresh usable market data/);
// A frozen CTS reference is not a stopped live feed. Auction values remain
// separate eligibility evidence even while current frames keep arriving.
const auctionPending=structuredClone(current);
auctionPending.runtime.monitoring_mode='ACTIVE';
auctionPending.runtime.observation={phase:'CTS_CLOSE',reference:'22700.75',iep:null};
for(const key of ['signal','market'])auctionPending.runtime.feed_health[key]={connected:true,reconnects:0,pending_messages:0,last_received_at:new Date(viewTime+1000).toISOString(),last_processed_at:new Date(viewTime+1000).toISOString(),last_usable_at:key==='market'?new Date(viewTime+1000).toISOString():null};
show(auctionPending);
assert.match(ids.notice.textContent,/Live feeds are receiving data/);
assert.match(ids.notice.textContent,/official indicative index value/);
assert.equal(ids.notice.hidden,true,'Expected missing auction input must not become a feed outage');
assert.match(ids['live-connections'].children[0].children[1].textContent,/Receiving frames/);
const auctionClosed=structuredClone(auctionPending);
auctionClosed.runtime.observation.phase='CAS_STOP';
auctionClosed.runtime.strategies=['CAS_LAG_V1'];
auctionClosed.runtime.expiry_today=true;
show(auctionClosed);
assert.match(ids.notice.textContent,/provider has closed auction entries/);
assert.equal(ids.notice.hidden,true,'A closed auction must not become a stopped-feed warning');
assert.equal(ids['strategy-checks'].children[0].children[1].textContent,'Closed');
assert.match(ids['strategy-checks'].children[0].children[0].children.map(c=>c.textContent).join(' '),/Provider reports the auction closed/);
const signalSilent=structuredClone(auctionPending);
signalSilent.runtime.feed_health.signal.last_processed_at='2026-10-01T08:00:00Z';
signalSilent.runtime.feed_health.signal.last_received_at='2026-10-01T08:00:00Z';
show(signalSilent);
assert.match(ids.notice.textContent,/Waiting for fresh usable market data/);
assert.equal(ids.notice.hidden,false,'Stopped index frames must still warn');
const bookStale=structuredClone(auctionPending);
bookStale.runtime.feed_health.market.last_usable_at='2026-10-01T08:00:00Z';
show(bookStale);
assert.match(ids.notice.textContent,/Waiting for fresh usable market data/);
assert.equal(ids.notice.hidden,false,'Fresh transport must not hide stale option books');
const disconnected=structuredClone(current);disconnected.runtime.feed_health.order.connected=false;show(disconnected);
assert.match(ids.notice.textContent,/Dhan order updates disconnected/);
assert.equal(ids.notice.hidden,false,'An idle session must not hide a real disconnection');
const marketDown=structuredClone(current);
marketDown.runtime.feed_health.market={connected:false,reconnects:76,pending_messages:0,last_error:'ConnectionClosedError'};
show(marketDown);
assert.match(ids.notice.textContent,/Dhan options feed disconnected/);
assert.doesNotMatch(ids.notice.textContent,/Upstox index feed disconnected/);
assert.match(ids['live-connections'].children[1].children[0].children[1].textContent,/Connection closed/);
assert.match(ids['live-connections'].children[1].children[0].children[1].textContent,/reconnects: 76/);
const noDataPlan=structuredClone(marketDown);
noDataPlan.connections={fresh:true,observed_at:stamp,checks:[{name:'dhan_auth',status:'PASS',facts:{data_plan:'Inactive',derivatives_enabled:true}}]};
show(noDataPlan);
assert.match(ids.notice.textContent,/Dhan reports an inactive data subscription/);
assert.match(ids.notice.textContent,/Data APIs in DhanHQ/);
noDataPlan.connections.fresh=false;show(noDataPlan);
assert.match(ids.notice.textContent,/Last Dhan check reported an inactive data subscription/);
noDataPlan.connections.fresh=true;noDataPlan.connections.checks[0].facts.data_plan='Active';show(noDataPlan);
assert.doesNotMatch(ids.notice.textContent,/inactive data subscription/,'An active plan must not retain a historical inactive label');
show({...marketDown,runtime:{...marketDown.runtime,fresh:false}});
assert.match(ids.notice.textContent,/bot status is stale or missing/,'Old disconnection must not claim current health');
show(current);
assert.equal(ids.notice.hidden,true,'A fresh recovery clears the incident notice');
const delayed=structuredClone(current);delayed.runtime.feed_health.market.oldest_pending_ms=1500;show(delayed);
assert.match(ids.notice.textContent,/processing is delayed/);
show({...current,runtime:{fresh:true,authority:'ENABLED'}});
assert.match(ids.notice.textContent,/unavailable from the deployed version/);
show({...current,collector:{fresh:false}});
assert.match(ids.notice.textContent,/stale/);
assert.equal(ids.authority.textContent,'Trading status unknown');
// Decision board reports actual state and never promotes missing inputs to zero.
const inputs={phase:'CAS_LM_START',phase_at:stamp,iep:'24060.00',reference:'24000.00',direction:'CE',iep_at:stamp,expiry:'2026-10-06T00:00:00+05:30',watchlist:[]};
show({...current,runtime:{...current.runtime,state:'NO_TRADE_DAY',observation:inputs}});
assert.equal(ids['now-title'].textContent,'Waiting for an expiry session');
assert.match(ids['next-step'].textContent,/06 Oct/);
assert.equal(ids.notice.hidden,true,'Healthy routine notices do not occupy the overview');
assert.equal(ids['watch-table'].hidden,true,'No empty table scaffolding');
assert.equal(ids['reference-value'].textContent,'24,000.00');
assert.match(ids['signal-direction'].textContent,/last observed/,'Old IEP is not presented as fresh direction');
show({...current,runtime:{...current.runtime,state:'POSITION_OPEN',monitoring_mode:'ACTIVE',reason:'Holding the position',observation:inputs}});
assert.equal(ids['now-title'].textContent,'Managing an open position');
show({...current,collector:{fresh:false},runtime:{...current.runtime,state:'POSITION_OPEN',observation:inputs}});
assert.equal(ids['now-title'].textContent,'Current bot state is unknown');
assert.equal(ids.notice.hidden,false);
show({...current,runtime:{...current.runtime,state:'ARMED_WAITING_SIGNAL',observation:null}});
assert.equal(ids['signal-value'].textContent,'—');
assert.equal(ids['signal-direction'].textContent,'Awaiting signal');
assert.match(ids['watch-empty'].textContent,/not available/);
console.log('Decision-first layout, stale signals and empty observations verified');
// Pre-auction prices are visible without becoming auction values or a trade signal.
const preAuction={...inputs,iep:null,iep_at:null,direction:null,reference:null,phase:null,ltp:'24123.50',ltp_at:stamp,ltp_received_at:stamp};
show({...current,runtime:{...current.runtime,state:'ARMED_WAITING_SESSION',observation:preAuction}});
assert.equal(ids['index-value'].textContent,'24,123.50');
assert.equal(ids['signal-value'].textContent,'—');
assert.equal(ids['signal-direction'].textContent,'Awaiting signal');
assert.match(ids['index-age'].textContent,/Last observed/);
assert.match(ids['next-step'].textContent,/15:05/);
assert.match(ids['input-feeds'].textContent,/no message observed/);
show({...current,runtime:{...current.runtime,state:'POSITION_OPEN',observation:preAuction}});
assert.equal(ids['now-title'].textContent,'Managing an open position','Idle monitoring cannot hide position management');
show({...current,collector:{fresh:false},runtime:{...current.runtime,observation:preAuction}});
assert.match(ids['input-feeds'].textContent,/unknown/);
assert.match(ids['history-summary'].textContent,/no monitoring history/);
// A recorded no-trade-day is not proof of zero fills; missing days stay unknown.
const history={status:'AVAILABLE',started_at:stamp,days:[{date:'2026-10-01',first_at:stamp,last_at:stamp,samples:1,unknown_samples:0,gaps:0,states:['NO_TRADE_DAY']}],events:[{at:stamp,state:'NO_TRADE_DAY',source_current:true,ltp:'24123.50',ltp_at:stamp,iep:null,books:2,feeds:{signal:true,market:true,order:true}}]};
show({...current,history});
assert.equal(ids['history-events'].children.length,1);
assert.match(ids['history-summary'].textContent,/1 monitoring samples/);
assert.match(ids['history-coverage'].textContent,/Not an eligible expiry session/);
const closedHistory={...history,days:[{...history.days[0],states:['WAITING_EXCHANGE_SESSION']}],events:[{...history.events[0],state:'WAITING_EXCHANGE_SESSION',reason:'No contract passes the price, depth, fees and remaining capital checks.'}]};
show({...current,history:closedHistory});
assert.match(ids['history-coverage'].textContent,/Waiting for an exchange session/);
const closedHistoryText=ids['history-events'].children[0].children[1].children.map(n=>n.textContent).join(' ');
assert.match(closedHistoryText,/No new entries while waiting for an exchange session/);
assert.match(closedHistoryText,/Last recorded execution note: No contract passes/,'An older execution note is not a current closed-session entry blocker');
show({...current,history_unchanged:true});
assert.equal(ids['history-events'].children.length,1,'Compact quote updates retain existing history');
vm.runInContext("state.historyDate='2026-09-30'; renderHistory(state.data)",browser);
assert.match(ids['history-summary'].textContent,/No recorded monitoring coverage/);
assert.match(ids['history-summary'].textContent,/does not establish that no trades/);
assert.equal(ids['history-events'].children.length,0);
show({...current,history:{status:'UNAVAILABLE',days:[],events:[]}});
assert.match(ids['history-summary'].textContent,/could not be read/);
console.log('Pre-auction values, receipt ages, retained history and unknown days verified');
// Pulse marks the dashboard stream alive without rerendering financial data.
let pulses=0;
const pulseStream=new Stream({source,now:()=>now,refresh:()=>{},signIn:()=>{},onData:()=>{},onTime:()=>pulses++});
pulseStream.start();const pulseConnection=connections.at(-1);
pulseConnection.pulse({data:JSON.stringify({server_time:stamp})});
assert.equal(pulses,1);
pulseStream.stop();pulseConnection.pulse({data:JSON.stringify({server_time:stamp})});
assert.equal(pulses,1,'Closed connections cannot refresh health');
console.log('Live health, idle silence, diagnostics, stale sources and stable DOM verified');

});

setImmediate(()=>{
 const f={available:true,server_time:'2026-10-06T05:00:00Z',collector:{fresh:true},
 runtime:{fresh:true,authority:'ENABLED',state:'ARMED_WAITING_SIGNAL',monitoring_mode:'ACTIVE',
 strategies:['GAP_FADE_DOUBLE','NIFTY_SELLOFF_REBOUND_1510','CAS_LAG_V1'],expiry_today:true,
 strategy_evaluations:[{strategy:'GAP_FADE_DOUBLE',state:'NOT_APPLICABLE',enabled:true,reason:'EXPIRY_SESSION_OUTSIDE_RESEARCH_SCOPE'},
 {strategy:'NIFTY_SELLOFF_REBOUND_1510',state:'WAITING',enabled:true,reason:'OUTSIDE_STRATEGY_WINDOW'}]}};
 browser.strategiesFixture=f;vm.runInContext('render(strategiesFixture)',browser);
 assert.equal(ids['strategy-checks'].children.length,3);
 assert.equal(ids['now-title'].textContent,'Watching configured strategies');
 assert.ok(!ids['next-step'].textContent.includes('auction value'));
 f.daily_monitor={fresh:true,observed_at:f.server_time,mode:'READ_ONLY',writes_to_broker:false,
  strategy_evaluations:[{strategy:'GAP_FADE_DOUBLE',state:'NO_SIGNAL',reason:'GAP_FADE_CONDITIONS_NOT_MET'}]};
 vm.runInContext('render(strategiesFixture)',browser);
 assert.equal(ids['strategy-checks'].children.length,3,'Observer must not duplicate funded strategy rows');
 assert.ok(!ids['strategy-mode'].textContent.includes('cannot submit orders'),'Funded strategy rows must not be described as read-only');
 f.runtime.software_verified=false;
 vm.runInContext('render(strategiesFixture)',browser);
 assert.match(ids['now-title'].textContent,/blocked by software verification/,'A software entry blocker must not look like ordinary signal waiting');
 assert.equal(ids.authority.textContent,'Trading authority enabled','Standing permission is not entry readiness');
 f.runtime.software_verified=true;
 vm.runInContext('render(strategiesFixture)',browser);
 assert.equal(ids['now-title'].textContent,'Funded trader: watching configured strategies');
 f.server_time='2026-10-06T05:00:01Z';f.runtime.fresh=false;
 vm.runInContext('render(strategiesFixture)',browser);
 for(const row of ids['strategy-checks'].children)assert.equal(row.children[1].textContent,'Unknown');
 console.log('Multiple strategy checks and stale demotion verified');
});

setImmediate(()=>{
 const stamp='2026-10-09T04:15:00Z';
 browser.monitorFixture={available:true,server_time:stamp,collector:{fresh:true},account_read_ok:true,
  runtime:{fresh:true,authority:'DISABLED',state:'NO_TRADE_DAY',strategies:[]},
  daily_monitor:{fresh:true,observed_at:stamp,mode:'READ_ONLY',writes_to_broker:false,
   strategy_evaluations:[{strategy:'GAP_FADE_DOUBLE',state:'SIGNAL',reason:'GAP_FADE_CONFIRMED',side:'CE',evaluated_at:stamp}]}};
 vm.runInContext('render(monitorFixture)',browser);
 assert.equal(ids.authority.textContent,'New entries disabled','Observer signal must not enable trading');
 assert.match(ids['strategy-mode'].textContent,/cannot submit orders/);
 assert.match(ids['strategy-checks'].children[0].children[0].children[1].textContent,/Read-only monitor/);
 browser.monitorFixture.server_time='2026-10-09T04:17:00Z';
 vm.runInContext('render(monitorFixture)',browser);
 assert.equal(ids['strategy-checks'].children[0].children[1].textContent,'Unknown','Stale observer signal must be demoted');
 console.log('Daily observer labels, authority isolation and stale signals verified');
});

setImmediate(()=>{
 const stamp='2026-10-09T04:20:00Z';
 const conditions=[{key:'gap_size',state:'FAIL',value:'.0032',minimum:'.005'},
  {key:'persistence',state:'FAIL',expected:'RISING'},
  {key:'futures_direction',state:'UNKNOWN',value:null,expected:'RISING'}];
 browser.explained={available:true,server_time:stamp,collector:{fresh:true},runtime:{fresh:true,authority:'DISABLED'},
  daily_monitor:{fresh:true,observed_at:stamp,mode:'READ_ONLY',writes_to_broker:false,
   strategy_evaluations:[{strategy:'GAP_FADE_DOUBLE',state:'NO_SIGNAL',reason:'GAP_FADE_CONDITIONS_NOT_MET',evaluated_at:stamp,conditions,next_check_at:'2026-10-09T04:25:00Z'}]}};
 vm.runInContext('render(explained)',browser);
 let row=ids['strategy-checks'].children[0];
 assert.match(row.children[0].children[2].textContent,/Opening gap, Price persistence not met/);
 assert.match(row.children[0].children.map(c=>c.textContent).join(' '),/Next scheduled check/);
 const detail=row.children.find(c=>c.children?.[0]?.textContent?.startsWith('Why this decision'));
 let list=detail?.children[1];
 assert.ok(list,'Observed conditions have a visible list');
 assert.match(list.children[0].children[0].children[1].textContent,/0.32%.*0.50%/);
 assert.equal(list.children[2].children[1].textContent,'Unavailable');
 const last=structuredClone(browser.explained.daily_monitor.strategy_evaluations[0]);
 browser.explained.server_time='2026-10-09T04:21:00Z';
 browser.explained.daily_monitor.observed_at=browser.explained.server_time;
 browser.explained.daily_monitor.last_decisions=[last];
 Object.assign(browser.explained.daily_monitor.strategy_evaluations[0],{state:'WAITING',reason:'OUTSIDE_STRATEGY_WINDOW',evaluated_at:browser.explained.server_time});
 vm.runInContext('render(explained)',browser);
 row=ids['strategy-checks'].children[0];
 assert.match(row.children[0].children.map(c=>c.textContent).join(' '),/Last completed decision.*Opening gap, Price persistence not met/);
 const retained=row.children.find(c=>c.children?.[0]?.textContent?.startsWith('Inputs at the last decision'));
 assert.ok(retained,'Previous decision values remain inspectable between scheduled checks');
 assert.match(retained.children[1].children[0].children[0].children[1].textContent,/0.32%.*0.50%/);
 // Older monitor decisions have numeric details but no condition rows.
 const legacy=browser.explained.daily_monitor.last_decisions[0];
 legacy.conditions=[];
 legacy.details={gap:'-.000176967',fraction_filled:'-65.225',persistent:false,future_5m_return:'-.002885'};
 vm.runInContext('render(explained)',browser);
 row=ids['strategy-checks'].children[0];
 const legacyDetail=row.children.find(c=>c.children?.[0]?.textContent?.startsWith('Inputs at the last decision'));
 assert.ok(legacyDetail,'Earlier version decisions must retain inspectable numeric inputs');
 assert.match(legacyDetail.children[1].textContent,/Opening gap: -0.02%/);
 assert.match(legacyDetail.children[1].textContent,/Persistence: failed/);
 console.log('Visible failed conditions, exact thresholds, next check and retained decision verified');
});

setImmediate(()=>{
 const stamp='2026-10-12T07:00:00Z';
 browser.moneyFixture={available:true,server_time:stamp,collector:{fresh:true},account:{fresh:true,available_cash:'8822.36',open_position_count:0},ledger:{available:true,counts:{fills:0}},runtime:{fresh:true,authority:'ENABLED',software_verified:true,broker_route_verified:false,state:'ARMED_WAITING_SIGNAL',strategies:['GAP_FADE_DOUBLE']}};
 vm.runInContext('render(moneyFixture)',browser);
 assert.match(ids['now-title'].textContent,/Not entering trades.*order route unverified/);
 browser.moneyFixture.runtime.route_attempts_used=1;browser.moneyFixture.runtime.route_attempt_limit=1;
 vm.runInContext('render(moneyFixture)',browser);
 assert.match(ids['next-step'].textContent,/1 of 1.*No further attempt/);
 browser.moneyFixture.runtime.route_attempt_limit=2;
 vm.runInContext('render(moneyFixture)',browser);
 assert.match(ids['next-step'].textContent,/1 of 2.*bounded automatic check/);
 assert.equal(ids['fill-count'].textContent,'0');
 assert.match(ids['fill-note'].textContent,/No fills recorded/);
 assert.equal(ids['pnl-unreported'].hidden,false);
 browser.moneyFixture.ledger={available:false};
 browser.moneyFixture.runtime.state='POSITION_OPEN';
 browser.moneyFixture.runtime.reason='No specific decision reason was recorded.';
 vm.runInContext('render(moneyFixture)',browser);
 assert.equal(ids['fill-count'].textContent,'—','Unavailable execution records must not imply zero fills');
 assert.equal(ids['now-title'].textContent,'Managing an open position','Route blocker must not hide position management');
 assert.match(ids['now-reason'].textContent,/monitoring its recorded exit rules/);
 browser.moneyFixture.runtime.fresh=false;
 vm.runInContext('render(moneyFixture)',browser);
 assert.equal(ids['now-title'].textContent,'Current bot state is unknown','Stale route observations cannot establish current blockage');
});

setImmediate(()=>{
 browser.signalHistory={server_time:'2026-10-13T05:00:00Z',runtime:{fresh:true,strategies:['NIFTY_SELLOFF_REBOUND_1510'],strategy_evaluations:[{strategy:'NIFTY_SELLOFF_REBOUND_1510',state:'WAITING',reason:'OUTSIDE_STRATEGY_WINDOW'}]},ledger:{last_signals:[{strategy:'NIFTY_SELLOFF_REBOUND_1510',side:'CE',evaluated_at:'2026-10-12T09:40:00Z',outcome:'ENTRY_DEADLINE_MISSED',blocking_reason:'UNKNOWN',candidate_checks:[]}]}};
 vm.runInContext('renderStrategies(signalHistory)',browser);
 let row=ids['strategy-checks'].children[0];
 assert.equal(row.children[1].textContent,'Waiting','Historical signal must not look like a current trade');
 let text=row.children[0].children.map(c=>c.textContent).join(' ');
 assert.match(text,/Last qualifying signal \(historical\).*CALL/);
 assert.match(text,/entry window expired.*Prior blocking reason was not recorded/);
 browser.signalHistory.ledger.last_signals[0].blocking_reason='OPTION_BOOK_UNAVAILABLE_OR_STALE';
 browser.signalHistory.ledger.last_signals[0].candidate_checks=[{strike:'22550.00',budget:'8381.24',one_lot_cash:'9000.00',reason:'ONE_LOT_UNAFFORDABLE'}];
 vm.runInContext('renderStrategies(signalHistory)',browser);
 row=ids['strategy-checks'].children[0];
 assert.match(row.children[0].children.map(c=>c.textContent).join(' '),/no current usable quote/);
 const detail=row.children[0].children.find(c=>c.children?.[0]?.textContent==='Contracts checked for this entry');
 assert.match(detail.children[1].textContent,/One lot exceeds.*9,000.00.*8,381.24/);
 browser.signalHistory.ledger.last_signals[0].outcome='DECISION_COMMITTED';
 vm.runInContext('renderStrategies(signalHistory)',browser);
 assert.ok(!ids['strategy-checks'].children[0].children[0].children.some(c=>c.children?.[0]?.textContent==='Contracts checked for this entry'),'A committed order must not present an earlier failed retry as its final assessment');
 console.log('Historical qualifying signal, unknown legacy blocker and candidate costs verified');
});

setImmediate(async()=>{
 const requests=[];
 browser.fetch=async url=>{requests.push(url);return {ok:true,status:200,json:async()=>({available:true,server_time:new Date().toISOString(),collector:{fresh:true},history:url.includes('?')?undefined:{status:'AVAILABLE',days:[],events:[]},history_unchanged:url.includes('?')})};};
 vm.runInContext('state.fetching=false;state.historyFetchedAt=null',browser);
 await vm.runInContext('refresh()',browser);
 await vm.runInContext('refresh()',browser);
 assert.deepEqual(requests,['/api/status','/api/status?history=omit']);
 assert.equal(vm.runInContext('state.data.history.status',browser),'AVAILABLE','Compact updates must preserve the journal');
 vm.runInContext('state.historyFetchedAt=Date.now()-61000',browser);
 await vm.runInContext('refresh()',browser);
 assert.equal(requests[2],'/api/status','Journal must refresh after one minute');
 const newest=new Date(Date.now()+1000).toISOString();
 browser.newest=newest;
 vm.runInContext('render({available:true,server_time:newest,collector:{fresh:true},runtime:{fresh:true,authority:"ENABLED"}});state.historyFetchedAt=null',browser);
 browser.fetch=async()=>({ok:true,status:200,json:async()=>({available:true,server_time:new Date(Date.now()-1000).toISOString(),history:{status:'UNAVAILABLE',days:[],events:[]},runtime:{fresh:true,authority:'DISABLED'}})});
 await vm.runInContext('refresh()',browser);
 assert.equal(ids.authority.textContent,'Trading authority enabled','Older history response must not replace newer live authority');
 assert.equal(vm.runInContext('state.data.history.status',browser),'UNAVAILABLE','An older journal response must still update history accurately');
 console.log('Compact refresh, retained journal and periodic full refresh verified');
});

setImmediate(()=>{
 const base={available:true,collector:{fresh:true},runtime:{fresh:true},account_read_ok:false};
 const feeds={issues:[],known:3,idle:true};
 browser.noticeFixture={...base,account_error:'ACCOUNT_OBSERVATION_STALE'};browser.noticeFeeds=feeds;
 assert.match(vm.runInContext('monitoringNotice(noticeFixture,noticeFeeds).text',browser),/last successful account check is stale/);
 assert.ok(!vm.runInContext('monitoringNotice(noticeFixture,noticeFeeds).text',browser).includes('failed'));
 browser.noticeFixture={...base,account_error:'BROKER_READ_FAILED'};
 assert.match(vm.runInContext('monitoringNotice(noticeFixture,noticeFeeds).text',browser),/read failed.*fresh reconciliation/);
 browser.noticeFixture={...base,account_read_ok:true,runtime:{fresh:true,account_snapshot_fresh:false}};
 assert.match(vm.runInContext('monitoringNotice(noticeFixture,noticeFeeds).text',browser),/trader reconciliation is stale or incomplete/);
 browser.cashFixture={available:true,collector:{fresh:true},runtime:{fresh:true},ledger:{cash_reconciliation:{
  status:'REPORTED_CHARGES_COMPLETE',gross_pnl:'2791.75',reported_charges:'1082.39',net_after_reported_charges:'1709.36',closed_trades:16}}};
 vm.runInContext('render(cashFixture)',browser);
 assert.equal(ids['cash-reconciliation'].hidden,false);
 assert.match(ids['cash-reconciliation'].textContent,/2,791.75.*1,082.39.*1,709.36/);
 browser.cashFixture.ledger.cash_reconciliation={status:'CHARGES_PENDING',gross_pnl:'2791.75',orders_with_complete_charges:31,executed_orders:32};
 vm.runInContext('render(cashFixture)',browser);
 assert.match(ids['cash-reconciliation'].textContent,/31 of 32.*net profit is not yet confirmed/);
 console.log('Actual failure versus stale success, trader reconciliation blocker and cost-complete results verified');
});

setImmediate(()=>{
 browser.candleFixture={available:true,collector:{fresh:true},account_read_ok:true,server_time:'2026-10-14T05:20:10Z',
  runtime:{fresh:true,strategies:[],input_health:{fresh:true,spot:{latest_completed:'2026-10-14T05:20:00Z',current_complete:true,missing_minutes:0},
   future:{latest_completed:'2026-10-14T05:20:00Z',current_complete:true,missing_minutes:1,first_missing:'2026-10-14T05:19:00Z'},options:{requested:10,ready:8}}}};
 browser.candleFeeds={known:3,issues:[],idle:false};
 assert.match(vm.runInContext('monitoringNotice(candleFixture,candleFeeds).text',browser),/required completed candles are missing/);
 vm.runInContext('renderStrategies(candleFixture)',browser);
 assert.match(ids['input-history'].textContent,/Futures:.*1 missing session minute.*8 of 10/);
 browser.candleFixture.runtime.input_health.future.missing_minutes=0;
 assert.match(vm.runInContext('monitoringNotice(candleFixture,candleFeeds).text',browser),/observations are current/);
 browser.candleFixture.runtime.input_health.fresh=false;
 vm.runInContext('renderStrategies(candleFixture)',browser);
 assert.match(ids['input-history'].textContent,/readiness is unknown/);
 console.log('Completed candle holes, watched option readiness and stale health verified');
});

setImmediate(()=>{
 browser.selectionFixture={runtime:{fresh:true,state:'ARMED_WAITING_SIGNAL',minute_source:'UPSTOX_COMPLETED_I1_STREAM',
  strategy_selection:{reason:'SELECTED',mode:'MEASURED_CASH_PER_MINUTE',selected:'OPEN_DRIVE_FAST',evaluated_at:new Date().toISOString(),
   candidates:[{strategy:'OPEN_DRIVE_FAST',side:'CE',quantity:65,limit:'10.00',friction_cash:'6.50',estimated_net_profit:'40.00',
    estimated_profit_per_minute:'20.00',holding_minutes:'2',filled_closed:4,sessions:1,
    entry_fill_rate:'.5',mean_entry_fill_fraction:'.25',closed_entry_opportunities:8,filled_entry_opportunities:4,return_standard_error:'.03'}]},
   execution_feedback:[{strategy:'CAS_LAG_V1',filled_closed:16,sessions:1,closed_entry_opportunities:30,
    filled_entry_opportunities:12,entry_fill_rate:'.4',mean_entry_fill_fraction:'.3',mean_estimated_net_return:'.01',return_standard_error:'.028'}]}};
 vm.runInContext('renderSelection(selectionFixture)',browser);
 assert.match(ids['selection-reason'].textContent,/net rupees per holding minute/);
 assert.match(ids['selection-flow'].textContent,/validated Upstox stream/);
 const list=ids['selection-candidates'].children[0];
 assert.match(list.children[1].children[2].textContent,/4 filled closed trades across 1 session/);
 assert.match(list.children[1].children[3].textContent,/50.0%.*25.0%/);
 assert.match(ids['selection-history'].children[0].textContent,/16 filled closed trades.*1 session.*1.00%.*2.80%/);
 browser.selectionFixture.runtime.strategy_selection.reason='CONFLICTING_UNRANKED_SIGNALS';
 browser.selectionFixture.runtime.strategy_selection.selected=null;
 vm.runInContext('renderSelection(selectionFixture)',browser);
 assert.match(ids['selection-reason'].textContent,/No trade was selected/);
 browser.selectionFixture.runtime.state='WAITING_EXCHANGE_SESSION';
 vm.runInContext('renderSelection(selectionFixture)',browser);
 assert.match(ids['selection-reason'].textContent,/exchange session is closed/);
 browser.selectionFixture.runtime.strategy_selection=null;
 vm.runInContext('renderSelection(selectionFixture)',browser);
 assert.ok(!ids['selection-reason'].textContent.includes('retained below'),'A missing comparison must not claim to retain one');
 browser.selectionFixture.runtime.strategy_selection={mode:'WAITING',reason:'NO_EXECUTABLE_SIGNAL',candidates:[]};
 vm.runInContext('renderSelection(selectionFixture)',browser);
 assert.ok(!ids['selection-reason'].textContent.includes('retained below'),'An initialized empty comparison is not a recorded comparison');
 console.log('Cash/time selection, conflict abstention and closed-session explanation verified');

 browser.strategyResults={server_time:'2026-10-14T10:10:00+00:00',runtime:{fresh:true,strategies:['CAS_LAG_V1','ORDINARY_PUBLISHED_PCR_TRAIL'],funded_strategies:['CAS_LAG_V1'],strategy_evaluations:[{strategy:'ORDINARY_PUBLISHED_PCR_TRAIL',state:'WAITING',enabled:true,funded_enabled:false,reason:'EXCHANGE_CLOSED'}],expiry_today:false},ledger:{available:true,strategy_performance:[{strategy:'CAS_LAG_V1',filled_closed:16,gross_pnl:'2791.75',reported_charges:'1082.39',net_pnl:'1709.36',charges_complete:true,trades:[]},{strategy:'ORDINARY_PUBLISHED_PCR_TRAIL',filled_closed:1,gross_pnl:'-2665.00',charges_complete:false,trades:[]}]}};
 vm.runInContext('renderStrategies(strategyResults)',browser);
 assert.match(ids['strategy-mode'].textContent,/1 permitted to trade real money/);
 const content=node=>[node.textContent,...node.children.map(content)].join(' ');
 assert.match(content(ids['strategy-performance']),/1,709.36/);
 assert.match(content(ids['strategy-performance']),/Awaiting final fees/);
 assert.match(content(ids['strategy-checks']),/Observation only/);
 assert.match(content(ids['strategy-checks']),/Real-money entries permitted/);
 console.log('Funded versus observed permissions and actual strategy results verified');
 browser.prunedRoster=structuredClone(browser.strategyResults);
 browser.prunedRoster.runtime.strategies=['CAS_LAG_V1','TREND_PULLBACK_FAST'];
 browser.prunedRoster.runtime.funded_strategies=['CAS_LAG_V1','TREND_PULLBACK_FAST'];
 browser.prunedRoster.runtime.strategy_evaluations.push({strategy:'TREND_PULLBACK_FAST',state:'NO_SIGNAL',enabled:true,funded_enabled:true});
 browser.prunedRoster.daily_monitor={fresh:true,strategy_evaluations:[{strategy:'GAP_FADE_DOUBLE',state:'SIGNAL'}]};
 vm.runInContext('renderStrategies(prunedRoster)',browser);
 assert.equal(ids['strategy-checks'].children.length,2,'A removed engine cannot return through stale checks or a legacy observer');
 assert.doesNotMatch(content(ids['strategy-checks']),/Morning gap-fade|published pcr/);
 assert.match(content(ids['strategy-performance']),/PCR trend/,'Disabling an engine must preserve its actual execution history');
 console.log('Explicit production roster hides removed observers while preserving execution history');
 browser.exitFixture={runtime:{fresh:true,state:'POSITION_OPEN'},account:{fresh:true,positions:[{quantity:65}]},
  ledger:{active_trades:[{strategy:'ORDINARY_PUBLISHED_PCR_TRAIL',quantity:65,trailing:true,stop_fraction:'0.50',target_known:true,target_multiple:null,exit_due:'2026-10-14T10:04:00Z',exit_trigger:null}]}};
 vm.runInContext('renderDecision(exitFixture)',browser);
 assert.equal(ids['position-exits'].hidden,false);
 assert.match(ids['position-exits'].textContent,/50% below the highest completed minute close/);
 assert.match(ids['position-exits'].textContent,/No fixed profit target/);
 assert.match(ids['position-exits'].textContent,/No exit trigger recorded/);
 assert.match(ids['position-exits'].textContent,/give back profit and close below entry/);
 browser.exitFixture.ledger.active_trades=[];
 vm.runInContext('renderDecision(exitFixture)',browser);
 assert.equal(ids['position-exits'].hidden,true,'Unknown exit policy cannot retain an old policy');
});

setImmediate(()=>{
 const stamp='2026-10-15T05:00:00Z';
 browser.compact={server_time:stamp,collector:{fresh:true},account_read_ok:true,
  account:{fresh:true,available_cash:'7805.94',open_position_count:0,positions:[],age_seconds:1},
  runtime:{fresh:true,authority:'ENABLED',state:'ARMED_WAITING_SIGNAL',broker_route_verified:true,expiry_today:false,
   strategies:['CAS_LAG_V1','TREND_PULLBACK_FAST'],funded_strategies:['CAS_LAG_V1','TREND_PULLBACK_FAST'],
   observation:{expiry:'2026-10-19'},strategy_evaluations:[{strategy:'TREND_PULLBACK_FAST',funded_enabled:true,state:'NO_SIGNAL',evaluated_at:stamp,details:{trend_30m:'.003',pullback_10m:'.001'}}]},
  ledger:{available:true,counts:{fills:0},strategy_performance:[],cash_reconciliation:{status:'CHARGES_PENDING'}}};
 vm.runInContext('renderLive(compact)',browser);
 assert.equal(ids['live-cash'].textContent,'₹7,805.94');
 assert.equal(ids['live-net'].textContent,'—','Pending fees must never become zero net profit');
 assert.equal(ids['live-trades-today'].textContent,'0 completed trades today');
 assert.equal(ids['live-decision-title'].textContent,'Waiting for a pullback');
 assert.equal(ids['live-strategies'].children.length,2);
 assert.equal(ids['live-strategies'].children[0].dataset.strategy,'TREND_PULLBACK_FAST','Today’s eligible strategy comes before an ineligible expiry engine');
 browser.compact.runtime.strategy_evaluations[0]={strategy:'TREND_PULLBACK_FAST',state:'WAITING',evaluated_at:'2026-10-15T05:01:00Z',details:{}};
 browser.compact.server_time='2026-10-15T05:01:00Z';
 ids['live-strategies'].children.find(n=>n.dataset.strategy==='TREND_PULLBACK_FAST').open=true;
 vm.runInContext('renderLive(compact)',browser);
 assert.match(ids['live-decision-reason'].textContent,/10:30.*Last|Last decision 10:30/,'Between-check updates must retain the dated completed decision');
 assert.equal(ids['live-strategies'].children.find(n=>n.dataset.strategy==='TREND_PULLBACK_FAST').open,true,'Live updates must preserve an expanded strategy explanation');
 browser.compact.runtime.broker_route_verified=false;
 vm.runInContext('renderLive(compact)',browser);
 assert.equal(ids['live-decision-title'].textContent,'Checking the order connection','Permission alone is not entry readiness');
 browser.compact.runtime.fresh=false;
 vm.runInContext('renderLive(compact)',browser);
 assert.equal(ids['live-funding'].textContent,'Permission unknown');
 assert.equal(ids['live-decision-title'].textContent,'Live status unavailable');
 assert.equal(vm.runInContext("signedPercent(null)",browser),'Not reported','A missing input is not a zero percent observation');
 browser.compact.ledger.strategy_performance=[{strategy:'CAS_LAG_V1',filled_closed:4,trades:[]}];
 vm.runInContext('renderLive(compact)',browser);
 assert.match(ids['live-trades-today'].textContent,/unknown/,'Truncated history must not claim zero completed trades');
 vm.runInContext("selectView('history',false)",browser);
 assert.equal(ids.overview.hidden,true);assert.equal(ids['history-view'].hidden,false);assert.equal(ids.system.hidden,true);
 vm.runInContext("selectView('system',false)",browser);
 assert.equal(ids.overview.hidden,true);assert.equal(ids['history-view'].hidden,true);assert.equal(ids.system.hidden,false);
 vm.runInContext("selectView('live',false)",browser);
 assert.equal(ids.overview.hidden,false);assert.equal(ids['history-view'].hidden,true);assert.equal(ids.system.hidden,true);
 console.log('Compact money, dated reasons, pane isolation, missing inputs and stale permission verified');
});

setImmediate(()=>{
 browser.compact.runtime.fresh=true;browser.compact.runtime.authority='ENABLED';
 browser.compact.runtime.state='POSITION_OPEN';browser.compact.account.open_position_count=1;
 browser.compact.account.positions=[{symbol:'NIFTY fixture',quantity:65,average_price:'100.00',unrealised:'-300.00'}];
 browser.compact.ledger.active_trades=[{strategy:'TREND_PULLBACK_FAST',quantity:65}];
 vm.runInContext('renderLive(compact)',browser);
 assert.equal(ids['live-decision-title'].textContent,'Managing your position','Position management takes priority over cached no-entry reasons');
 assert.equal(ids['live-held'].children[0].children[1].children[1].textContent,'-₹300.00');
 browser.compact.account.positions[0].unrealised=null;
 vm.runInContext('renderLive(compact)',browser);
 assert.equal(ids['live-held'].children[0].children[1].children[1].textContent,'—');
 assert.equal(ids['live-held'].children[0].children[1].children[1].className,undefined,'Unknown P&L cannot receive a profitable color');
 browser.compact.ledger.strategy_performance=[{strategy:'CAS_LAG_V1',filled_closed:1,trades:[{exit_at:null}]}];
 vm.runInContext('renderLive(compact)',browser);
 assert.match(ids['live-trades-today'].textContent,/unknown/,'Missing close timestamps cannot prove zero trades today');
 console.log('Held-position priority, unknown unrealised P&L and incomplete dates verified');
});

setImmediate(()=>{
 browser.recordedFixture={server_time:'2026-10-15T06:32:00Z',runtime:{fresh:true,authority:'ENABLED',strategies:['CAS_LAG_V1','TREND_PULLBACK_FAST'],funded_strategies:['CAS_LAG_V1','TREND_PULLBACK_FAST'],expiry_today:false},ledger:{available:true,decision_history:{status:'AVAILABLE',date:'2026-10-15',strategies:[{strategy:'TREND_PULLBACK_FAST',truncated:false,records:[{strategy:'TREND_PULLBACK_FAST',evaluated_at:'2026-10-15T06:30:00Z',received_at:'2026-10-15T06:30:03Z',state:'NO_SIGNAL',details:{trend_30m:'.003',pullback_10m:'.001'}}]}]}}};
 browser.waiting={strategy:'TREND_PULLBACK_FAST',state:'WAITING',reason:'OUTSIDE_STRATEGY_WINDOW',details:{}};
 browser.recordedFixture.runtime.strategy_evaluations=[browser.waiting];
 vm.runInContext('state.liveChecks={}',browser);
 let snapshot=vm.runInContext("liveStrategyState('TREND_PULLBACK_FAST',waiting,recordedFixture)",browser);
 assert.equal(snapshot.check.evaluated_at,'2026-10-15T06:30:00Z','Cold reload retains the durable last decision');
 assert.match(snapshot.reason,/No opposing pullback/);
 vm.runInContext('renderLive(recordedFixture)',browser);
 assert.match(ids['live-check-total'].textContent,/1 completed checks.*0 signals/);
 assert.match(ids['live-decision-reason'].textContent,/12:00 IST.*No opposing pullback/);
 browser.recordedFixture.ledger.decision_history.strategies[0].records.push({strategy:'TREND_PULLBACK_FAST',evaluated_at:'2026-10-15T06:30:00Z',received_at:'2026-10-15T06:30:05Z',state:'UNKNOWN',reason:'MISSING_COMPLETED_BAR',details:{}});
 snapshot=vm.runInContext("liveStrategyState('TREND_PULLBACK_FAST',waiting,recordedFixture)",browser);
 assert.equal(snapshot.label,'Last check incomplete','A later missing-bar warning cannot be hidden by the earlier successful evaluation');
 vm.runInContext('renderLive(recordedFixture)',browser);
 assert.match(ids['live-check-total'].textContent,/1 data warnings/);
 assert.equal(ids['today-checks'].children.length,1,'Same scheduled boundary is displayed once with its latest receipt');
 assert.match(ids['today-checks'].children[0].children[1].textContent,/bar was unavailable/);
 browser.recordedFixture.ledger.decision_history.date='2026-10-14';
 assert.equal(vm.runInContext('recordedChecks(recordedFixture).length',browser),0,'Yesterday cannot become today’s reason');
 browser.recordedFixture.ledger.decision_history.date='2026-10-15';
 browser.recordedFixture.ledger.decision_history.strategies[0].records=[{strategy:'TREND_PULLBACK_FAST',evaluated_at:'2026-10-15T06:40:00Z',received_at:'2026-10-15T06:40:03Z',state:'SIGNAL'}];
 assert.equal(vm.runInContext('recordedChecks(recordedFixture).length',browser),0,'Future records cannot become current evidence');
 console.log('Durable decisions, cold reload, receipt order, warnings and date boundary verified');
});

setImmediate(()=>{
 browser.secondsFixture={server_time:'2026-10-15T08:00:00Z',runtime:{fresh:true,authority:'ENABLED',funded_strategies:['CAS_LAG_V1']},account:{fresh:true,available_cash:'7805.94'},
  seconds_experiments:{fresh:true,status:'AVAILABLE',mode:'SIMULATION',initial_bankroll:'7805.94',delay_seconds:'1.00',
   evaluations:[{strategy:'SECONDS_FUTURES_CATCHUP',state:'NO_SIGNAL',reason:'SECONDS_EDGE_BELOW_COSTS',details:{},evaluated_at:'2026-10-15T08:00:00Z'}],
   results:[{strategy:'SECONDS_FUTURES_CATCHUP',signals:2,closed:1,entries:1,missed:1,net:'42.00',cash:'7847.94'}]}};
 vm.runInContext('renderLive(secondsFixture)',browser);
 assert.equal(ids['live-cash'].textContent,'₹7,805.94','Paper profits cannot increase broker cash');
 assert.match(ids['seconds-summary'].textContent,/simulated/);
 assert.match(ids['seconds-context'].textContent,/independently.*simulated money/);
 assert.match(ids['seconds-strategies'].children[0].children[0].children[1].textContent,/does not clear the cost/);
 browser.secondsFixture.seconds_experiments.fresh=false;
 vm.runInContext('renderLive(secondsFixture)',browser);
 assert.match(ids['seconds-summary'].textContent,/unavailable/);
 assert.equal(ids['seconds-strategies'].children[0].children[0].children[0].children[1].textContent,'Unknown');
 console.log('Five-strategy simulation is separate from funded permission and real cash');
});

setImmediate(()=>{
 browser.blocked={server_time:'2026-10-15T09:00:00Z',runtime:{fresh:true,authority:'ENABLED',state:'ARMED_WAITING_SIGNAL',
   strategies:['SECONDS_FUTURES_CATCHUP'],funded_strategies:['SECONDS_FUTURES_CATCHUP'],software_verified:true,
   account_snapshot_fresh:true,current_account_funded:true,broker_route_verified:false,route_attempts_used:3,route_attempt_limit:3},
   ledger:{available:true,route_check:{state:'REJECTED',reason:'LOW_OPEN_INTEREST'}}};
 vm.runInContext('renderLive(blocked)',browser);
 assert.equal(ids['live-funding'].textContent,'Funded · entries blocked');
 assert.match(ids['live-decision-title'].textContent,/order check rejected/i);
 assert.match(ids['live-decision-reason'].textContent,/open interest.*3 of 3/i);
 browser.blocked.runtime.state='WAITING_EXCHANGE_SESSION';
 vm.runInContext('renderLive(blocked)',browser);
 assert.match(ids['live-decision-reason'].textContent,/exchange session is closed.*open interest.*3 of 3/i);
 assert.equal(vm.runInContext("liveStrategyState('SECONDS_FUTURES_CATCHUP',null,blocked).label",browser),'Market closed','Expected closed-session silence must not look like a data failure');
 browser.blocked.runtime.state='ARMED_WAITING_SIGNAL';
 browser.blocked.ledger.route_check=null;
 vm.runInContext('renderLive(blocked)',browser);
 assert.match(ids['live-decision-title'].textContent,/attempts exhausted/i);
 browser.blocked.runtime.broker_route_verified=true;
 vm.runInContext('renderLive(blocked)',browser);
 assert.equal(ids['live-funding'].textContent,'Funded · waiting for a signal');
 const explanation=vm.runInContext("conditionSummary({strategy:'SECONDS_FUTURES_CATCHUP',state:'NO_SIGNAL',reason:'SECONDS_RULE_NOT_MET',details:{future_move_2s:'0.50',impulse_threshold:'4.60'}})",browser);
 assert.match(explanation,/0\.5.*4\.6/,'The missing futures impulse must be explained with observed and required values');
 console.log('Funded permission, rejected/exhausted route and concrete seconds reasons remain distinct');
});

setImmediate(()=>{
 assert.match(vm.runInContext("secondsExplanation({reason:'SECONDS_UNAFFORDABLE',details:{entry_cash:'8000',exit_fee_reserve:'80',cash_budget:'7415'}})",browser),/cash|afford/i);
 assert.match(vm.runInContext("secondsExplanation({reason:'OPTIONS_FEED_UNAVAILABLE'})",browser),/option quote/i);
 browser.blocked.release={upgrade_required:true};
 browser.blocked.runtime.broker_route_verified=true;
 vm.runInContext('renderLive(blocked)',browser);
 assert.match(ids['live-funding'].textContent,/update pending/i);
 assert.match(ids['live-decision-reason'].textContent,/running trader|trader software/i);
 delete browser.blocked.release;
 console.log('Exact execution blockers and funded software update remain visible');
});
