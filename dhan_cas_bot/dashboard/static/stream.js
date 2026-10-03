'use strict';
// A one-way status stream. The browser never connects to either broker.
class DashboardStream {
 constructor({onData, refresh, signIn, source = url => new EventSource(url), now = () => Date.now()}) {
  this.onData=onData; this.refresh=refresh; this.signIn=signIn; this.source=source; this.now=now;
  this.connection=null; this.lastPush=null; this.lastFallback=null; this.running=false;
 }
 start() {
  if(this.running)return;
  this.running=true;
  this.fallback();
  try {
   const connection=this.source('/api/events'); this.connection=connection;
   connection.onmessage=event=>{
    if(this.connection!==connection)return;
    try {
     const data=JSON.parse(event.data);
     if(typeof data.available!=='boolean')throw new Error('Invalid status');
     this.lastPush=this.now(); this.onData(data);
    } catch { this.lastPush=null; this.fallback(); }
   };
   connection.onerror=()=>{if(this.connection===connection){this.lastPush=null;this.fallback();}};
   connection.addEventListener('auth-required',()=>{this.stop();this.signIn();});
  } catch { this.connection=null; }
 }
 fallback() {
  if(!this.running)return;
  if(this.lastFallback===null||this.now()-this.lastFallback>=5000){this.lastFallback=this.now();this.refresh();}
 }
 tick() {
  if(this.running&&(this.lastPush===null||this.now()-this.lastPush>5000))this.fallback();
 }
 stop() {
  this.running=false;
  if(this.connection)this.connection.close();
  this.connection=null; this.lastPush=null; this.lastFallback=null;
 }
}
