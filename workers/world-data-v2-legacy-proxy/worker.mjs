const V1='https://eagle-eyes-world-data-edge.salathaniebrown.workers.dev';

function J(data,status=200){
  return new Response(JSON.stringify(data,null,2),{
    status,
    headers:{
      'content-type':'application/json; charset=utf-8',
      'cache-control':'no-store'
    }
  });
}

async function get(path){
  try{
    const r=await fetch(V1+path,{
      headers:{accept:'application/json'}
    });

    const text=await r.text();

    let data;

    try{
      data=JSON.parse(text);
    }catch{
      data={raw:text};
    }

    return {
      ok:r.ok,
      status:r.status,
      data
    };

  }catch(e){
    return {
      ok:false,
      status:503,
      data:{
        error:String(
          e&&e.message
            ?e.message
            :e
        )
      }
    };
  }
}

function usgs(d){
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

function eonet(d){
  return (d.events||[]).map(function(e){

    const list=e.geometry||[];

    const g=
      list.length
        ?list[list.length-1]
        :null;

    const c=
      g &&
      Array.isArray(g.coordinates)
        ?g.coordinates
        :null;

    return {
      id:e.id||null,

      source:'NASA EONET',

      type:
        e.categories &&
        e.categories[0]
          ?e.categories[0].title
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

function nws(d){
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

      severity:
        p.severity ||
        null,

      area:
        p.areaDesc ||
        null,

      verified:true,

      url:
        p['@id'] ||
        null
    };
  });
}

async function load(kind){

  const r=
    await get(
      '/api/events?source='+
      encodeURIComponent(kind)
    );

  if(!r.ok){
    return {
      ok:false,
      kind,
      status:r.status,
      events:[],
      error:r.data
    };
  }

  let events=[];

  if(kind==='usgs'){
    events=usgs(r.data);
  }

  if(kind==='eonet'){
    events=eonet(r.data);
  }

  if(kind==='nws'){
    events=nws(r.data);
  }

  return {
    ok:true,
    kind,
    status:r.status,
    events
  };
}

async function all(){

  const batches=
    await Promise.all(
      ['usgs','eonet','nws']
        .map(load)
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
    events,
    unavailable
  };
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
'input,button{padding:10px;background:#0c2519;color:white;border:1px solid #2b8057}'+
'input{width:68%}'+
'pre{white-space:pre-wrap;max-height:420px;overflow:auto}'+
'.bad{color:#ff6b79}'+
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
'Normalized from the verified Eagle Eyes edge. '+
'No simulated values.'+
'</p>'+

'</main>'+

'<script>'+

'async function g(u){'+
'const r=await fetch(u,{cache:"no-store"});'+
'return [r,await r.json()];'+
'}'+

'async function load(s){'+
'try{'+
'const a=await g("/api/events?source="+s);'+
'document.getElementById(s).textContent=a[1].count||0;'+
'if(!a[0].ok){document.getElementById(s).className="v bad";}'+
'}catch(e){'+
'document.getElementById(s).textContent="N/A";'+
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

'["usgs","eonet","nws"].forEach(load);'+

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
        upstream:V1,
        timestamp:
          new Date().toISOString()
      });
    }

    if(u.pathname==='/api/metrics'){

      const r=
        await get('/api/metrics');

      return J(
        r.data,
        r.status
      );
    }

    if(u.pathname==='/api/source-health'){

      const names=[
        'usgs',
        'eonet',
        'nws'
      ];

      const checks=
        await Promise.all(
          names.map(
            async function(s){

              const x=
                await load(s);

              return {
                source:s,
                ok:x.ok,
                status:x.status,
                count:x.events.length
              };
            }
          )
        );

      return J({
        ok:
          checks.every(
            function(x){
              return x.ok;
            }
          ),

        sources:checks,

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

      if(
        ![
          'usgs',
          'eonet',
          'nws'
        ].includes(source)
      ){

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
          source,
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