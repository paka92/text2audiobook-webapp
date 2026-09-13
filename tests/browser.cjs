// Run with PLAYWRIGHT_MODULE pointing to playwright-core; all HTTP is mocked.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const {execFileSync} = require('node:child_process');
const assert = require('node:assert/strict');
async function main() {
  const html = execFileSync('.venv/bin/python', ['-c', 'import app; print(app.app.test_client().get("/").get_data(as_text=True))'], {encoding:'utf8'});
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const page = await browser.newPage();
    const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    let submitted, status={running:false,total:0,done:0,message:'Bir kitap seçin.',usage:{Wavenet:{monthly:0,gross:0,limit:4000000},Neural2:{monthly:0,gross:0,limit:1000000}}};
    let requests=0;
    await page.route('**/*', async route=>{
      const url=new URL(route.request().url());
      const send=(data,code=200)=>route.fulfill({status:code,contentType:'application/json',body:JSON.stringify(data)});
      if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
      if(url.pathname==='/api/books')return send({books:[{name:'book',characters:7,oversize:0,files:[{name:'001.txt',bytes:7,characters:7,error:''}]}],usage:status.usage});
      if(url.pathname==='/api/voices')return send({voices:['tr-TR-Wavenet-A']});
      if(url.pathname==='/api/previews')return send({previews:[]});
      if(url.pathname==='/api/status')return send(status);
      if(url.pathname==='/api/session')return send({token:'fresh-token'});
      if(url.pathname==='/api/start'){
        requests++;submitted=route.request().postDataJSON();
        assert.equal(route.request().headers()['x-local-token'],'fresh-token');
        return send({error:'014.txt: Dosya 5210 bayt; en fazla 4.999 bayt olabilir. Kitap hiç gönderilmedi; metni düzeltin.'},400);
      }
      return route.abort();
    });
    await page.goto('http://127.0.0.1:5002/');
    await page.selectOption('#book','book');
    await page.click('#load');
    await page.selectOption('#voice','tr-TR-Wavenet-A');
    await page.selectOption('#preview-file','001.txt');
    await page.locator('#speaking_rate').fill('0.5');
    await page.click('#preview');
    await page.waitForFunction(()=>!document.getElementById('error-panel').hidden);
    assert.equal(requests,1);
    assert.equal(submitted.settings.speaking_rate,0.5);
    assert.equal(submitted.settings.paragraph_pause,undefined);
    assert.match(await page.textContent('#error-text'),/014.txt/);
    assert.equal(await page.inputValue('#book'),'book');
    assert.equal(await page.inputValue('#preview-file'),'001.txt');
    await page.reload();
    await page.waitForFunction(()=>document.getElementById('book').value==='book');
    assert.equal(await page.inputValue('#voice'),'tr-TR-Wavenet-A');
    assert.equal(await page.inputValue('#preview-file'),'001.txt');
    assert.equal(await page.inputValue('#speaking_rate'),'0.5');
    assert.match(await page.textContent('#error-text'),/014.txt/);
    assert.equal(await page.locator('#error-panel').isVisible(),true);
    assert.equal(await page.locator('#preview').isEnabled(),true);
    assert.equal(requests,1,'Reload must never retry synthesis');
    assert.deepEqual(errors,[]);
    console.log('Chrome: failure visible, selections survive reload, fresh session used, no automatic synthesis retry.');
  } finally {await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
