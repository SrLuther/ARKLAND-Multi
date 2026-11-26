// Prévia fixture local; nunca executar contra o portal de produção.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.CHAT_PLAYWRIGHT_MODULE||'playwright');

test('painel: abas, validação, prévia segura, descoberta, publicação e rollback',async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  try{
    const initial=(await (await page.request.get('http://127.0.0.1:5188/api/admin/chat-arkland')).json()).revision;
    const defaults=JSON.parse(fs.readFileSync(path.join(__dirname,'../../ChatArkland/configs/config.json'),'utf8')).Shared.config;
    const reset=await page.request.put('http://127.0.0.1:5188/api/admin/chat-arkland/config',{data:{config:defaults,expected_revision:initial}});
    assert.equal(reset.status(),200);const baseRevision=initial+1;
    await page.goto('http://127.0.0.1:5188/');
    await page.locator('#ca-preview-button').waitFor();
    assert.match(await page.locator('.preview-label').innerText(),/dados fictícios/);
    await page.locator('[data-field="PollRate"]').fill('0');
    await page.locator('#ca-preview-button').click();
    await page.waitForFunction(()=>document.querySelector('#ca-feedback').classList.contains('ca-error'));
    assert.match(await page.locator('#ca-feedback').innerText(),/PollRate/);
    await page.locator('[data-field="PollRate"]').fill('0.25');
    await page.locator('#ca-preview-button').click();
    await page.locator('#ca-preview:visible').waitFor();
    assert.match(await page.locator('#ca-preview').innerText(),/\(125\)/);
    assert.ok(await page.locator('#ca-preview span[style]').count()>3);
    for(const tab of ['funcionalidades','cores','mapas','filtro','discord','mensagens','sincronizacao','tags']){
      await page.locator(`[data-tab="${tab}"]`).click();
      assert.ok((await page.locator('#ca-tab-content').innerText()).trim().length>30);
    }
    await page.locator('#ca-discover').click();
    await page.locator('[data-candidate]').first().waitFor();
    assert.equal(await page.locator('[data-candidate]').count(),3);
    await page.locator('[data-candidate]').first().click();
    await page.locator('[data-candidate]').first().click();
    assert.equal(await page.locator('[data-field$=".Approved"]').count(),2);
    assert.equal(await page.locator('[data-field$=".Approved"]:checked').count(),0);
    await page.locator('[data-field="Tags.0.Label"]').fill('<img src=x onerror=alert(1)>');
    await page.locator('#ca-preview-button').click();
    await page.locator('#ca-preview:visible').waitFor();
    assert.equal(await page.locator('#ca-preview img').count(),0);
    await page.locator('[data-tab="mapas"]').click();
    assert.equal(await page.locator('[data-map-field="Enabled"]').count(),2);
    await page.locator('[data-map-field="Enabled"]').first().check();
    await page.locator('#ca-publish').click();
    await page.waitForFunction(()=>document.querySelector('#ca-feedback')?.textContent.includes('Configuração publicada'));
    await page.locator('[data-tab="sincronizacao"]').click();
    assert.ok((await page.locator('#ca-tab-content').innerText()).includes('Revisão publicada: '+(baseRevision+1)));
    await page.locator(`[data-rollback="${baseRevision}"]`).click();
    await page.waitForFunction(()=>document.querySelector('#ca-feedback')?.textContent.includes('Revisão restaurada'));
    assert.ok((await page.locator('#ca-tab-content').innerText()).includes('Revisão publicada: '+(baseRevision+2)));
    await page.screenshot({path:'D:/DOC/arkland-chat-admin-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.locator('[data-tab="geral"]').click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
    await page.screenshot({path:'D:/DOC/arkland-chat-admin-mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});
