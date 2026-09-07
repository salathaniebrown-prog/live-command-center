const CC='https://live-command-center-production-31ed.up.railway.app';

const SRC={
  usgs:'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson',
  eonet:'https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100',
  nws:'https://api.weather.gov/alerts/active'
};

function J(data,status){
  return new Response(JSON.stringify(data,null,2),{
    status:status||200,
    headers:{
      'content-type':'application/json; charset=utf-8',
      'cache-control':'no-store',
      'x-content-type-options':'nosniff'
    }
  });
}

async function fetchJson(url){
  const headers={
    accept:'application/json'
  };

  if(url.indexOf('api.weather.gov')!==-1){
    headers.accept='application/geo+json';
    headers['user-agent']='Eagle-Eyes-World-Data-V2/1.0 (https://eagle-eyes-world-data-v2.salathaniebrown.workers.dev)';
  }

  const r=await fetch(url,{
    headers:headers
  });

  const text=await r.text();

  let data;

  try{
    data=JSON.parse(text);
  }catch(e){
    data={raw:text};
  }

  if(!r.ok){
    return {
      ok:false,
      status:r.status,
      data:data
    };
  }

  return {
    ok:true,
    status:r.status,
    data:data
  };
}

function normUSGS(d){
  return (d.features||[]).map(function(f){

    const p=f.properties||{};

    const c=
      f.geometry &&
      Array.isArray(f.geometry.coordinates)
        ?f.geometry.coordinates
        :null;

    return {
      id:f.id||null,
      source:'USGS',
      type:'earthquake',
      title:p.place||null,

      observedAt:p.time
        ?new Date(p.time).toISOString()
        :null,

      location:c
        ?{
            lon:c[0],
            lat:c[1],
            depthKm:
              typeof c[2]==='number'
                ?c[2]
                :null
          }
        :null,

      severity:
        typeof p.mag==='number'
          ?p.mag
          :null,

      verified:true,
      url:p.url||null
    };
  });
}

function normEONET(d){
  return (d.events||[]).map(function(e){

    const gs=e.geometry||[];

    const g=
      gs.length
        ?gs[gs.length-1]
        :null;

    const c=
      g &&
      Array.isArray(g.coordinates)
        ?g.coordinates
        :null;

    const cats=e.categories||[];

    return {
      id:e.id||null,
      source:'NASA EONET',

      type:
        cats.length &&
        cats[0].title
          ?cats[0].title
          :'natural_event',

      title:e.title||null,

      observedAt:
        g&&g.date
          ?g.date
          :null,

      location:
        c &&
        typeof c[0]==='number'
          ?{
              lon:c[0],
              lat:c[1]
            }
          :null,

      severity:null,
      verified:true,
      url:e.link||null
    };
  });
}

function normNWS(d){
  return (d.features||[]).map(function(f,i){

    const p=f.properties||{};

    return {
      id:
        f.id ||
        p.id ||
        ('nws-'+i),

      source:'NOAA/NWS',

      type:
        p.event ||
        'weather_alert',

      title:
        p.headline ||
        p.event ||
        null,

      observedAt:
        p.onset ||
        p.sent ||
        null,

      location:null,
      area:p.areaDesc||null,
      severity:p.severity||null,
      verified:true,
      url:p['@id']||null
    };
  });
}

async function load(kind){

  if(!SRC[kind]){
    return {
      ok:false,
      kind:kind,
      status:400,
      events:[],
      error:'unknown_source'
    };
  }

  try{

    const r=
      await fetchJson(
        SRC[kind]
      );

    if(!r.ok){
      return {
        ok:false,
        kind:kind,
        status:r.status,
        events:[],
        error:r.data
      };
    }

    let events=[];

    if(kind==='usgs'){
      events=normUSGS(r.data);
    }

    if(kind==='eonet'){
      events=normEONET(r.data);
    }

    if(kind==='nws'){
      events=normNWS(r.data);
    }

    return {
      ok:true,
      kind:kind,
      status:200,
      events:events
    };

  }catch(e){

    return {
      ok:false,
      kind:kind,
      status:503,
      events:[],
      error:String(
        e&&e.message
          ?e.message
          :e
      )
    };
  }
}

async function all(){

  const batches=
    await Promise.all(
      [
        'usgs',
        'eonet',
        'nws'
      ].map(load)
    );

  const events=[];
  const unavailable=[];

  batches.forEach(function(b){

    if(b.ok){

      Array.prototype.push.apply(
        events,
        b.events
      );

    }else{

      unavailable.push({
        source:b.kind,
        status:b.status,
        error:b.error
      });
    }
  });

  return {
    events:events,
    unavailable:unavailable
  };
}

async function metrics(){

  try{

    const r=
      await fetch(
        CC+'/api/metrics',
        {
          headers:{
            accept:'application/json'
          }
        }
      );

    const text=
      await r.text();

    let data;

    try{
      data=JSON.parse(text);
    }catch(e){
      data={raw:text};
    }

    return J(
      data,
      r.status
    );

  }catch(e){

    return J(
      {
        ok:false,
        available:false,
        source:'railway-command-center',
        error:'upstream_unavailable'
      },
      503
    );
  }
}

const PAGE=
'<!doctype html>'+

'<meta name="viewport" content="width=device-width,initial-scale=1">'+

'<title>Eagle Eyes V2</title>'+

'<style>'+

'body{margin:0;background:#050a07;color:#eafff3;font:15px monospace}'+

'main{max-width:950px;margin:auto;padding:24px}'+

'h1{color:#62ffae}'+

'.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}'+

'.c{border:1px solid #246544;background:#08140e;padding:14px}'+

'.v{font-size:24px;color:#62ffae}'+

'.bad{color:#ff6b79}'+

'input,button{padding:10px;background:#0c2519;color:white;border:1px solid #2b8057}'+

'input{width:68%}'+

'pre{white-space:pre-wrap;max-height:420px;overflow:auto}'+

'</style>'+

'<main>'+

'<h1>EAGLE EYES WORLD DATA V2</h1>'+

'<p id="h">Checking...</p>'+

'<div class="grid">'+

'<div class="c">'+
'USGS'+
'<div id="usgs" class="v">—</div>'+
'</div>'+

'<div class="c">'+
'NASA EONET'+
'<div id="eonet" class="v">—</div>'+
'</div>'+

'<div class="c">'+
'NOAA/NWS'+
'<div id="nws" class="v">—</div>'+
'</div>'+

'<div class="c">'+
'COMMAND CENTER'+
'<div id="m" class="v">—</div>'+
'</div>'+

'</div>'+

'<p>'+

'<input id="q" placeholder="search verified world events">'+

'<button onclick="go()">Search</button>'+

'</p>'+

'<pre id="o"></pre>'+

'<p>'+
'Verified Internet sources. No simulated values.'+
'</p>'+

'</main>'+

'<script>'+

'async function g(u){'+
'const r=await fetch(u,{cache:"no-store"});'+
'return [r,await r.json()];'+
'}'+

'async function l(s){'+
'try{'+
'const a=await g("/api/events?source="+s);'+
'const e=document.getElementById(s);'+
'e.textContent=a[1].count||0;'+
'if(!a[0].ok)e.className="v bad";'+
'}catch(x){'+
'const e=document.getElementById(s);'+
'e.textContent="N/A";'+
'e.className="v bad";'+
'}'+
'}'+

'async function go(){'+
'const q=document.getElementById("q").value.trim();'+
'if(!q)return;'+
'const a=await g("/api/search?q="+encodeURIComponent(q));'+
'document.getElementById("o").textContent=JSON.stringify(a[1],null,2);'+
'}'+

'(async function(){'+

'try{'+
'const a=await g("/healthz");'+
'document.getElementById("h").textContent=a[0].ok?"V2 ONLINE":"V2 ERROR";'+
'}catch(e){}'+

'["usgs","eonet","nws"].forEach(l);'+

'try{'+
'const a=await g("/api/metrics");'+
'document.getElementById("m").textContent=a[0].ok?"ONLINE":"N/A";'+
'}catch(e){}'+

'})();'+

'</script>';

export default{

  async fetch(req){

    const u=
      new URL(req.url);

    if(req.method!=='GET'){

      return J(
        {
          ok:false,
          error:'method_not_allowed'
        },
        405
      );
    }

    if(u.pathname==='/'){

      return new Response(
        PAGE,
        {
          headers:{
            'content-type':
              'text/html; charset=utf-8',
            'cache-control':
              'no-store'
          }
        }
      );
    }

    if(u.pathname==='/healthz'){

      return J({
        ok:true,
        status:'healthy',
        service:
          'eagle-eyes-world-data-v2',
        runtime:
          'cloudflare-workers',
        timestamp:
          new Date().toISOString()
      });
    }

    if(u.pathname==='/api/metrics'){

      return metrics();
    }

    if(u.pathname==='/api/source-health'){

      const batches=
        await Promise.all(
          [
            'usgs',
            'eonet',
            'nws'
          ].map(load)
        );

      return J({
        ok:
          batches.every(
            function(x){
              return x.ok;
            }
          ),

        sources:
          batches.map(
            function(x){

              return {
                source:x.kind,
                ok:x.ok,
                status:x.status,
                count:x.events.length
              };
            }
          ),

        timestamp:
          new Date().toISOString()
      });
    }

    if(u.pathname==='/api/events'){

      const source=
        (
          u.searchParams.get('source')||
          'all'
        ).toLowerCase();

      if(source==='all'){

        const x=
          await all();

        return J({
          ok:
            x.unavailable.length===0,

          count:
            x.events.length,

          events:
            x.events,

          unavailableSources:
            x.unavailable,

          timestamp:
            new Date().toISOString()
        });
      }

      if(!SRC[source]){

        return J(
          {
            ok:false,
            error:'unknown_source',
            allowed:[
              'all',
              'usgs',
              'eonet',
              'nws'
            ]
          },
          400
        );
      }

      const x=
        await load(source);

      return J(
        {
          ok:x.ok,
          source:source,
          count:x.events.length,
          events:x.events,
          timestamp:
            new Date().toISOString()
        },
        x.ok
          ?200
          :503
      );
    }

    if(u.pathname==='/api/search'){

      const q=
        (
          u.searchParams.get('q')||
          ''
        )
        .trim()
        .toLowerCase();

      if(!q){

        return J(
          {
            ok:false,
            error:'missing_query'
          },
          400
        );
      }

      const x=
        await all();

      const results=
        x.events
          .filter(
            function(e){

              return JSON
                .stringify(e)
                .toLowerCase()
                .indexOf(q)!==-1;
            }
          )
          .slice(0,100);

      return J({
        ok:true,
        query:q,
        count:
          results.length,
        results:
          results,
        unavailableSources:
          x.unavailable,
        timestamp:
          new Date().toISOString()
      });
    }

    return J(
      {
        ok:false,
        error:'not_found'
      },
      404
    );
  }
};