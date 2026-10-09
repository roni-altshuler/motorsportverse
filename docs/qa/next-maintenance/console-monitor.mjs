// Additional read-only browser observability for the repository's existing QA.
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
const qaRoot = process.env.NEXT_MAINTENANCE_QA_ROOT || process.cwd();
const { chromium } = createRequire(resolve(qaRoot, 'projects/f1-predictions/website/package.json'))('playwright');
if (!process.env.NEXT_MAINTENANCE_CONSOLE_LOG) throw new Error('Set NEXT_MAINTENANCE_CONSOLE_LOG to an evidence JSON path.');
import { writeFileSync } from 'node:fs';
const events=[];
const launch=chromium.launch.bind(chromium);
chromium.launch=async (...args)=>{
 const browser=await launch(...args);
 const create=browser.newContext.bind(browser);
 browser.newContext=async (...contextArgs)=>{
  const context=await create(...contextArgs);
  context.on('page',page=>{
   page.on('console',message=>{if(['error','warning'].includes(message.type()))events.push({kind:'console',type:message.type(),page:page.url(),text:message.text(),location:message.location()});});
   page.on('pageerror',error=>events.push({kind:'pageerror',page:page.url(),message:error.message,stack:error.stack}));
   page.on('requestfailed',request=>events.push({kind:'requestfailed',page:page.url(),url:request.url(),failure:request.failure()}));
  });return context;
 };return browser;
};
process.on('exit',code=>writeFileSync(process.env.NEXT_MAINTENANCE_CONSOLE_LOG,JSON.stringify({exit:code,events},null,2)+'\n'));
