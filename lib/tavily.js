/**
 * Tavily deep search helper
 */
import { loadConfig } from './config.js';

export async function tavilySearch(query) {
  const config = await loadConfig();
  const apiKey = config.tavily.apiKey;

  const res = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: apiKey,
      query,
      search_depth: 'advanced',
      max_results: 5,
      include_raw_content: false,
      include_answer: true,
    }),
  });
  if (!res.ok) {
    throw new Error(`Tavily ${res.status}: ${await res.text()}`);
  }
  const data = await res.json();
  return {
    answer: data.answer || '',
    results: (data.results || []).map((r) => ({
      title: r.title,
      url: r.url,
      content: r.content,
    })),
  };
}

export async function gatherEvidence(claims) {
  console.log('\x1b[36m→ Step 2/4 — Searching for evidence (Tavily advanced)...\x1b[0m');
  const results = [];

  for (let i = 0; i < claims.length; i += 3) {
    const batch = claims.slice(i, i + 3);
    const batchResults = await Promise.all(
      batch.map(async (claim) => {
        try {
          const sr = await tavilySearch(claim.searchQuery);
          console.log(`\x1b[36m  ✓ "${claim.searchQuery.slice(0, 55)}"\x1b[0m`);
          return { ...claim, evidence: sr };
        } catch (err) {
          console.log(`\x1b[33m  ⚠ Failed: ${claim.searchQuery.slice(0, 40)}\x1b[0m`);
          return { ...claim, evidence: { answer: '', results: [] } };
        }
      })
    );
    results.push(...batchResults);
  }
  return results;
}
