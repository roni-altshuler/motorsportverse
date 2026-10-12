const fs=require('node:fs');const path=require('node:path');const http=require('node:http');
const repo=path.resolve(__dirname,'../../..');
const {chromium}=require(path.join(repo,'website/node_modules/playwright'));
const relative=process.argv[2];const site=relative==='website'?'hub':relative.split('/')[1];
const root=path.join(repo,relative,'out');const output=path.join(repo,'docs/qa/static-backgrounds');
const mime={'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.woff2':'font/woff2'};
const server=http.createServer((request,response)=>{
 try{let uri=decodeURIComponent(request.url.split('?')[0]);let file=path.join(root,uri==='/'?'index.html':uri.replace(/\/$/,''));
  if(!fs.existsSync(file)||fs.statSync(file).isDirectory()){
   if(fs.existsSync(file+'.html'))file+='.html';else file=path.join(file,'index.html');
  }
  if(!file.startsWith(root+path.sep))throw new Error('outside export');
  const bytes=fs.readFileSync(file);response.writeHead(200,{'content-type':mime[path.extname(file)]||'application/octet-stream'});response.end(bytes);
 }catch{response.writeHead(404);response.end('not found');}
});
(async()=>{
 await new Promise(r=>server.listen(4360,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const report={site:relative,generatedAt:new Date().toISOString(),runtime:'Next.js 16.3.8 optimized static export; process-local webpack disk cache disabled',browser:browser.version(),cases:[],interactions:[]};
 const representative=['hub','f1-predictions','f2-predictions'].includes(site);
 const routes=['/'];
 if(site==='hub')routes.push('/projects/','/docs/');
 if(site==='f1-predictions')routes.push('/calendar/','/standings/','/race/17/','/circuits/','/compare/laps/','/about/');
 if(site==='f2-predictions')routes.push('/calendar/','/about/');
 for(const route of routes){
  for(const [device,width,height] of [['desktop',1440,900],['mobile',390,844]]){
   for(const theme of ['dark','light']){
    const context=await browser.newContext({viewport:{width,height},reducedMotion:'no-preference'});
    const page=await context.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(()=>{
     localStorage.setItem('motorsportverse-ambient','vivid');
     window.__backgroundProbe={frames:0,speedFieldPaints:0};
     const raf=window.requestAnimationFrame.bind(window);
     window.requestAnimationFrame=cb=>raf(t=>{window.__backgroundProbe.frames++;cb(t)});
     const fill=CanvasRenderingContext2D.prototype.fillRect;
     CanvasRenderingContext2D.prototype.fillRect=function(...args){if(this.canvas.classList.contains('speed-field'))window.__backgroundProbe.speedFieldPaints++;return fill.apply(this,args)};
    });
    const response=await page.goto('http://127.0.0.1:4360'+route,{waitUntil:'networkidle',timeout:60000});
    await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    await page.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=700){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,30))}window.scrollTo(0,0)});
    await page.waitForTimeout(1300);
    const sample=await page.evaluate(()=>({canvas:getComputedStyle(document.body).backgroundColor,bodyBackgroundImage:getComputedStyle(document.body).backgroundImage,decorativeCanvases:document.querySelectorAll('canvas.speed-field').length,heroRibbons:document.querySelectorAll('.hero-track-ribbon').length,ambientControls:document.querySelectorAll('[aria-label*="Backdrop"]').length,probe:{...window.__backgroundProbe},infiniteAnimations:document.getAnimations().filter(a=>a.effect?.getTiming().iterations===Infinity).map(a=>({name:a.animationName||a.constructor.name,target:a.effect?.target?.tagName,className:typeof a.effect?.target?.className==='string'?a.effect.target.className:a.effect?.target?.className?.baseVal||''})),width:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,title:document.title}));
    await page.waitForTimeout(350);const paintsAfter=await page.evaluate(()=>window.__backgroundProbe.speedFieldPaints);
    const banned=sample.infiniteAnimations.filter(a=>/hero-track|neon|shimmer-slide|spin-around|pulse-ring|marquee|orbit|gradient|sheen|podium-leader/.test(a.name+' '+a.className));
    const result={route,device,theme,width,height,httpStatus:response.status(),...sample,decorativePaintsDuring350ms:paintsAfter-sample.probe.speedFieldPaints,decorativeInfiniteAnimations:banned,errors};
    if(representative&&route==='/'){
     const short=site.replace('-predictions','');const shot=`after-${short}-${device}-${theme}.png`;
     await page.screenshot({path:path.join(output,'screenshots',shot)});result.screenshot='screenshots/'+shot;
    }
    if(response.status()!==200||sample.decorativeCanvases||sample.heroRibbons||banned.length||paintsAfter||errors.length||sample.scrollWidth>sample.width+1)result.failed=true;
    report.cases.push(result);
    if(route==='/'&&theme==='dark'){
     if(site==='hub'&&device==='desktop'){
      await page.getByRole('button',{name:'Full calendar',exact:true}).click();
      await page.getByRole('searchbox',{name:'Search races'}).fill('not-a-real-circuit-qa');
      const searchEmpty=await page.getByText('No races in this view.',{exact:true}).isVisible();
      await page.getByRole('button',{name:'Explore the calendar',exact:true}).click();
      const rows=await page.locator('.race-row').count();
      await page.locator('.race-row').first().click();
      const selection=await page.locator('.race-row').first().getAttribute('aria-pressed');
      await page.getByRole('button',{name:'Open command palette'}).click();
      const palette=await page.getByRole('dialog').isVisible();await page.keyboard.press('Escape');
      report.interactions.push({name:'Race filtering/search/selection and keyboard palette',searchEmpty,rows,selection,palette,passed:searchEmpty&&rows>0&&selection==='true'&&palette});
     }else if(site!=='hub'&&device==='mobile'){
      const open=page.getByRole('button',{name:'Open menu',exact:true});
      if(await open.count()){
       await open.click();const close=page.getByRole('button',{name:'Close menu',exact:true});const drawer=await close.isVisible();await close.click();
       report.interactions.push({name:'Mobile navigation opens/closes',passed:drawer});
      }
     }
    }
    if(site==='f1-predictions'&&route==='/circuits/'&&theme==='dark'){
     await page.getByRole('button',{name:'Try fictional demo',exact:true}).click();
     await page.getByRole('button',{name:'Next snapshot',exact:true}).waitFor();
     const before=await page.getByRole('slider',{name:'Capture snapshot'}).inputValue();
     await page.getByRole('button',{name:'Next snapshot',exact:true}).click();
     const after=await page.getByRole('slider',{name:'Capture snapshot'}).inputValue();
     const driverButtons=page.locator('button[title="Alex Rivera"]');
     let selection=false;
     if(await driverButtons.count()){await driverButtons.first().click();selection=await driverButtons.first().getAttribute('aria-pressed')==='true'}
     report.interactions.push({name:`User-operated circuit workspace (${device}); existing clearly-labelled fictional demonstration`,before,after,driverSelection:selection,passed:before!==after&&selection});
    }
    console.log(site,route,device,theme,'backgroundLoops',banned.length,'paint',paintsAfter,'errors',errors.length,result.failed?'FAIL':'OK');
    await context.close();
   }
  }
 }
 fs.writeFileSync(path.join(output,`after-${site}-browser.json`),JSON.stringify(report,null,2)+'\n');
 await browser.close();await new Promise(r=>server.close(r));
 if(report.cases.some(c=>c.failed)||report.interactions.some(i=>!i.passed))process.exitCode=1;
})().catch(error=>{console.error(error);server.close();process.exit(1)});
