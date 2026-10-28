const el = id => document.getElementById(id);
async function checkReady() {
  try {
    const response = await fetch('/ready');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail);
    el('status').textContent = `Index ${data.index_version} · ${data.embedding_model} · ${data.llm_configured ? data.llm_model : 'Search ready; add GROQ_API_KEY for answers'}`;
  } catch (error) { el('status').textContent = error.message; }
}
document.querySelectorAll('[data-q]').forEach(button => button.addEventListener('click', () => { el('question').value = button.dataset.q; }));
async function run(mode) {
  const question = el('question').value.trim();
  if (question.length < 3) { el('question').focus(); return; }
  el('ask').disabled = el('search').disabled = true;
  el('busy').textContent = mode === 'ask' ? 'Retrieving and generating…' : 'Retrieving…';
  el('result').hidden = true; el('evidence').hidden = true;
  try {
    const response = await fetch(`/api/${mode}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question})});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Invalid request. Check question length.');
    el('result-title').textContent = mode === 'search' ? 'Search results' : data.status === 'answered' ? 'Answer' : 'Insufficient evidence';
    el('answer').textContent = data.answer || 'Review the retrieved passages below. No LLM call was made.';
    el('answer').className = '';
    el('metrics').textContent = mode === 'search' ? `Retrieval ${data.retrieval_ms} ms · Index ${data.index_version}` : `Retrieval ${data.timings.retrieval_ms} ms · Total ${data.timings.total_ms} ms · Tokens ${data.usage.total_tokens ?? 'unavailable'} · Request ${data.request_id}`;
    el('sources').replaceChildren();
    for (const source of data.sources) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      const cited = (data.citations || []).includes(source.id);
      summary.textContent = `${cited ? 'CITED · ' : ''}PDF page ${source.page} · ${source.id} · similarity ${source.score}`;
      const text = document.createElement('p'); text.textContent = source.text;
      const link = document.createElement('a'); link.href = source.url; link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Open this page in the official PDF ↗';
      details.append(summary, text, link); details.open = cited; el('sources').append(details);
    }
    el('evidence').hidden = false;
  } catch (error) {
    el('result-title').textContent = 'Could not complete the request';
    el('answer').textContent = error.message; el('answer').className = 'error'; el('metrics').textContent = '';
  } finally {
    el('result').hidden = false; el('ask').disabled = el('search').disabled = false; el('busy').textContent = '';
  }
}
el('ask').addEventListener('click', () => run('ask'));
el('search').addEventListener('click', () => run('search'));
checkReady();
