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
