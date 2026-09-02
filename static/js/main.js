async function updateQuotes(){
  const status=document.getElementById('quote-status-text');
  const dot=document.getElementById('quote-dot');
  if(!status) return;
  try{
    const r=await fetch('/api/quotes',{cache:'no-store'}); const d=await r.json();
    if(!d.ok) throw new Error(d.error||'Falha');
    const fmt=(v)=>v==null?'--':Number(v).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('quote-xau').textContent=fmt(d.xauusd);
    document.getElementById('quote-btc').textContent=fmt(d.btc);
    document.getElementById('quote-usdbrl').textContent=fmt(d.usdbrl);
    status.textContent='Cotações atualizadas • dados de mercado podem ter atraso'; dot.classList.add('live');
  }catch(e){status.textContent='Não foi possível atualizar agora';dot.classList.remove('live')}
}
updateQuotes(); setInterval(updateQuotes,30000);
