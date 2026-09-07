const CC='https://live-command-center-production-31ed.up.railway.app';

const SOURCES={
  usgs:'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson',
  eonet:'https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100',
  nws:'https://api.weather.gov/alerts/active'
};

function json(data,status){
  return new Response(
    JSON.stringify(data,null,2),
    {
      status:status||200,
      headers:{
        'content-type':'application/json; charset=utf-8',
        'cache-control':'no-store'
      }
    }
  );
}

async function upstream(url){
  try{
    const headers={
      'accept':'application/json'
    };

    if(url.indexOf('api.weather.gov')!==-1){
      headers['accept']='application/geo+json';
      headers['user-agent']='Eagle-Eyes-World-Data-Edge/1.0 (https://eagle-eyes-world-data-edge.salathaniebrown.workers.dev)';
    }

    const r=await fetch(url,{
      method:'GET',
      headers:headers
    });

    const body=await r.text();

    return new Response(
      body,
      {
        status:r.status,
        headers:{
          'content-type':
            r.headers.get('content-type')||
            'application/json',
          'cache-control':'no-store'
        }
      }
    );

  }catch(e){
    return json(
      {
        ok:false,
        error:'upstream_unavailable',
        detail:String(e)
      },
      503
    );
  }
}

const PAGE=
'<!doctype html>'+
'<html>'+
'<head>'+
'<meta charset="utf-8">'+
'<meta name="viewport" content="width=device-width,initial-scale=1">'+
'<title>Eagle Eyes</title>'+
'<style>'+
'body{margin:0;background:#050a07;color:#eafff3;font:16px monospace}'+
'main{max-width:800px;margin:auto;padding:24px}'+
'h1{color:#62ffae}'+
'a{color:#62ffae;text-decoration:none}'+
'.c{border:1px solid #246544;padding:16px;margin:12px 0;background:#08140e}'+
'</style>'+
'</head>'+
'<body>'+
'<main>'+
'<h1>EAGLE EYES WORLD DATA EDGE</h1>'+
'<div class="c"><a href="/healthz">Health</a></div>'+
'<div class="c"><a href="/api/metrics">Railway metrics</a></div>'+
'<div class="c"><a href="/api/sources">Sources</a></div>'+
'<div class="c"><a href="/api/events?source=usgs">USGS earthquakes</a></div>'+
'<div class="c"><a href="/api/events?source=eonet">NASA EONET</a></div>'+
'<div class="c"><a href="/api/events?source=nws">NOAA/NWS alerts</a></div>'+
'<p>No simulated values are substituted for unavailable sources.</p>'+
'</main>'+
'</body>'+
'</html>';

export default{
  async fetch(req){
    const u=new URL(req.url);

    if(req.method!=='GET'){
      return json(
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
            'content-type':'text/html; charset=utf-8',
            'cache-control':'no-store'
          }
        }
      );
    }

    if(u.pathname==='/healthz'){
      return json({
        ok:true,
        status:'healthy',
        service:'eagle-eyes-world-data-edge',
        runtime:'cloudflare-workers',
        timestamp:new Date().toISOString()
      });
    }

    if(u.pathname==='/api/metrics'){
      return upstream(
        CC+'/api/metrics'
      );
    }

    if(u.pathname==='/api/sources'){
      return json({
        ok:true,
        sources:[
          'usgs',
          'eonet',
          'nws'
        ],
        commandCenter:CC,
        timestamp:new Date().toISOString()
      });
    }

    if(u.pathname==='/api/events'){
      const source=String(
        u.searchParams.get('source')||
        'usgs'
      ).toLowerCase();

      if(!SOURCES[source]){
        return json(
          {
            ok:false,
            error:'unknown_source',
            allowed:[
              'usgs',
              'eonet',
              'nws'
            ]
          },
          400
        );
      }

      return upstream(
        SOURCES[source]
      );
    }

    return json(
      {
        ok:false,
        error:'not_found'
      },
      404
    );
  }
};