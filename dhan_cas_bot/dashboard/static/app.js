'use strict';
const $ = id => document.getElementById(id);
const state = {data:null, source:'broker', fetching:false, generation:0, historyDate:'', historyFetchedAt:null};
const rendered=new Map();
function changed(key,value){const encoded=JSON.stringify(value);if(rendered.get(key)===encoded)return false;rendered.set(key,encoded);return true;}
const names = {dhan_auth:'Dhan authentication', dhan_account:'Dhan account', egress:'Static IP & whitelist', contract_metadata:'Contract catalogue', upstox_feed:'Upstox index feed', dhan_market_feed:'Dhan options feed', dhan_order_socket:'Order-update socket'};
const pending = new Set(['PENDING_SEND','SEND_UNKNOWN','SENT','TRANSIT','PENDING','PART_TRADED','TRIGGERED']);
function el(tag, text, className){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function cash(value){if(value===null||value===undefined)return '—';const m=String(value).match(/^(-?)(\d+)\.(\d{2})$/);if(!m)return '—';const rupees=BigInt(m[2]).toLocaleString('en-IN');return `${m[1]}₹${rupees}.${m[3]}`;}
function at(value){if(!value)return 'No observation';const d=new Date(value);return Number.isNaN(d.getTime())?'Unknown time':new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(d)+' IST';}
function age(s){if(s===null||s===undefined)return 'Unknown age';if(s<60)return `${s}s ago`;if(s<3600)return `${Math.floor(s/60)}m ago`;if(s<86400)return `${Math.floor(s/3600)}h ago`;return `${Math.floor(s/86400)}d ago`;}
function pnl(id,value){const n=$(id);n.textContent=cash(value);n.classList.remove('positive','negative');if(value&&value!=='0.00')n.classList.add(value.startsWith('-')?'negative':'positive');}
function badge(text,kind=''){return el('span',text,'badge '+kind);}
function feedError(value){return ({ConnectionClosedError:'Connection closed',TimeoutError:'Connection timed out',InvalidHandshake:'Connection handshake failed',HTTPStatusError:'Provider request failed',OSError:'Network connection failed',EOFError:'Connection ended unexpectedly',ContractError:'Feed validation failed'})[value]||'Cause not reported';}
function diagnosticFailure(c){const f=c.facts||{};let detail=feedError(c.error_type);if(c.http_status)detail+=` · HTTP ${c.http_status}`;if(f.keepalive_timeout)detail+=' · no reply to the connection keepalive';if(f.close_received_code!=null)detail+=` · provider close code ${f.close_received_code}`;if(f.close_sent_code!=null)detail+=` · client close code ${f.close_sent_code}`;return detail+'. This is the dated diagnostic result; current socket state is shown in Live connections.';}
function details(c){const f=c.facts||{};if(c.status==='FAIL')return diagnosticFailure(c);if(c.name==='dhan_market_feed')return `${f.full_packets??'No'} full packets recorded · ${f.book_verified?'book data observed':'book data unverified'}`;if(c.name==='upstox_feed')return `${f.index_seen?'Index received':'Index unverified'} · ${f.index_iep_seen?'IEP observed':'IEP not observed'}`;if(c.name==='dhan_order_socket')return `${f.websocket_connected?'Socket connected':'Socket unverified'} · ${f.route_verified?'order route verified':'order route unverified'}`;if(c.name==='contract_metadata')return `${f.instruments??'—'} contracts · expiry ${f.expiry?new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short'}).format(new Date(f.expiry)):'unknown'}`;if(c.name==='dhan_auth')return `${f.derivatives_enabled?'F&O enabled':'F&O unverified'} · data plan ${f.data_plan||'unknown'}`;if(c.name==='dhan_account')return `${Number.isInteger(f.open_positions)?`${f.open_positions} open positions`:'Open-position count unavailable'} · ${f.positions??'—'} position records · ${f.orders??'—'} orders`;if(c.name==='egress')return f.matches_expected?'Observed IP matches the configured address.':'Expected IP match unverified.';return 'No result recorded.';}
function rows(target, rows, columns){if(!changed('table:'+target,[rows,columns.map(c=>c.title||'')]))return;const body=$(target);body.replaceChildren();for(const r of rows){const tr=el('tr');for(const c of columns){const td=el('td',undefined,c.numeric?'numeric':'');const v=c.read(r);if(v instanceof Node)td.append(v);else td.textContent=v??'—';tr.append(td);}body.append(tr);}}
function orderBadge(s){return badge((s||'UNKNOWN').replaceAll('_',' '),s==='REJECTED'?'bad':pending.has(s)?'warn':s==='TRADED'||s==='FILLED'?'good':'');}
function renderOrders(){const d=state.data;const a=d?.account;const ledger=d?.ledger;const kind=state.source;if(!changed('orders',[a?{...a,age_seconds:undefined}:a,ledger,kind,$('order-filter').value]))return;let items=kind==='broker'?a?.orders:ledger?.[kind];const available=kind==='broker'?Array.isArray(items):ledger?.available&&Array.isArray(items);items=available?items:[];const filter=$('order-filter').value;if(kind!=='fills'&&filter!=='all')items=items.filter(r=>filter==='pending'?pending.has(r.state):filter==='filled'?['TRADED','FILLED'].includes(r.state):['CANCELLED','REJECTED','ABORTED'].includes(r.state));$('order-filter').disabled=kind==='fills';
 const columns=kind==='fills'?[{title:'Observed time',read:r=>at(r.occurred_at)},{title:'Security ID',read:r=>r.security_id},{title:'Quantity',numeric:true,read:r=>r.quantity},{title:'Fill price',numeric:true,read:r=>cash(r.price)},{title:'Recorded fees',numeric:true,read:r=>cash(r.fees)}]:[{title:kind==='broker'?'Instrument':'Created at',read:r=>kind==='broker'?(r.symbol||r.security_id):at(r.occurred_at)},{title:'Side',read:r=>r.side},{title:'Status',read:r=>orderBadge(r.state)},{title:'Quantity',numeric:true,read:r=>r.quantity},...(kind==='broker'?[{title:'Filled',numeric:true,read:r=>r.filled_quantity}]:[]),{title:'Limit price',numeric:true,read:r=>cash(r.price)}];
 const tr=el('tr');columns.forEach(c=>tr.append(el('th',c.title,c.numeric?'numeric':'')));$('order-head').replaceChildren(tr);rows('order-body',items,columns);$('orders-empty').hidden=items.length>0;$('order-table').hidden=!items.length;$('orders-empty').textContent=!available?'No verified order-history observation is available.':filter!=='all'&&kind!=='fills'?'No orders match this filter.':kind==='broker'?'Dhan reported no orders in this snapshot.':'No '+(kind==='fills'?'fills':'order intents')+' have been recorded in the bot’s ledger.';
 $('order-context').textContent=kind==='broker'?(a?`${a.fresh?'Current':'Last observed'} broker snapshot · ${at(a.observed_at)}${a.orders_truncated?' · latest 100 shown':''}`:'Broker account unavailable.'):'Latest 100 persisted records. Recorded fees may not include final contract-note adjustments.';
}
function renderTimings(rt){
 if(!changed('timings',rt?.telemetry))return;
 const metrics=rt?.telemetry?.latency||{};const counts=rt?.telemetry?.decision_counts||{};
 const labels={decision_ms:'Decision cycle',signal_to_decision_ms:'Latest signal → cycle',market_to_decision_ms:'Latest book → cycle',decision_to_submit_ms:'Cycle → order send',http_ack_ms:'Order HTTP response',first_fill_recorded_ms:'Send → first fill recorded',reconcile_ms:'Account reconciliation',loop_lag_ms:'Event-loop delay',book_age_ms:'Book age at entry'};
 $('timings').replaceChildren();$('entry-checks').replaceChildren();
 for(const [key,value] of Object.entries(metrics)){if(!labels[key])continue;const row=el('div');row.append(el('dt',labels[key]),el('dd',value.p95===null?'—':`${value.p95} ms (${value.samples??0})`));$('timings').append(row);}
 $('timing-empty').hidden=Object.keys(metrics).length>0;
 for(const [key,value] of Object.entries(counts)){const row=el('div');row.append(el('dt',key.toLowerCase().replaceAll('_',' ')),el('dd',value??'—'));$('entry-checks').append(row);}
}
function elapsed(stamp,now){const value=(Date.parse(now)-Date.parse(stamp))/1000;return Number.isFinite(value)&&value>=-5?Math.max(0,Math.floor(value)):null;}
function renderFeeds(rt,now){
 const feeds=rt?.feed_health||{};const names={signal:'Upstox index feed',market:'Dhan options feed',order:'Dhan order updates'};
 const idle=rt?.monitoring_mode==='IDLE';const fresh=rt?.fresh===true;
 const issues=[];let known=0;
 const auctionExpected=Number(rt?.observation?.reference)>0&&['CTS_CLOSE','CAS_LM_START','CAS_M_STOP'].includes(rt?.observation?.phase);
 const auctionClosed=rt?.observation?.phase==='CAS_STOP';
 const rows=Object.entries(names).map(([key,name])=>{
  const f=feeds[key];let status='Unknown',kind='warn',detail='The deployed bot has not supplied live connection observations.';
  if(f){
   if(typeof f.connected==='boolean')known++;
   const seen=elapsed(f.last_received_at,now),processed=elapsed(f.last_processed_at,now),usable=elapsed(f.last_usable_at,now);
   detail=`Last message in this connection: ${seen===null?'not observed':age(seen)} · reconnects: ${f.reconnects??'unknown'}`;
   if(f.connected===false)detail+=` · last error: ${feedError(f.last_error)}`;
   if(key!=='order')detail+=` · accepted ${key==='market'?'book':'strategy input'}: ${usable===null?'not observed':age(usable)}`;
   else detail+=' · silence is normal when no orders change';
   detail+=` · pending messages: ${f.pending_messages??'unknown'}`;
   if(f.pending_messages>0)detail+=` · oldest queued: ${f.oldest_pending_ms??'unknown'} ms`;
   if(f.processing_ms!==null&&f.processing_ms!==undefined)detail+=` · last processing: ${f.processing_ms} ms`;
   if(!fresh){status='Historical';}
   else if(f.connected===false){status='Disconnected';kind='bad';issues.push('disconnected');}
   else if(f.connected===true){
    status='Connected';kind='good';
    if(Number(f.oldest_pending_ms)>1000){status='Processing delayed';kind='warn';issues.push('delayed');}
    else if(!idle&&key==='signal'&&(usable===null||usable>5)&&seen!==null&&seen<=5&&processed!==null&&processed<=5){
     status='Receiving frames';
     detail+=auctionClosed?' · provider has closed the auction':auctionExpected?' · auction entry awaits a current official indicative index value':' · no current strategy input accepted';
     issues.push('signal-pending');
    }
    else if(!idle&&key!=='order'&&(usable===null||usable>5)){status='Awaiting fresh data';kind='warn';issues.push('waiting');}
   }
  }
  return {name,status,kind,detail};
 });
 $('feed-context').textContent=!fresh?'Current feed health is unknown until a fresh bot status arrives.':idle?'The bot reports an idle session: entries are outside their active window. Market data may still arrive; receipt times and socket state are shown separately.':'Live socket observations. Connected does not mean the strategy has a usable signal or permission to trade.';
 if(changed('feed-rows',rows)){$('live-connections').replaceChildren();for(const r of rows){const row=el('div',undefined,'connection-row live-feed');const info=el('div');info.append(el('p',r.name,'connection-name'),el('p',r.detail,'connection-detail'));row.append(info,badge(r.status,r.kind));$('live-connections').append(row);}}
 return {issues,known,idle,auctionExpected,auctionClosed,disconnected:rows.filter(r=>r.status==='Disconnected').map(r=>r.name)};
}
function monitoringNotice(d,feeds){
 if(!d.available)return {text:'No dashboard snapshot is available. The collector may not be running.',kind:'error'};
 if(!d.collector?.fresh)return {text:'Dashboard observations are stale. Current trading status is unknown.',kind:'error'};
 if(!d.runtime?.fresh)return {text:'The bot status is stale or missing. Current trading authority cannot be confirmed.',kind:'error'};
 if(!d.account_read_ok){
  if(d.account_error==='ACCOUNT_OBSERVATION_STALE')return {text:'The last successful account check is stale. Previous balances and positions are shown until a fresh check completes.',kind:'warn'};
  if(d.account_error==='ACCOUNT_OBSERVATION_UNAVAILABLE')return {text:'Waiting for a current Dhan account observation. Previous balances and positions are shown where available.',kind:'warn'};
  return {text:'The latest Dhan account read failed. Previous balances and positions are shown; the trader needs fresh reconciliation before opening another position.',kind:'error'};
 }
 if(d.account&&!d.account.fresh)return {text:'Account observations are stale. Last observed balances and positions are shown; current account state is unknown.'};
 if(d.runtime.account_snapshot_fresh===false)return {text:'The broker balance is current, but trader reconciliation is stale or incomplete. New entries require a fresh reconciled account.',kind:'warn'};
 if(feeds.issues.includes('disconnected')){
  const plan=d.connections?.checks?.find(c=>c.name==='dhan_auth')?.facts?.data_plan;
  let next='Open System → Live connections for the latest error and reconnect count.';
  if(feeds.disconnected.includes('Dhan options feed')&&['Inactive','Expired'].includes(plan))next=`${d.connections.fresh?'Dhan reports':'Last Dhan check reported'} an ${plan.toLowerCase()} data subscription. Check Data APIs in DhanHQ${d.connections.fresh?'.':'; the check time is under System → Diagnostics.'}`;
  return {text:`${feeds.disconnected.join(' / ')} disconnected. ${next}`,kind:'error'};
 }
 if(feeds.issues.includes('delayed'))return {text:'Feed processing is delayed. Inspect pending messages in Live connections.'};
 const history=d.runtime.input_health;
 if(history?.fresh&&['spot','future'].some(k=>history[k]?.current_complete===false||history[k]?.missing_minutes>0))return {text:'Live quotes are arriving, but required completed candles are missing. See What the bot sees for the affected source; those rules cannot evaluate.'};
 if(feeds.known<3)return {text:'Account and bot updates are current. Live feed health is unavailable from the deployed version; dated diagnostics are shown separately.'};
 if(feeds.idle)return {text:'The bot reports an idle session. Account updates are current; live socket observations are shown below.',kind:'healthy'};
 if(feeds.issues.includes('waiting'))return {text:'Account updates are current. Waiting for fresh usable market data; inspect Live connections.'};
 if(feeds.issues.includes('signal-pending'))return feeds.auctionClosed?
  {text:'Live feeds are receiving data. The provider has closed auction entries; position management continues.',kind:'healthy'}:feeds.auctionExpected?
  {text:'Live feeds are receiving data. Auction entries await a current official indicative index value.',kind:'healthy'}:
  {text:'Upstox frames are arriving, but no current strategy input has been accepted. Inspect index inputs in Live connections.'};
 return {text:'Account and feed observations are current. Trading authority and entry conditions are shown separately.',kind:'healthy'};
}
function points(value){return cash(value).replace('₹','');}
function shortDate(value){return value?new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short'}).format(new Date(value)):'date unconfirmed';}
function istDay(value){const d=new Date(value);return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);}
function stateLabel(value){return ({WAITING_EXCHANGE_SESSION:'Waiting for an exchange session',NO_TRADE_DAY:'Not an eligible expiry session',ARMED_WAITING_SESSION:'Waiting for trading window',ARMED_WAITING_SIGNAL:'Waiting for auction signal',POSITION_OPEN:'Managing open position',ENTRY_PENDING:'Entry awaiting execution',EXIT_PENDING:'Exit awaiting execution',SETTLEMENT_PENDING:'Settlement pending',RECOVERING:'Reconciling account',ENTRY_HALTED:'Entries blocked',DISARMED:'Entries disabled',UNKNOWN:'Current state unknown'})[value]||'Unknown state';}
function renderHistory(d){
 const h=d?.history;
 if(!state.historyDate)state.historyDate=istDay(d?.server_time);
 $('history-date').value=state.historyDate;
 if(!changed('history',[h,state.historyDate]))return;
 const day=h?.days?.find(row=>row.date===state.historyDate);
 const events=(h?.events||[]).filter(row=>istDay(row.at)===state.historyDate).slice(-30).reverse();
 const available=h?.status==='AVAILABLE';
 $('history-summary').textContent=!h?'This deployed version has no monitoring history in its snapshot.':!available?'Monitoring history could not be read. Current observations and execution records are separate.':day?`${state.historyDate} · ${day.samples} monitoring samples · ${day.unknown_samples} with unknown source state · ${day.gaps} recording gaps over 90 seconds`:`No recorded monitoring coverage for ${state.historyDate||'this date'}. This does not establish that no trades occurred.`;
 $('history-coverage').textContent=day?`First sample ${at(day.first_at)}; last ${at(day.last_at)}. States observed: ${(day.states||[]).map(stateLabel).join(' · ')}. Samples do not prove uninterrupted coverage.`:h?.started_at?`Recording began ${at(h.started_at)}. Earlier activity is not reconstructed.`:'';
 $('history-events').replaceChildren();
 for(const e of available?events:[]){
  const li=el('li'),info=el('div'),time=el('time',at(e.at));time.dateTime=e.at;
  const quote=(label,value,stamp)=>value==null?`${label} not recorded`:`${label} ${points(value)} (${age(elapsed(stamp,e.at))} at sample)`;
  const connected=Object.values(e.feeds||{}).filter(v=>v===true).length;
  info.append(el('strong',stateLabel(e.state)),el('p',e.source_current?`${quote('NIFTY',e.ltp,e.ltp_at)} · ${quote('IEP',e.iep,e.iep_at)} · ${e.books??'unknown'} books · ${connected}/3 sockets connected`:'Bot status was stale or missing. Market and trading state were unknown.'));
  if(e.state==='WAITING_EXCHANGE_SESSION')info.append(el('p','No new entries while waiting for an exchange session.'));
  if(e.reason)info.append(el('p',e.state==='WAITING_EXCHANGE_SESSION'?`Last recorded execution note: ${e.reason}`:e.reason));for(const s of e.strategies||[])info.append(el('p',`${strategyNames[s.strategy]||s.strategy}: ${conditionSummary(s)}`));for(const s of e.daily_monitor||[])info.append(el('p',`Read-only ${strategyNames[s.strategy]||s.strategy}: ${conditionSummary(s)}`));li.append(time,info);$('history-events').append(li);
 }
 $('history-empty').hidden=available&&events.length>0;
 $('history-empty').textContent=day?'The daily summary is retained; no detail samples for this date remain in the bounded history.':'No samples are available for this date. Missing history is not a zero-trade result.';
}
const strategyNames={CAS_LAG_V1:'Expiry auction',GAP_FADE_DOUBLE:'Morning gap-fade',NIFTY_SELLOFF_REBOUND_1510:'Overnight rebound'};
const strategyReasons={CALENDAR_UNAVAILABLE:'The exchange calendar is unavailable.',EXCHANGE_CLOSED:'The exchange is closed.',CONTRACT_CALENDAR_UNAVAILABLE:'Current contract dates are unavailable.',EXPIRY_SESSION_OUTSIDE_RESEARCH_SCOPE:'NIFTY expires today; gap-fade covers non-expiry sessions.',OUTSIDE_STRATEGY_WINDOW:'Waiting for the next scheduled check.',SPECIAL_SESSION_OUTSIDE_RESEARCH_SCOPE:'This is a special session outside the tested schedule.',NEXT_SESSION_EXIT_UNAVAILABLE:'The next session does not support the planned exit.',SELLOFF_THRESHOLD_MET:'The index decline crossed the 0.75% trigger.',SELLOFF_BELOW_THRESHOLD:'The index decline has not reached 0.75%.',GAP_FADE_CONFIRMED:'Gap, retracement, persistence and futures direction agree.',GAP_FADE_CONDITIONS_NOT_MET:'The gap-fade conditions do not all agree.',COMPLETED_INPUT_MISSING_OR_INVALID:'A required completed minute is missing or invalid.',NOT_CONFIGURED:'This engine is not enabled in the service configuration.',STRATEGY_INPUTS_STALE:'The minute inputs are stale.',STRATEGY_INPUT_UNAVAILABLE:'A market-data request failed.',INPUTS_NOT_RECEIVED:'Waiting for the first input check.'};
const conditionNames={rule:'Entry rule',gap_size:'Opening gap',gap_fill:'Gap retracement',persistence:'Price persistence',futures_direction:'Futures confirmation',selloff:'Decline from open'};
function pct(value){return value==null?'Unavailable':`${(Number(value)*100).toFixed(2)}%`;}
function conditionDetail(c){
 const direction=c.expected==='RISING'?'rising':c.expected==='FALLING'?'falling':null;
 if(c.key==='persistence')return c.state==='UNKNOWN'?'Three completed closes or the gap direction are unavailable.':`Last three closes ${c.state==='PASS'?'are':'are not all'} ${direction||'in the required direction'}.`;
 if(c.key==='futures_direction')return `${pct(c.value)} over five minutes; needs ${direction||'a confirmed gap direction'}.`;
 if(c.key==='gap_size')return `${pct(c.value)}; needs an absolute gap of at least ${pct(c.minimum)}.`;
 if(c.key==='gap_fill')return `${pct(c.value)} filled; needs ${pct(c.minimum)} to ${pct(c.maximum)}.`;
 if(c.key==='selloff')return `${pct(c.value)} from open; needs ${pct(c.maximum)} or lower.`;
 return 'Condition unavailable.';
}
function conditionSummary(row){
 const checks=row.conditions||[],failed=checks.filter(c=>c.state==='FAIL'),missing=checks.filter(c=>c.state==='UNKNOWN');
 if(row.state==='NO_SIGNAL'&&failed.length)return `Skipped: ${failed.map(c=>conditionNames[c.key]).join(', ')} not met.`;
 if(row.state==='UNKNOWN'&&missing.length)return `Cannot decide: ${missing.map(c=>conditionNames[c.key]).join(', ')} ${missing.length===1?'is':'are'} unavailable.`;
 if(row.family&&row.family!=='GAP_FADE'&&!['NIFTY_SELLOFF_REBOUND_1510','CAS_LAG_V1'].includes(row.strategy)){
  if(row.reason==='EXPANDED_RULE_CONFIRMED')return `Entry conditions met · ${row.side==='CE'?'CALL':'PUT'}.`;
  if(row.reason==='EXPANDED_RULE_NOT_MET')return 'Observed inputs do not meet the entry rule.';
  if(row.reason.startsWith('MISSING_'))return `Cannot decide: ${row.reason.slice(8).replaceAll('_',' ').toLowerCase()} unavailable.`;
  if(row.reason==='SOURCE_NOT_YET_AVAILABLE')return 'The required source was not available at this decision time.';
 }
 return strategyReasons[row.reason]||row.state;
}
function conditionList(row,current){
 const list=el('ul',undefined,'strategy-conditions');list.setAttribute('aria-label','Observed entry conditions');
 const invalid=!current||['STRATEGY_INPUTS_STALE','STRATEGY_INPUT_UNAVAILABLE','INPUTS_NOT_RECEIVED'].includes(row.reason);
 for(const original of row.conditions||[]){
  const c=invalid?{...original,state:'UNKNOWN'}:original,li=el('li'),body=el('div');
  body.append(el('strong',conditionNames[c.key]||'Condition'),el('p',conditionDetail(c)));
  const label=c.state==='PASS'?'Passed':c.state==='FAIL'?'Not met':'Unavailable';
  li.append(body,badge(label,c.state==='PASS'?'good':c.state==='FAIL'?'':'warn'));list.append(li);
 }
 return list;
}
function renderSelection(d){
 const rt=d.runtime,sel=rt?.strategy_selection;
 $('selection-stamp').textContent=sel?.evaluated_at?`Last comparison ${at(sel.evaluated_at)}`:'No executable comparison recorded';
 const names=s=>strategyNames[s]||s.replaceAll('_',' ').toLowerCase();
 const closed=rt?.state==='WAITING_EXCHANGE_SESSION';
 const recorded=sel?.evaluated_at&&sel?.candidates?.length>0;
 let reason=closed?'The exchange session is closed.'+(recorded?' The last comparison is retained below.':''):
  'The bot compares whole-lot affordability, fresh executable depth and spread before allocating money.';
 if(sel?.reason==='SELECTED')reason+=` Selected ${names(sel.selected)}. `+(sel.mode==='QUALIFIED_AUCTION'?'It passed the live auction discrepancy, execution and cash checks. No simultaneous executable minute candidate was present.':sel.mode==='MEASURED_CASH_PER_MINUTE'?
  'Its estimated net rupees per holding minute, adjusted for observed fill completion, ranked highest among executable candidates.':
  'No measured profit estimate exists for these candidates. Same-side selection used lower execution friction, then a shorter holding limit.');
 else if(sel?.reason==='CONFLICTING_UNRANKED_SIGNALS')reason+=' Calls and puts both qualified without measured positive evidence. No trade was selected.';
 else if(sel?.reason==='NO_POSITIVE_ESTIMATED_EDGE')reason+=' The fillable candidates had no positive estimated profit after current costs. No trade was selected.';
 else reason+=' No executable candidate comparison has been recorded this session.';
 $('selection-reason').textContent=reason;
 const percent=(value,digits=1)=>value==null?'unavailable':`${(Number(value)*100).toFixed(digits)}%`;
 const history=rt?.execution_feedback||[];
 if(changed('selection-history',history)){
  $('selection-history').replaceChildren();
  for(const row of history){
   if(!row.filled_closed&&!row.closed_entry_opportunities)continue;
   const text=`${names(row.strategy)}: ${row.filled_closed??0} filled closed trades across ${row.sessions??0} session(s). `+
    `${row.filled_entry_opportunities??'—'} of ${row.closed_entry_opportunities??'—'} recent completed entry opportunities filled; average quantity completion ${percent(row.mean_entry_fill_fraction)}. `+
    (row.mean_estimated_net_return!=null?`Estimated mean net return ${percent(row.mean_estimated_net_return,2)}; standard error ${percent(row.return_standard_error,2)}. `:'')+
    (row.sessions===1?'One session is insufficient to establish a repeatable edge.':'Charges remain estimates until final broker fees are reconciled.');
   $('selection-history').append(el('p',text,'connection-detail'));
  }
 }
 const source={UPSTOX_COMPLETED_I1_STREAM:'Latest NIFTY minute source: validated Upstox stream',REST_BOOTSTRAP_OR_GAP_REPAIR:'Latest NIFTY minute source: REST startup or gap repair',NOT_OBSERVED:'NIFTY minute source has not yet been observed'}[rt?.minute_source]||'NIFTY minute source not reported';
 $('selection-flow').textContent=`${source}. Prices and fills use WebSockets; futures OI, missing candles and published inputs retain bounded REST reads. Estimates use prior closed trades and conservative costs; targets are not forecasts.`;
 if(!changed('selection-candidates',sel))return;
 $('selection-candidates').replaceChildren();
 if(!sel?.candidates?.length)return;
 const list=el('details',undefined,'decision-inputs');list.append(el('summary',`${sel.candidates.length} executable candidate${sel.candidates.length===1?'':'s'} compared`));
 for(const row of sel.candidates){
  const item=el('div',undefined,'selection-candidate');
  const winner=sel.selected===row.strategy;
  item.append(el('p',`${winner?'Selected · ':''}${names(row.strategy)} · ${row.side||'Side unknown'}`,'connection-name'));
  const measured=row.estimated_net_profit!=null;
  item.append(el('p',`${row.quantity??'—'} units · entry limit ${cash(row.limit)} · friction reserve ${cash(row.friction_cash)}`,'connection-detail'));
  item.append(el('p',measured?`Conditional net ${cash(row.estimated_net_profit)} · fill-adjusted ${cash(row.estimated_profit_per_minute)}/minute · observed hold ${Number(row.holding_minutes).toFixed(1)} minutes · ${row.filled_closed} filled closed trades across ${row.sessions} session(s).`:
   'Profit estimate unavailable. Execution quality is an experimental fallback, not evidence of an edge.','connection-detail'));
  item.append(el('p',`Observed entry fill rate ${percent(row.entry_fill_rate)} · average quantity completion ${percent(row.mean_entry_fill_fraction)} · return standard error ${percent(row.return_standard_error,2)}.`,'connection-detail'));
  list.append(item);
 }
 $('selection-candidates').append(list);
}

function renderStrategies(d){
 const rt=d.runtime,observer=d.daily_monitor,hasRoster=Array.isArray(rt?.strategies)&&(rt.strategies.length>0||Array.isArray(rt.funded_strategies)),configured=rt?.strategies||[],checks=rt?.strategy_evaluations||[];
 const funded=rt?.funded_strategies,performance=d.ledger?.strategy_performance||[];
 const performanceAt=name=>performance.find(x=>x.strategy===name);
 const observerChecks=hasRoster?[]:observer?.strategy_evaluations||[];
 const usingObserver=observerChecks.length>0,calendar=hasRoster?rt:observer||rt;
 $('calendar-stamp').textContent=calendar?.calendar_checked_at?`Calendar checked ${at(calendar.calendar_checked_at)}`:'No exchange calendar observation';
 $('strategy-mode').textContent=Array.isArray(funded)?`${funded.length} permitted to trade real money · ${configured.length} scanned configurations. Observation-only rules cannot place new entries. Expand a family for its live inputs and execution history.`:usingObserver?'Daily checks are read-only and cannot submit orders. Funded permissions have not been reported by the trading service.':`${configured.length} scanned configurations. Separate funded permissions have not been reported by this service version.`;
 if(changed('strategy-performance',performance)){
  $('strategy-performance').replaceChildren();
  if(performance.length){
   const wrap=el('div',undefined,'table-wrap'),table=el('table'),head=el('tr');
   for(const text of ['Strategy','Closed trades','Gross P&L','Broker charges','Net P&L'])head.append(el('th',text));
   table.append(head);
   for(const row of performance){const tr=el('tr');for(const text of [strategyNames[row.strategy]||row.strategy.replaceAll('_',' ').toLowerCase(),String(row.filled_closed),cash(row.gross_pnl),row.charges_complete?cash(row.reported_charges):'Awaiting final fees',row.charges_complete?cash(row.net_pnl):'Awaiting final fees'])tr.append(el('td',text));table.append(tr);}
   wrap.append(table);$('strategy-performance').append(wrap);
  }else $('strategy-performance').append(el('p',d.ledger?.available?'No completed filled trades recorded.':'Execution history is unavailable.','subtle'));
 }
 const market=observer?.spot!=null?`NIFTY completed close ${points(observer.spot)} · ${at(observer.spot_at)}${observer.opening!=null?` · Session open ${points(observer.opening)}`:''}${observer.previous_close!=null?` · Previous close ${points(observer.previous_close)}`:''}`:'';
 $('strategy-market').textContent=market;
 const health=rt?.input_health;
 $('input-history').textContent=!health||!health.fresh?'Completed-candle readiness is unknown until a fresh input check arrives.':
  [['spot','NIFTY'],['future','Futures']].map(([key,name])=>{const row=health[key]||{};return `${name}: ${row.latest_completed?`through ${at(row.latest_completed)}`:'no completed candles'}${row.missing_minutes>0?` · ${row.missing_minutes} missing session minute(s), first ${at(row.first_missing)}`:row.current_complete===false?' · latest completed minute missing':''}${row.error?` · ${row.error}`:''}`;}).join(' / ')+
  ` / Options: ${health.options?.ready??'unknown'} of ${health.options?.requested??'unknown'} watched contracts have the required three completed minutes.`;
 const display=checks.filter(row=>!hasRoster||configured.includes(row.strategy)).map(row=>({...row,current:rt?.fresh===true,source:'Trading service'}));
 for(const row of observerChecks)if(!configured.includes(row.strategy))display.push({...row,current:observer.fresh===true,source:'Read-only monitor',lastDecision:(observer.last_decisions||[]).find(v=>v.strategy===row.strategy)});
 if(configured.includes('CAS_LAG_V1')||(!configured.length&&rt?.observation?.expiry)){
  const expiryToday=rt.expiry_today??(istDay(rt.observation?.expiry)===istDay(d.server_time));
  const closed=expiryToday&&rt?.observation?.phase==='CAS_STOP';
  display.push({strategy:'CAS_LAG_V1',current:rt?.fresh===true,source:'Trading service',state:closed?'CLOSED':expiryToday?'WAITING':'NOT_APPLICABLE',enabled:true,funded_enabled:Array.isArray(funded)?funded.includes('CAS_LAG_V1'):null,reason:closed?'Provider reports the auction closed. No new auction entries; exit and settlement handling continue.':expiryToday?'Expiry confirmed from current contracts. Auction entry checks are below.':`Next loaded NIFTY expiry: ${shortDate(rt.observation?.expiry)}.`});
 }
 for(const row of display)row.lastSignal=(d.ledger?.last_signals||[]).find(v=>v.strategy===row.strategy);
 $('strategy-empty').hidden=display.length>0;
 display.sort((a,b)=>Number(b.funded_enabled===true)-Number(a.funded_enabled===true));
 if(!changed('strategy-checks',{display,performance}))return;
 const expanded=new Set([...$('strategy-checks').querySelectorAll('details.strategy-family[open]')].map(n=>n.dataset.family));
 $('strategy-checks').replaceChildren();
 const groups=new Map();
 for(const row of display){
  const wrap=el('div',undefined,'connection-row'),info=el('div');
  const state=row.current?row.state:'UNKNOWN',label={WAITING:'Waiting',CLOSED:'Closed',NO_SIGNAL:'No signal',SIGNAL:'Signal observed',NOT_APPLICABLE:'Not applicable',DISABLED:'Disabled',UNKNOWN:'Unknown'}[state]||'Unknown';
  const window=row.strategy==='GAP_FADE_DOUBLE'?'09:45–11:30 IST · every 5 minutes':row.strategy==='NIFTY_SELLOFF_REBOUND_1510'?'15:10 IST · may hold into the next session':row.strategy==='CAS_LAG_V1'?'Eligible expiry · auction phase required':`${row.scope==='EXPIRY'?'Expiry sessions':row.scope==='ORDINARY'?'Non-expiry sessions':'Verified trading sessions'} · ${row.exit_policy||'DOUBLE'} exit`;
  info.append(el('p',strategyNames[row.strategy]||row.strategy.replaceAll('_',' ').toLowerCase(),'connection-name'),el('p',`${row.source} · ${window}`,'connection-detail'));
  const finished=row.current&&row.strategy==='GAP_FADE_DOUBLE'&&row.reason==='OUTSIDE_STRATEGY_WINDOW'&&new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(d.server_time))>='11:30';
  info.append(el('p',row.current?(finished?'Morning entry window finished. No new entry from this engine today.':row.strategy==='CAS_LAG_V1'?row.reason:conditionSummary(row)):'This observation is stale. Current checks are unknown.','connection-detail'));
  const values=row.conditions?.length?[]:[];
  if(row.spot!=null)values.unshift(`NIFTY minute close ${points(row.spot)}`);
  if(row.entry_rule)info.append(el('p',row.entry_rule,'connection-detail'));
  if(row.evaluated_at)values.push(`Checked ${at(row.evaluated_at)}`);
  if(values.length)info.append(el('p',values.join(' · '),'connection-detail'));
  if(row.family&&Object.keys(row.details||{}).length){
   const inputs=el('details',undefined,'decision-inputs');inputs.append(el('summary','Observed market inputs'));
   const ratios=new Set(['gap','fraction_filled','future_5m_return','open_return','spot_15m','future_15m','future_oi_5m','future_5m','basis_change','bank_15m','it_15m','gift_15m','trend_30m','pullback_10m','move_15m','first_half_hour_return','premium_return','premium_return_3m','oi_change','own_oi','opposite_oi','opposite_return','vix_15m','pcr_change_5m','pcr_change','prior_trend_20d']);
   for(const [key,value] of Object.entries(row.details))inputs.append(el('p',`${key.replaceAll('_',' ')}: ${ratios.has(key)?pct(value):Number(value).toLocaleString('en-IN',{maximumFractionDigits:3})}`,'connection-detail'));
   info.append(inputs);
  }
  if(row.ranking_available)info.append(el('p',`${row.filled_closed} filled closed trades · mean return after estimated costs ${pct(row.mean_estimated_net_return)}.`,'connection-detail'));
  else if(row.family)info.append(el('p','Selection score unavailable: fewer than three filled closed trades.','connection-detail'));
  if(row.next_check_at)info.append(el('p',`Next scheduled check: ${at(row.next_check_at)}.`, 'connection-detail'));
  const signal=row.lastSignal;
  if(signal){
   const explanations={ONE_LOT_UNAFFORDABLE:'One lot exceeds the available entry budget',OPTION_BOOK_UNAVAILABLE_OR_STALE:'An affordable contract has no current usable quote',FIXED_LIMIT_ALREADY_MISSED:'The ask moved above the fixed entry limit',OPTION_MINUTES_UNAVAILABLE:'Required completed option candles are missing',NO_AFFORDABLE_LIQUID_CONTRACT:'No contract passed affordability and liquidity checks',ENTRY_NOT_PERMITTED:'Execution permission was unavailable',OPTION_LIQUIDITY_BELOW_POLICY:'Recent volume or open interest is below the entry requirement',OPTION_DEPTH_BELOW_ONE_LOT:'Less than one lot is available inside the limit',OPTION_LIMIT_OUTSIDE_BAND:'The fixed limit is outside the permitted price band',READY:'Contract passed entry checks'};
   info.append(el('p',`Last qualifying signal (historical) · ${at(signal.evaluated_at)} · ${signal.side==='CE'?'CALL':'PUT'}`,'last-strategy-decision'));
   const outcome=signal.outcome==='ENTRY_DEADLINE_MISSED'?'Entry skipped: entry window expired.':signal.outcome==='DECISION_COMMITTED'?'Order decision recorded. Check orders and fills for execution.':signal.outcome==='PRIOR_REBOUND_EXITED_TODAY'?'Entry skipped: this engine already exited a rebound today.':'Execution outcome was not recorded.';
   const blocker=explanations[signal.blocking_reason]||'Prior blocking reason was not recorded.';
   info.append(el('p',`${outcome}${signal.outcome==='DECISION_COMMITTED'?'':` ${blocker}`}`,'connection-detail'));
   if(signal.outcome!=='DECISION_COMMITTED'&&signal.candidate_checks?.length){
    const detail=el('details',undefined,'decision-inputs');
    detail.append(el('summary','Contracts checked for this entry'));
    for(const check of signal.candidate_checks){
     const costs=check.one_lot_cash!=null?` · One-lot cash including fee reserve ${cash(check.one_lot_cash)} / budget ${cash(check.budget)}`:'';
     detail.append(el('p',`Strike ${points(check.strike)}: ${explanations[check.reason]||'Check result unavailable'}${costs}`,'connection-detail'));
    }
    info.append(detail);
   }
  }
  const last=row.lastDecision;
  if(last&&last.evaluated_at!==row.evaluated_at&&['SIGNAL','NO_SIGNAL'].includes(last.state))info.append(el('p',`Last completed decision · ${at(last.evaluated_at)}: ${conditionSummary(last)}`, 'last-strategy-decision'));
  info.append(el('p',row.current?(row.funded_enabled===true?'Real-money entries permitted':row.funded_enabled===false?'Observation only · new money entries disabled':'Funded permission not reported'):'Funded permission is historical until the service updates.','connection-detail'));
  const perf=performanceAt(row.strategy);
  if(perf){
   info.append(el('p',`${perf.filled_closed} completed trades · gross ${cash(perf.gross_pnl)} · ${perf.charges_complete?`net ${cash(perf.net_pnl)} after ${cash(perf.reported_charges)} broker charges`:'final net awaiting broker fees'}`,'connection-detail'));
   const history=el('details',undefined,'decision-inputs');history.append(el('summary',`Execution history · latest ${perf.trades?.length||0} trades`));
   for(const trade of perf.trades||[])history.append(el('p',`${at(trade.entry_at)} → ${at(trade.exit_at)} · ${trade.quantity} units · bought ${cash(trade.entry_price)}, sold ${cash(trade.exit_price)} · gross ${cash(trade.gross_pnl)}${trade.charges_complete?` · net ${cash(trade.net_pnl)}`:' · final fees pending'}`,'connection-detail'));
   info.append(history);
  }else info.append(el('p',d.ledger?.available?'No completed filled trades recorded for this configuration.':'Execution history is unavailable.','connection-detail'));
  wrap.append(info,badge(label,state==='UNKNOWN'?'warn':''));
  if(row.conditions?.length){
   const detail=el('details',undefined,'decision-inputs');
   detail.append(el('summary',`Why this decision · inputs at ${at(row.evaluated_at)}`),conditionList(row,row.current));
   wrap.append(detail);
  }else if(row.strategy!=='CAS_LAG_V1')wrap.append(el('p',row.reason==='STRATEGY_INPUT_UNAVAILABLE'?'Condition inputs are unavailable because a market-data request failed.':row.entry_rule?(row.reason==='EXCHANGE_CLOSED'?'The exchange is closed; no entry condition is evaluated outside its verified session.':'The rule and observed inputs above explain this check. Missing inputs cannot be treated as a qualifying signal.'):'This service has not provided condition details for this rule.','condition-caption'));
  if(last&&last.evaluated_at!==row.evaluated_at&&['SIGNAL','NO_SIGNAL'].includes(last.state)){
   const detail=el('details',undefined,'last-decision-inputs');
   detail.append(el('summary',`Inputs at the last decision · ${at(last.evaluated_at)}`));
   if(last.conditions?.length)detail.append(conditionList(last,true));
   else{
    const labels={gap:'Opening gap',fraction_filled:'Gap filled',future_5m_return:'Futures 5 min',open_return:'From open'};
    const recorded=Object.entries(last.details||{}).filter(([key])=>key in labels).map(([key,value])=>`${labels[key]}: ${pct(value)}`);
    if(typeof last.details?.persistent==='boolean')recorded.push(`Persistence: ${last.details.persistent?'passed':'failed'}`);
    detail.append(el('p',recorded.length?recorded.join(' · '):'Detailed inputs were not recorded by the earlier service version.','connection-detail'));
   }
   wrap.append(detail);
  }
  const family=row.family||row.strategy;
  if(!groups.has(family))groups.set(family,[]);groups.get(family).push({row,wrap});
 }
 for(const [family,rows] of groups){
  if(rows.length===1){$('strategy-checks').append(rows[0].wrap);continue;}
  const group=el('details',undefined,'strategy-family');group.dataset.family=family;group.open=expanded.has(family);
  const summary=el('summary'),counts=new Map();for(const {row} of rows){const status=row.current?row.state:'UNKNOWN';counts.set(status,(counts.get(status)||0)+1);}
  const fundedCount=rows.filter(x=>x.row.current&&x.row.funded_enabled===true).length;
  summary.append(el('strong',family.replaceAll('_',' ').toLowerCase()),el('span',`${rows.length} variants · ${fundedCount} funded · ${[...counts].map(([s,n])=>`${n} ${s.replaceAll('_',' ').toLowerCase()}`).join(' / ')}`,'connection-detail'));
  group.append(summary);for(const {wrap} of rows)group.append(wrap);$('strategy-checks').append(group);
 }
}
function renderDecision(d){
 const rt=d.runtime,o=rt?.observation,a=d.account,current=rt?.fresh===true;
 const titles={NO_TRADE_DAY:'Waiting for an expiry session',ARMED_WAITING_SESSION:'Waiting for the trading window',ARMED_WAITING_SIGNAL:'Watching for an auction signal',POSITION_OPEN:'Managing an open position',ENTRY_PENDING:'Entry submitted · awaiting execution',EXIT_PENDING:'Reducing the position',SETTLEMENT_PENDING:'Waiting for settlement',RECOVERING:'Reconciling the account',ENTRY_HALTED:'New entries are blocked',DISARMED:'New entries are disabled'};
 let title=current?(titles[rt.state]||'Waiting for a decision update'):'Current bot state is unknown';
 let reason=current?rt.reason:'The dashboard needs a fresh bot observation before it can describe the current state.';
 if(current&&rt.state==='POSITION_OPEN'&&(!reason||reason==='No specific decision reason was recorded.'))reason='The position is open. The bot is monitoring its recorded exit rules; current P&L is shown above.';
 let next='';
 const directional=(rt?.strategies||[]).some(name=>name!=='CAS_LAG_V1');
 if(current&&rt.state==='NO_TRADE_DAY'){
  reason='This strategy trades NIFTY options on their expiry session. It is not looking for entries today.';
  next=o?.expiry?`Loaded contract expiry: ${shortDate(o.expiry)}. Route checks start at 15:05 IST on an eligible session.`:'The next session will be confirmed from the contract catalogue.';
 }else if(current&&rt.monitoring_mode==='IDLE'&&['ARMED_WAITING_SESSION','ARMED_WAITING_SIGNAL'].includes(rt.state)){
  title='Waiting for the trading window';reason='Trading is outside the active auction window. Received market data and its age are shown below.';next='Eligible expiry sessions: route checks 15:05–15:19:30; auction entries 15:20–15:30 IST. A verified final-value path can run until 15:38:30.';
 }else if(current&&['ARMED_WAITING_SIGNAL','ARMED_WAITING_SESSION'].includes(rt.state)){
  next=!rt.broker_route_verified?'Next: qualify the broker order route.':!o?.iep?'Next: receive a usable official auction value.':'Next: evaluate the next auction observation or option quote.';
 }
 if(current&&directional&&['ARMED_WAITING_SIGNAL','ARMED_WAITING_SESSION','WAITING_EXCHANGE_SESSION'].includes(rt.state)){
  title=rt.state==='WAITING_EXCHANGE_SESSION'?'Waiting for an exchange session':'Watching configured strategies';
  reason='The strategy checks below show the latest evaluation and missing inputs.';
  next=rt.broker_route_verified?'Signals still need current option depth, available cash and final order checks.':'New entries also require broker order-route qualification.';
 }
 if(current&&rt.authority==='ENABLED'&&rt.broker_route_verified===false&&['ARMED_WAITING_SIGNAL','ARMED_WAITING_SESSION','ENTRY_HALTED'].includes(rt.state)){
  title='Not entering trades — order route unverified';
  reason='Real-money permission is enabled, but the broker order route has not passed its required check. A qualifying signal cannot become an entry yet.';
  const used=rt.route_attempts_used,limit=rt.route_attempt_limit;
  next=Number.isSafeInteger(used)&&used>=0&&Number.isSafeInteger(limit)&&limit>0?`Route attempts used this session: ${used} of ${limit}. ${used>=limit?'No further attempt is permitted under the saved allowance.':'A bounded automatic check can run in its eligible open-session window.'}`:'The route check must complete within the saved probe allowance. Cancelling an unfilled route-test order is not a strategy trade.';
 }
 if(current&&rt.authority==='ENABLED'&&rt.software_verified===false&&!['POSITION_OPEN','ENTRY_PENDING','EXIT_PENDING','SETTLEMENT_PENDING','RECOVERING'].includes(rt.state)){
  title='New entries blocked by software verification';
  reason='The running software does not have matching verification. Enabled trading authority cannot override this check.';
  next='The service needs a verified release before it can qualify the order route or submit a new entry.';
 }
 if(current&&rt.authority==='DISABLED'&&!['POSITION_OPEN','EXIT_PENDING','SETTLEMENT_PENDING','RECOVERING'].includes(rt.state)){
  title='New entries are disabled';reason='The bot can continue observing and handling existing positions.';next='';
 }
 if(d.daily_monitor)title='Funded trader: '+title.charAt(0).toLowerCase()+title.slice(1);
 $('now-title').textContent=title;$('now-reason').textContent=reason||'No specific decision reason was recorded.';$('next-step').textContent=next;$('next-step').hidden=!next;
 const fills=d.ledger?.counts?.fills,knownFills=d.ledger?.available===true&&Number.isSafeInteger(fills)&&fills>=0;
 $('fill-count').textContent=knownFills?String(fills):'—';
 $('fill-note').textContent=knownFills?fills===0?'No fills recorded in the bot ledger':'Fill records, not completed trades':'Execution ledger unavailable';
 $('realised-note').textContent=a?.realised_pnl==null?'Not reported by Dhan':'As reported by Dhan';$('unrealised-note').textContent=a?.unrealised_pnl==null?'Not reported by Dhan':'As reported by Dhan';
 const settlement=d.ledger?.cash_reconciliation;
 const usableSettlement=['REPORTED_CHARGES_COMPLETE','CHARGES_PENDING'].includes(settlement?.status);
 $('cash-reconciliation').hidden=!usableSettlement;
 $('cash-reconciliation').textContent=!usableSettlement?'':settlement.status==='REPORTED_CHARGES_COMPLETE'?
  `Recorded closed bot trades: gross ${cash(settlement.gross_pnl)} − broker-reported charges ${cash(settlement.reported_charges)} = net ${cash(settlement.net_after_reported_charges)}. ${settlement.closed_trades} closed trades; latest fill ${at(settlement.last_trade_at)}. These results are separate from today’s account P&L.`:
  `Recorded closed bot trades: gross ${cash(settlement.gross_pnl)}. Complete charges are available for ${settlement.orders_with_complete_charges} of ${settlement.executed_orders} executed orders; net profit is not yet confirmed.`;
 $('signal-value').textContent=points(o?.iep);$('reference-value').textContent=points(o?.reference);
 $('index-value').textContent=points(o?.ltp);
 const ltpAge=elapsed(o?.ltp_at,d.server_time),receiptAge=elapsed(o?.ltp_received_at,d.server_time);
 $('index-age').textContent=o?.ltp==null?'No accepted pre-auction index observation.':`${current&&ltpAge!==null&&ltpAge<=5?'Recent':'Last observed'} · provider ${age(ltpAge)} · received ${age(receiptAge)}`;
 const inputFeeds=rt?.feed_health||{};
 $('input-feeds').textContent=!current?'Live data receipt is unknown until a fresh bot status arrives.':[['signal','Index feed'],['market','Options feed']].map(([key,label])=>{const f=inputFeeds[key],seen=elapsed(f?.last_received_at,d.server_time);return `${label}: ${f?.connected===true?'connected':f?.connected===false?'disconnected':'unknown'} · ${seen===null?'no message observed':age(seen)}`;}).join(' / ');
 const signalAge=elapsed(o?.iep_at,d.server_time),recent=current&&signalAge!==null&&signalAge<=5;
 $('signal-direction').textContent=o?.direction?`${o.direction==='CE'?'Calls':'Puts'}${recent?'':' · last observed'}`:'Awaiting signal';
 $('input-stamp').textContent=o?.iep_at?`${recent?'Accepted':'Last accepted'} · ${age(signalAge)}`:'No accepted auction value';
 const phases={CTS_CLOSE:'Continuous trading closed',CAS_LM_START:'Auction collection open',CAS_M_STOP:'Auction collection in progress',CAS_STOP:'Auction collection ended',UNKNOWN:'Auction phase unknown'};
 $('phase-context').textContent=o?.phase?`${phases[o.phase]||'Auction phase unknown'} · ${at(o.phase_at)}${o.final_value?' · Verified final value '+points(o.final_value):''}`:'Auction inputs appear only when accepted. The NIFTY observation above comes from the pre-auction reference feed, which stops collecting at 15:15 IST; it is not an auction value.';
 const gateRows=[['software_verified','Software checks'],['current_account_funded','Funded account'],['broker_route_verified','Order route'],['official_cas_signal_seen','Auction session observed']];
 const gateValues=gateRows.map(([key,label])=>({label,pass:rt?.[key],text:rt?.[key]===true?'Observed':rt?.[key]===false?'Waiting':'Unknown'}));
 gateValues.push({label:'Frozen reference',pass:!!o?.reference,text:o?.reference?'Recorded':'Waiting'},{label:'Accepted auction value',pass:recent,text:recent?'Recent':o?.iep?'Last observed':'Waiting'});
 if(changed('decision-gates',[current,gateValues])){$('gates').replaceChildren();for(const g of gateValues){const li=el('li');li.append(el('span',g.label),badge(!current?'Unknown':g.text,current&&g.pass?'good':''));$('gates').append(li);}}
 const noPnl=a?.realised_pnl==null&&a?.unrealised_pnl==null;
 $('realised-metric').hidden=noPnl;$('unrealised-metric').hidden=noPnl;$('pnl-unreported').hidden=!noPnl;$('account-strip').className='account-strip'+(noPnl?' no-pnl':'');
 const watch=o?.watchlist||[];
 rows('watch-body',watch.map(r=>({...r,age_seconds:elapsed(r.observed_at,d.server_time),current})),[
  {title:'Contract',read:r=>`NIFTY ${points(r.strike)} ${r.option_type||''} · ${shortDate(r.expiry)}`},
  {title:'Bid / ask',numeric:true,read:r=>{const cell=el('div');cell.append(el('span',`${cash(r.bid)} / ${cash(r.ask)}`),el('small',`${r.bid_quantity??'—'} / ${r.ask_quantity??'—'} units`,'depth-note'));return cell;}},
  {title:'Last price / activity',numeric:true,read:r=>{const cell=el('div');cell.append(el('span',cash(r.last_price)),el('small',`Vol ${r.volume??'—'} / OI ${r.open_interest??'—'}`,'depth-note'));return cell;}},
  {title:'One lot',numeric:true,read:r=>cash(r.one_lot_cash)},
  {title:'Conditional intrinsic',numeric:true,read:r=>cash(r.conditional_intrinsic)},
  {title:'Observation',read:r=>`${r.confirmations??0} confirmations · ${r.current?'':'historical · '}${age(r.age_seconds)}`},
 ]);
 $('watch-table').hidden=watch.length===0;$('watch-note').hidden=!watch.length;$('watch-empty').hidden=watch.length>0;
 $('watch-empty').textContent=!o?'Market input observations are not available from this bot version.':'No usable option books retained. Check the options feed receipt above; waiting for the trading window does not confirm that data is arriving.';
 $('watch-stamp').textContent=rt?.books_observed==null?'':`${rt.books_observed} retained books`;
 const entry=d.ledger?.last_entry;
 $('last-entry').textContent=entry?`${at(entry.occurred_at)} · ${strategyNames[entry.strategy]||(entry.strategy?entry.strategy.replaceAll('_',' ').toLowerCase():'Strategy not reported')} · NIFTY ${points(entry.strike)} ${entry.option_type||''}. Selected ${entry.quantity??'unknown'} units at a limit of ${cash(entry.limit)}.${entry.reference!=null?` Reference ${points(entry.reference)}; ${entry.confirmations??'unknown'} confirmations.`:''}`:d.ledger?.available?'No entry decision has been recorded.':'The decision ledger is unavailable.';
 $('positions-table').hidden=!a?.positions?.length;$('positions-section').hidden=Array.isArray(a?.positions)&&a.positions.length===0&&a.fresh===true;
 const exits=(d.ledger?.active_trades||[]).filter(t=>t.quantity>0).map(t=>{
  const stop=t.stop_fraction!=null?`${Math.round((1-Number(t.stop_fraction))*100)}% below ${t.trailing?'the highest completed minute close':'the entry premium'}`:'Stop policy unavailable';
  const target=t.target_known?(t.target_multiple==null?'No fixed profit target':`Profit target: ${t.target_multiple}× entry`):'Profit target unavailable';
  const protect=t.net_protection?` Net-profit protection retains ${Math.round(Number(t.net_protection.retain)*100)}% of observed peak liquidation profit after estimated costs. Recorded profit floor: ${cash(t.net_protection.floor)}. A gap or failed fill can still realise less.`:'';
  return `${t.strategy.replaceAll('_',' ')}: ${stop}. ${target}. Scheduled exit ${at(t.exit_due)}. ${t.exit_trigger?`Exit triggered: ${t.exit_trigger.replaceAll('_',' ')}; due ${at(t.trigger_due)}.`:'No exit trigger recorded.'}${protect}${t.trailing?' A trailing stop can give back profit and close below entry.':''} Recorded policy; the current trailing price is not supplied by this bot version.`;
 });
 $('position-exits').hidden=!exits.length;$('position-exits').textContent=exits.join(' ');
 const feeds=rt?.feed_health||{};const values=Object.values(feeds);const connected=values.filter(f=>f.connected===true).length;
 $('system-summary').textContent=!current?'Current health unknown':`${connected} of 3 sockets connected`;
}

function render(d){
 if(state.data?.server_time&&d.server_time&&Date.parse(d.server_time)<Date.parse(state.data.server_time))return;
 d=structuredClone(d);
 if(d.history_unchanged===true&&d.history===undefined)d.history=state.data?.history;
 for(const [key,ttl] of [['collector',60],['runtime',45],['account',60],['connections',900],['daily_monitor',90]]){const v=d[key];if(v?.observed_at){const seconds=(Date.parse(d.server_time)-Date.parse(v.observed_at))/1000;v.age_seconds=seconds>=-5?Math.max(0,Math.floor(seconds)):null;if(!Number.isFinite(seconds)||seconds>ttl||seconds< -5)v.fresh=false;}}
 if(d.runtime&&!d.collector?.fresh)d.runtime.fresh=false;
 if(d.daily_monitor&&!d.collector?.fresh)d.daily_monitor.fresh=false;
 if(d.runtime&&!d.runtime.fresh)d.runtime.authority='UNKNOWN';
 state.generation++;state.data=d;const rt=d.runtime;renderTimings(rt);renderHistory(d);renderSelection(d);renderStrategies(d);const a=d.account;const cs=d.connections;const ledger=d.ledger;$('observation').textContent=rt?.observed_at?`${((rt.strategies||[]).length>3?`${rt.strategies.length} enabled strategies`:(rt.strategies||[]).map(s=>strategyNames[s]||s).join(' / '))||(rt.observation?.expiry?'Expiry auction service':'Strategy not reported')} · ${rt.fresh?'Updated':'Last observed'} ${at(rt.observed_at)}`:'Waiting for a bot observation.';
 const feedState=renderFeeds(rt,d.server_time);
 const notice=$('notice');notice.className='notice';const message=monitoringNotice(d,feedState);notice.textContent=message.text;if(message.kind)notice.classList.add(message.kind);notice.hidden=message.kind==='healthy';
 $('cash-label').textContent=a?.fresh?'Available cash':'Last observed cash';$('cash').textContent=cash(a?.available_cash);$('cash-age').textContent=a?`${age(a.age_seconds)} · ${a.fresh?'broker read':'historical observation'}`:'No broker observation';pnl('realised',a?.realised_pnl);pnl('unrealised',a?.unrealised_pnl);$('position-count').textContent=a?.open_position_count??'—';$('position-note').textContent=a?.fresh?'Current broker snapshot':a?'Last observed account':'Awaiting account data';
 const au=rt?.authority||'UNKNOWN';$('authority').className='authority '+(au==='ENABLED'?'enabled':au==='UNKNOWN'?'neutral':'');$('authority').textContent=au==='ENABLED'?'Trading authority enabled':au==='DISABLED'?'New entries disabled':'Trading status unknown';$('authority-note').textContent=au==='ENABLED'?'The bot reports write authority and is armed. Individual orders still require all entry conditions.':au==='DISABLED'?'The bot reports new entries disabled. Existing positions may still require exit handling.':'No current bot observation establishes whether trading is enabled.';$('heartbeat').textContent=rt?.observed_at?`${rt.fresh?'Current':'Stale'} · ${age(rt.age_seconds)}`:'Unknown';$('runtime-state').textContent=(rt?.state||'UNKNOWN').replaceAll('_',' ').toLowerCase();$('books').textContent=rt?.books_observed??'—';$('contracts').textContent=rt?.contract_count??'—';$('clock-error').textContent=rt?.clock_uncertainty_ms===null||rt?.clock_uncertainty_ms===undefined?'—':rt.clock_uncertainty_ms+' ms';$('decision').textContent=rt?.reason||'No decision observation is available.';
 $('connection-age').textContent=cs?.observed_at?`${cs.fresh?'Recent check':'Historical check'} · ${at(cs.observed_at)}`:'No explicit connection check has been recorded.';if(changed('diagnostics',[cs?.checks,cs?.fresh])){$('connections').replaceChildren();for(const [index,c] of (cs?.checks||Object.keys(names).map(name=>({name,status:'UNKNOWN',facts:{}}))).entries()){const row=el('div',undefined,'connection-row');const text=el('div');text.append(el('p',names[c.name]||'Connection','connection-name'),el('p',details(c),'connection-detail'));let status=c.status==='PASS'?'Passed':c.status==='FAIL'?'Failed':c.status==='NO_DATA'?'No data':c.status==='SKIP'?'Skipped':'Unknown';const kind=c.status==='FAIL'?'bad':c.status==='PASS'&&cs?.fresh?'good':'warn';if(c.status==='PASS'&&!cs?.fresh)status='Past pass';row.append(text,badge(status,kind));$('connections').append(row);}}
 $('positions-stamp').textContent=a?at(a.observed_at)+(a.positions_truncated?' · first 100 shown':''):'No observation';rows('positions',a?.positions||[],[{read:r=>r.symbol||r.security_id},{read:r=>r.product},{numeric:true,read:r=>r.quantity},{numeric:true,read:r=>cash(r.average_price)},{numeric:true,read:r=>cash(r.unrealised)}]);$('positions-empty').hidden=Boolean(a?.positions?.length);$('positions-empty').textContent=a?'Dhan reported no open positions in this snapshot.':'No verified account observation is available.';
 $('ledger-count').textContent=ledger?.available?`${ledger.counts.intents} intents · ${ledger.counts.fills} fills`:'Ledger unavailable';const events=[...(ledger?.orders||[]).map(r=>({t:r.occurred_at,title:`${r.side||'Order'} · ${r.security_id||'Unknown contract'}`,description:`${r.quantity??'—'} units at ${cash(r.price)} · ${r.state}`})),...(ledger?.fills||[]).map(r=>({t:r.occurred_at,title:'Fill recorded · '+(r.security_id||'Unknown contract'),description:`${r.quantity??'—'} units at ${cash(r.price)}`})),...(ledger?.incidents||[]).map(r=>({t:r.occurred_at,title:'Runtime incident recorded',description:'Details remain in the bot’s private operational logs.'}))].sort((x,y)=>(y.t||'').localeCompare(x.t||'')).slice(0,30);if(changed('activity',events)){$('timeline').replaceChildren();for(const e of events){const li=el('li');const time=el('time',at(e.t));if(e.t)time.dateTime=e.t;const info=el('div');info.append(el('strong',e.title),el('p',e.description));li.append(time,info);$('timeline').append(li);}}$('activity-empty').hidden=events.length>0;$('activity-empty').textContent=ledger?.available?'The ledger contains no recorded trading activity yet.':'The bot’s ledger could not be read. This does not establish that no trades occurred.';renderOrders();renderDecision(d);
}
async function refresh(){if(state.fetching)return;state.fetching=true;const generation=state.generation;$('refresh').disabled=true;try{const fullHistory=state.historyFetchedAt===null||Date.now()-state.historyFetchedAt>=60000;const response=await fetch(fullHistory?'/api/status':'/api/status?history=omit',{cache:'no-store',credentials:'same-origin',signal:AbortSignal.timeout(8000)});if(response.status===401){window.location.replace('/login');throw new Error('AUTH');}const data=await response.json();if(!response.ok&&response.status!==503)throw new Error('HTTP');if(fullHistory&&data.history){state.historyFetchedAt=Date.now();if(state.data?.server_time&&Date.parse(data.server_time)<Date.parse(state.data.server_time))render({...state.data,history:data.history,history_unchanged:false});}render(data);$('refresh-status').textContent='Last refresh '+at(new Date().toISOString());}catch(error){if(generation!==state.generation)return;if(state.data){const old=structuredClone(state.data);old.collector={...old.collector,fresh:false};for(const key of ['runtime','account','connections','daily_monitor'])if(old[key])old[key].fresh=false;if(old.runtime)old.runtime.authority='UNKNOWN';render(old);}$('notice').hidden=false;$('notice').className='notice error';$('notice').textContent=error.message==='AUTH'?'Your dashboard sign-in is required. Reload the page to sign in.':'Dashboard connection lost. Any values below are historical; current trading status is unknown.';$('authority').textContent='Trading status unknown';$('authority').className='authority neutral';$('authority-note').textContent='The latest dashboard request failed.';$('refresh-status').textContent='Refresh failed';}finally{state.fetching=false;$('refresh').disabled=false;}}
$('history-date').addEventListener('change',()=>{state.historyDate=$('history-date').value;renderHistory(state.data);});
for(const [id,offset] of [['history-today',0],['history-yesterday',86400000]])$(id).addEventListener('click',()=>{if(!state.data?.server_time)return;state.historyDate=istDay(new Date(Date.parse(state.data.server_time)-offset).toISOString());renderHistory(state.data);});
$('refresh').addEventListener('click',refresh);$('order-filter').addEventListener('change',renderOrders);const tabs=[...document.querySelectorAll('[data-source]')];function selectTab(tab){state.source=tab.dataset.source;for(const b of tabs){b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;}$('order-panel').setAttribute('aria-labelledby',tab.id);renderOrders();}for(const tab of tabs){tab.addEventListener('click',()=>selectTab(tab));tab.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const i=event.key==='Home'?0:event.key==='End'?tabs.length-1:(tabs.indexOf(tab)+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;selectTab(tabs[i]);tabs[i].focus();});}
for(const button of document.querySelectorAll('[data-copy]'))button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText($(button.dataset.copy).textContent);button.textContent='Copied';}catch{button.textContent='Select text to copy';}setTimeout(()=>button.textContent=button.dataset.copy.includes('check')||button.dataset.copy.includes('pause')?'Copy commands':'Copy command',2400);});
for(const link of document.querySelectorAll('.navigation a'))link.addEventListener('click',()=>{document.querySelectorAll('.navigation a').forEach(a=>a.removeAttribute('aria-current'));link.setAttribute('aria-current','page');});
function clock(){ $('clock').textContent=new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date())+' IST'; }clock();setInterval(clock,1000);
const monitor=new DashboardStream({source:url=>new EventSource(url+'?history=omit'),onTime:(stamp,observations)=>{if(!state.data)return;const data=structuredClone(state.data);for(const key of ['collector','runtime','account','connections','daily_monitor']){if(data[key]&&typeof observations?.[key]==='string')data[key].observed_at=observations[key];}render({...data,server_time:stamp});},onData:data=>{render(data);$('refresh-status').textContent='Live updates · '+at(data.server_time);},refresh,signIn:()=>window.location.replace('/login')});
if(!document.hidden)monitor.start();
setInterval(()=>{monitor.tick();if(monitor.running&&(state.historyFetchedAt===null||Date.now()-state.historyFetchedAt>=60000))monitor.fallback();},1000);
document.addEventListener('visibilitychange',()=>{if(document.hidden)monitor.stop();else monitor.start();});
window.addEventListener('pagehide',()=>monitor.stop());
window.addEventListener('pageshow',()=>{if(!document.hidden)monitor.start();});
