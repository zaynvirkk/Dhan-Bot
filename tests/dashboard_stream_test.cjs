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
const disconnected=structuredClone(current);disconnected.runtime.feed_health.order.connected=false;show(disconnected);
assert.match(ids.notice.textContent,/live feed is disconnected/);
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
 f.server_time='2026-10-06T05:00:01Z';f.runtime.fresh=false;
 vm.runInContext('render(strategiesFixture)',browser);
 for(const row of ids['strategy-checks'].children)assert.equal(row.children[1].textContent,'Unknown');
 console.log('Multiple strategy checks and stale demotion verified');
});
