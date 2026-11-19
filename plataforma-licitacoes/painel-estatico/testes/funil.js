// Funil até você: etapas, top 10, botão "Ver na lista", troca de núcleo; imprime as melhores do mês (JSON) para o relatório
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch(); const erros = [];
  for (const w of [1366, 390]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on('pageerror', (e) => erros.push(String(e))); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await p.addInitScript(() => { try { localStorage.setItem('paineis-fechados', '[]'); } catch (e) {} }); await p.goto('file://' + process.argv[2]); await p.waitForSelector('#funil-etapas li');
    await p.waitForFunction(() => /Todas as licitações do Brasil \d/.test(document.getElementById('cats').innerText), null, { timeout: 60000 }).catch(() => {});
    const etapas = await p.$$eval('#funil-etapas li', (xs) => xs.map((x) => x.innerText.replace(/\s+/g, ' ')));
    if (w === 1366) console.log(etapas.join('\n'));
    const top = await p.$$eval('#funil-top li', (xs) => xs.length);
    await p.click('#funil-ver'); await p.waitForTimeout(300);
    console.log(w, 'top', top, '| lista:', (await p.textContent('#conta')).replace(/\s+/g, ' ').slice(0, 90));
    const b1 = await p.$('#funil-top [data-funil]'); if (b1) { await b1.click(); await p.waitForTimeout(300);
      console.log(' prévia aberta:', await p.$eval('#previa', (e) => !e.hidden && e.innerText.length > 50)); }
    await p.keyboard.press('Escape'); await p.click('#funil-nucleo [data-g="telecom"]'); await p.waitForTimeout(200);
    console.log(' com telecom:', (await p.$$eval('#funil-etapas li', (xs) => xs.slice(-1)[0].innerText.replace(/\s+/g, ' '))));
    await p.click('#funil-nucleo [data-g="telecom"]');
    await p.check('#funil-prox'); await p.waitForTimeout(200);
    console.log(' com mês que vem:', (await p.$$eval('#funil-etapas li', (xs) => xs.slice(-1)[0].innerText.replace(/\s+/g, ' '))));
    await p.uncheck('#funil-prox');
    console.log(' largura', await p.evaluate(() => document.documentElement.scrollWidth));
    if (w === 1366 && process.argv[3]) {
      const dados = await p.evaluate(() => {
        const out = {};
        for (const prox of [false, true]) {
          document.getElementById('funil-prox').checked = prox;
          const { final } = etapasFunil();
          out[prox ? 'ate_dez' : 'nov'] = final.slice(0, 40).map((x) => { const s = notaOportunidade(x);
            return { id: x.id, nota: s.nota, mot: s.motivos, o: x.o, un: x.un, uf: x.uf, m: x.m, v: x.v, enc: x.enc, mod: x.mod, n: x.n, obj: x.obj,
              cp: CATS[principal(x)], g: grupoDe(x), pncp: x.pncp, orig: x.orig, plat: x.plat, vol: x.vol, c: x.c }; });
        }
        document.getElementById('funil-prox').checked = false;
        return out;
      });
      fs.writeFileSync(process.argv[3], JSON.stringify(dados, null, 1));
    }
    if (w === 390) await (await p.$('#funil-sec')).screenshot({ path: 'funil-390.png' });
    await p.close();
  }
  console.log('erros', JSON.stringify(erros)); await b.close();
})();
