// Regression checks for stale status replies and failed preview submissions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: '', hidden: true, textContent: '', src: null,
    pause() {}, load() {}, removeAttribute(key) { this[key] = null; },
    getAttribute(key) { return this[key]; }, replaceChildren(...options) { if(options.length)this.value=options[0].value; }, append() {},
  });
  return elements.get(id);
}
const context = vm.createContext({
  document: { getElementById: element, addEventListener() {}, createElement: () => ({style:{}, append() {}, setAttribute() {}}) },
  Option: function(text,value) { this.value=value; },
  localStorage: {getItem() {return this.value||null}, setItem(key,value) {this.value=value}},
  URLSearchParams, console, setInterval() {},
});
let source = fs.readFileSync('templates/index.html', 'utf8').split('<script>')[1].split('</script>')[0];
source = source.replace('{{ token|tojson }}', '"test-token"').replace('init();setInterval(poll,2000);', '');
vm.runInContext(source, context);
vm.runInContext(`
  refreshHistory=async()=>{};
  books=[{name:'book',files:[{name:'001.txt'}],oversize:0,characters:7}];
  $('book').value='book';$('voice').value='tr-TR-Wavenet-A';$('family').value='Wavenet';
  $('language').value='tr-TR';$('preview-file').value='001.txt';
  for(const [k,v] of Object.entries(defaults))$(k).value=v;
`, context);
const status = {running:false, total:1, done:1, usage:{}, preview_url:'/old.wav', message:'OLD', job_id:'old'};
async function run() {
  // A poll already in flight must not resurrect a preview after a settings edit.
  let resolve;
  context.reply = () => new Promise(r => { resolve = r; });
  vm.runInContext('api=reply', context);
  const pending = vm.runInContext('poll()', context);
  vm.runInContext("$('speaking_rate').value='0.5';$('speaking_rate').oninput()", context);
  resolve(status);
  await pending;
  assert.equal(element('player').hidden, true);
  assert.notEqual(element('message').textContent, 'OLD');

  // A rejected synthesis must retain the real error, even after another poll.
  context.reply = async () => { throw Error('4.999 bayt aşıldı'); };
  vm.runInContext('api=reply', context);
  await vm.runInContext('begin(true)', context);
  context.reply = async () => status;
  vm.runInContext('api=reply', context);
  await vm.runInContext('poll()', context);
  assert.equal(element('message').textContent, '4.999 bayt aşıldı');
  assert.equal(element('error-panel').hidden, false);
  assert.equal(element('error-text').textContent, '4.999 bayt aşıldı');
  assert.equal(element('player').hidden, true);

  // Accepted previews send changed settings and only display their own job.
  let sent;
  context.reply = async (url, payload) => {
    if (url === '/api/start') { sent = payload; return {job_id:'new'}; }
    return status;
  };
  vm.runInContext('api=reply', context);
  await vm.runInContext('begin(true)', context);
  await vm.runInContext('poll()', context);
  assert.equal(sent.settings.speaking_rate, 0.5);
  assert.equal(element('player').hidden, true);
  context.reply = async () => ({...status, job_id:'new', preview_url:'/new.wav'});
  vm.runInContext('api=reply', context);
  await vm.runInContext('poll()', context);
  assert.equal(element('player').src, '/new.wav');
  assert.equal(element('player').hidden, false);

  // A failed conversion surfaces the server's reason, not a generic message.
  const reason = '014.wav dosyasında durdu.\nGoogle kotası doldu.\n\nAyrıntı: 429 Quota exceeded';
  context.reply = async () => ({...status, job_id:'new', error:reason});
  vm.runInContext('api=reply', context);
  await vm.runInContext('poll()', context);
  assert.equal(element('error-panel').hidden, false);
  assert.equal(element('error-text').textContent, reason);
  assert.equal(element('message').textContent, reason);

  // Reloading preserves both the selection and an actionable error.
  vm.runInContext("draftReady=true;showError('Duraklama sınırı aşıldı');saveDraft();$('book').value='';$('speaking_rate').value=1;restoreDraft()", context);
  assert.equal(element('book').value, 'book');
  assert.equal(Number(element('speaking_rate').value), 0.5);
  assert.equal(element('voice').value, 'tr-TR-Wavenet-A');
  assert.equal(element('preview-file').value, '001.txt');
  assert.equal(element('error-text').textContent, 'Duraklama sınırı aşıldı');
  console.log('UI regression checks passed.');
}
run().catch(error => { console.error(error); process.exitCode=1; });
