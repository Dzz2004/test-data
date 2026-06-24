/**
 * LLM-powered steps using OpenAI-compatible API
 */
import OpenAI from 'openai';
import { loadConfig } from './config.js';

const MAX_QUERIES = 8;

let _client = null;
let _model = null;

async function getClient() {
  if (_client) return { client: _client, model: _model };
  const config = await loadConfig();
  _client = new OpenAI({
    baseURL: config.llm.baseUrl,
    apiKey: config.llm.apiKey,
  });
  _model = config.llm.model;
  return { client: _client, model: _model };
}

function extractJson(text) {
  const fenced = text.match(/```(?:json)?\s*\n([\s\S]*?)\n```/);
  if (fenced) return fenced[1].trim();
  const match = text.match(/[\[{][\s\S]*[\]}]/);
  return match ? match[0] : text;
}

async function chat(messages, maxTokens = 2048) {
  const { client, model } = await getClient();
  const resp = await client.chat.completions.create({
    model,
    messages,
    max_tokens: maxTokens,
    temperature: 0.3,
  });
  return resp.choices[0].message.content;
}

export async function extractClaims(persona) {
  console.log('\x1b[36m→ Step 1/4 — Extracting factual claims...\x1b[0m');
  const text = await chat([{
    role: 'user',
    content: `You are a persona data validator. Analyze this persona and extract factual claims verifiable via web search.

Focus on: salary expectations vs market, tech stack realism, career timeline validity, market demand for target role, industry trends.
Skip: subjective preferences, personal constraints, personality.

Return JSON array (max ${MAX_QUERIES}):
[{"field":"<profile field>","claim":"<assertion>","searchQuery":"<query in claim's language>","verificationType":"salary_check|tech_validity|career_path|market_demand|timeline_check"}]

Persona:
${JSON.stringify(persona, null, 2)}`,
  }]);
  const claims = JSON.parse(extractJson(text));
  console.log(`\x1b[36m  Found ${claims.length} claims\x1b[0m`);
  return claims;
}

export async function detectConflicts(persona, evidenceItems) {
  console.log('\x1b[36m→ Step 3/4 — Detecting conflicts...\x1b[0m');
  const summary = evidenceItems.map((item) => ({
    field: item.field,
    claim: item.claim,
    type: item.verificationType,
    answer: item.evidence.answer,
    sources: item.evidence.results
      .map((r) => `${r.title}: ${r.content}`)
      .join('\n')
      .slice(0, 1000),
  }));

  const text = await chat([{
    role: 'user',
    content: `Compare persona claims against evidence. Only flag genuine contradictions — if evidence is ambiguous or claim is in reasonable range, do NOT flag it.

Persona:
${JSON.stringify(persona, null, 2)}

Evidence:
${JSON.stringify(summary, null, 2)}

Return JSON:
{
  "conflicts": [
    {"field":"...","claim":"...","evidence":"<what search found>","severity":"critical|moderate|minor","suggestedFix":"<concrete correction>"}
  ],
  "validatedClaims": ["<claims confirmed accurate>"],
  "overallRealism": "high|medium|low",
  "notes": "<1-2 sentence assessment>"
}`,
  }], 3000);

  const result = JSON.parse(extractJson(text));
  const cc = result.conflicts?.length || 0;
  console.log(`\x1b[36m  ${cc} conflicts, realism: ${result.overallRealism}\x1b[0m`);
  return result;
}

export async function rewritePersona(profile, conflicts) {
  console.log('\x1b[36m→ Step 4/4 — Rewriting with corrections...\x1b[0m');
  const corrections = conflicts
    .map((c, i) => `${i + 1}. [${c.field}] "${c.claim}" → ${c.suggestedFix} (evidence: ${c.evidence})`)
    .join('\n');

  const text = await chat([{
    role: 'user',
    content: `Rewrite this profile applying ONLY these corrections. Keep all other fields unchanged. Maintain narrative tone and coherence. Return the full corrected "profile" object as JSON.

Original:
${JSON.stringify(profile, null, 2)}

Corrections:
${corrections}`,
  }], 4096);

  return JSON.parse(extractJson(text));
}
