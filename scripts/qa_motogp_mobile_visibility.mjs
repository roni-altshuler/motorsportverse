// Matched static-export browser QA; supply an exact base site's exported out directory.
// node scripts/qa_motogp_mobile_visibility.mjs <base-export-dir> [output-dir]
import { chromium } from '../projects/f1-predictions/website/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { paintState, revealRaceContent, scrollAndCheckPaint, scrollWholePage } from './qa_race_content.mjs';
const repository = fileURLToPath(new URL('../', import.meta.url));
assert.ok(process.argv[2], 'Supply the exact base MotoGP export directory.');
const baseExport = resolve(process.argv[2]);
const headExport = resolve(repository, 'projects/motogp-predictions/website/out');
const applicationHead = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repository, encoding: 'utf8' }).trim();
const baseCommit = 'b9408e3a56bd08e51220709aae5f017dabcda272';
const site = 'projects/motogp-predictions/website/';
// Verify the supplied export's adjacent source/build inputs against the pinned
// base. The repaired dependency lock used to build it is disclosed separately.
const baseFiles = execFileSync('git', ['ls-tree', '-r', '--name-only', baseCommit, '--', site], { cwd: repository, encoding: 'utf8' })
  .trim().split('\n').filter(path => /^(src\/|public\/|package\.json$|next\.config\.ts$|postcss\.config\.mjs$|tsconfig\.json$|\.npmrc$)/.test(path.slice(site.length)));
for (const path of baseFiles) {
  const expected = execFileSync('git', ['show', `${baseCommit}:${path}`], { cwd: repository });
  assert.deepEqual(await readFile(resolve(baseExport, '..', path.slice(site.length))), expected, `${path}: supplied base source differs`);
}
const baseSourceVerification = { sourceCommit: baseCommit, matchedFiles: baseFiles.length, dependencyLock: 'repaired head lock; original base lock fails npm ci' };
const output=resolve(process.argv[3] || '/tmp/motorsport-matched-motogp-qa');await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
const mime={'.html':'text/html','.txt':'text/plain','.js':'text/javascript','.css':'text/css','.json':'application/json','.woff2':'font/woff2','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.ico':'image/x-icon'};
const cases=[];
try {
 for(const reducedMotion of ['reduce','no-preference']) {
  for(const [label,root,sourceCommit] of [['base',baseExport,baseCommit],['head',headExport,applicationHead]]) {
   const server=createServer(async(req,res)=>{try {const pathname=new URL(req.url,'http://localhost').pathname;const p=resolve(root,`.${pathname.endsWith('/')?pathname+'index.html':pathname}`);if(!p.startsWith(`${root}/`))throw new Error('invalid path');const bytes=await readFile(p);res.writeHead(200,{'Content-Type':mime[extname(p)]||'application/octet-stream'});res.end(bytes);}catch{res.writeHead(404);res.end('Not found');}});
   await new Promise(done=>server.listen(0,'127.0.0.1',done));
   const origin=`http://127.0.0.1:${server.address().port}`;
   const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion});
   try {
    console.log(`${label} ${reducedMotion}: real mobile scrolling`);
    const page=await context.newPage();const pageErrors=[],resources=[];
    page.on('pageerror',e=>pageErrors.push(e.message));page.on('response',r=>{if(r.status()>=400)resources.push({url:r.url().replace(origin,''),status:r.status()});});
    await page.clock.setFixedTime(new Date('2026-10-07T12:00:00Z'));
    assert.equal((await page.goto(`${origin}/race/1/`,{waitUntil:'networkidle'})).status(),200);
    const bytes=await readFile(resolve(root,'data/rounds/round_01.json'));
    assert.deepEqual(bytes,execFileSync('git',['show',`${sourceCommit}:${site}public/data/rounds/round_01.json`],{cwd:repository}),`${label}: exported data differs from committed source`);
    const round=JSON.parse(bytes);await page.getByRole('main').getByRole('heading').filter({hasText:round.venueName}).first().waitFor();
    const probability=page.getByRole('heading',{name:'Win vs Podium',exact:true}).locator('../../..');
    const beforeScroll={probability:await paintState(probability),classification:await paintState(page.locator('main table').first())};
    const stops=await scrollWholePage(page);
    const captureStates=[];
    const sections=await revealRaceContent(page,round,async(name,locator)=>{
     const target=name.startsWith('podium-')?locator.locator('..'):locator;
     // Keep section captures below the real sticky navigation; do not hide it.
     const top=await target.evaluate(el=>Math.max(0,scrollY+el.getBoundingClientRect().top-180));
     await page.evaluate(top=>window.scrollTo({top,behavior:'instant'}),top);
     await page.waitForTimeout(150);
     const box=await target.boundingBox();
     assert.ok(box.y>=0&&box.y+box.height<=844,`${name}: capture extends beyond viewport`);
     const content=name==='probabilities'?target.getByRole('heading',{name:'Win vs Podium',exact:true}):locator;
     const state=await paintState(content);
     assert.ok(state.opacity>=.99&&!state.hiddenAncestors.length&&!state.covered,`${name}: capture content is hidden or covered`);
     captureStates.push({name,scrollY:await page.evaluate(()=>scrollY),box,state});
     await target.screenshot({path:`${output}/${label}-${reducedMotion}-${name}.png`});
    });
    await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));await page.waitForTimeout(150);
    // Capture naturally settled content; no screenshot animation fast-forward.
    await page.screenshot({path:`${output}/${label}-${reducedMotion}-full.png`,fullPage:true});
    const metrics=await page.evaluate(()=>({documentWidth:document.documentElement.scrollWidth,documentHeight:document.documentElement.scrollHeight,viewportWidth:innerWidth,viewportHeight:innerHeight}));
    const afterScroll={probability:await paintState(probability),classification:await paintState(page.locator('main table').first())};
    assert.deepEqual(pageErrors,[]);
    for(const resource of resources) {
     assert.ok(resource.status===404&&/^\/headshots\/[A-Z0-9_-]+\.webp$/.test(resource.url),`${label}: unexpected failed resource ${JSON.stringify(resource)}`);
     assert.equal(execFileSync('git',['ls-tree',baseCommit,'--',`${site}public${resource.url}`],{cwd:repository,encoding:'utf8'}),'',`${label}: missing resource exists on base`);
    }
    let negativeGuard=null;
    if(label==='head'&&reducedMotion==='reduce') {
     const originalStyle=await probability.getAttribute('style');
     await probability.evaluate(el=>el.style.opacity='0');
     try {
      assert.equal(await page.getByRole('heading',{name:'Win vs Podium',exact:true}).count(),1);
      await assert.rejects(scrollAndCheckPaint(page,probability,'QA-only hidden probability fixture',300),/content remains hidden/);
      negativeGuard={fixtureInjection:true,headingPresent:true,hiddenBodyRejected:true};
     }finally{
      await probability.evaluate((el,style)=>{if(style===null)el.removeAttribute('style');else el.setAttribute('style',style);},originalStyle);
     }
     await scrollAndCheckPaint(page,probability,'restored real probability content');
    }
    cases.push({label,sourceCommit,route:'/race/1/',reducedMotion,roundSha256:createHash('sha256').update(bytes).digest('hex'),beforeScroll,scrollStops:stops,sections,captureStates,metrics,afterScroll,negativeGuard,pageErrors,resources});
    console.log(`${label} ${reducedMotion}: ${sections.checks.length} painted-content assertions passed`);
   }finally{await context.close();await new Promise(done=>server.close(done));}
  }
 }
 for(const motion of ['reduce','no-preference']){
  const [a,b]=cases.filter(c=>c.reducedMotion===motion);
  assert.equal(a.roundSha256,b.roundSha256);assert.deepEqual(a.scrollStops,b.scrollStops);assert.deepEqual(a.metrics,b.metrics);
  assert.deepEqual(a.sections.podiumNames,b.sections.podiumNames);assert.equal(a.sections.classificationRows,b.sections.classificationRows);assert.equal(a.sections.probabilityRows,b.sections.probabilityRows);
 }
 await writeFile(`${output}/matched-browser-qa.json`,JSON.stringify({browser:browser.version(),applicationHead,baseSourceVerification,cases},null,2)+'\n');
 console.log(JSON.stringify({output,cases:cases.length,allContentPaintChecks:true}));
}finally{await browser.close();}
