function brasiliaParts(){
  const fmt=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  const p=Object.fromEntries(fmt.formatToParts(new Date()).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
  return {y:+p.year,m:+p.month,d:+p.day,h:+p.hour,min:+p.minute,s:+p.second};
}
function mins(t){const [h,m]=t.split(':').map(Number);return h*60+m}
function formatDuration(sec){sec=Math.max(0,Math.floor(sec)); const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60; return [h,m,s].map(v=>String(v).padStart(2,'0')).join(':')}
function updateSessions(){
  const n=brasiliaParts(); const nowSec=n.h*3600+n.min*60+n.s;
  document.getElementById('brasilia-clock').textContent=[n.h,n.min,n.s].map(v=>String(v).padStart(2,'0')).join(':');
  document.querySelectorAll('.session-card').forEach(card=>{
    const o=mins(card.dataset.open)*60,c=mins(card.dataset.close)*60; let open=false,target,label;
    if(c>o){open=nowSec>=o&&nowSec<c;if(open){target=c;label='FECHA EM'}else{target=nowSec<o?o:o+86400;label='ABRE EM'}}
    else{open=nowSec>=o||nowSec<c;if(open){target=nowSec<c?c:c+86400;label='FECHA EM'}else{target=o;label='ABRE EM'}}
    card.classList.toggle('open',open); card.querySelector('.session-state').textContent=open?'ABERTA':'FECHADA';
    card.querySelector('.countdown-label').textContent=label; card.querySelector('.countdown-value').textContent=formatDuration(target-nowSec);
  });
}
updateSessions();setInterval(updateSessions,1000);
