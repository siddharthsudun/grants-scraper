"""
Uses Claude Sonnet to extract structured grant data from raw scraped content.
"""
import json
import re
from typing import List, Dict, Any
from openai import OpenAI
from tqdm import tqdm

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "llama3.1:8b"

COMPANY_PROFILE = """
STARTUP: Ultimate Chicken Private Limited
PRODUCT: Sous vide ready-to-eat (RTE) chicken breast — zero preservatives, 27g protein, shelf-stable
STAGE: Pre-revenue, Phase 0 campus pilot at BITS Pilani
FOUNDERS: 2nd year students at BITS Pilani, Pilani (Rajasthan)
REGISTERED: Hyderabad, Telangana
MANUFACTURING: Pilani, Rajasthan
FSSAI: Application submitted, pending certification
DPIIT RECOGNITION: Not yet obtained
UDYAM REGISTRATION: Not yet obtained
SECTOR: Food & Beverage, FMCG, Food Tech, Protein, RTE Chicken
BUDGET: ₹10 Lakh needed for Phase 0+1
""".strip()

EXTRACTION_PROMPT = """You are a grants intelligence analyst for an Indian food startup.

{company_profile}

SOURCE: {source_name} | URL: {url}
TITLE: {title}

--- CONTENT ---
{content}
--- END ---

Extract ALL grants, schemes, incubation programs, competitions, subsidies, loans, or funding opportunities from this content.

Return a JSON array. Each item must have EXACTLY these fields:
{{
  "name": "official scheme/program name",
  "provider": "organization offering it",
  "type": "grant|loan|equity|incubation|competition|subsidy|cloud_credits|scheme|prerequisite",
  "amount": "amount in INR/USD or range or 'Not specified'",
  "eligibility": "who qualifies, stage, sector, geography",
  "deadline": "deadline or 'Rolling' or 'Check website'",
  "apply_url": "application URL",
  "apply_email": "contact email or empty string",
  "apply_method": "step-by-step how to apply",
  "insider_tips": "2-3 SPECIFIC tips for Ultimate Chicken — reference their FSSAI pending, no DPIIT yet, student founders, Rajasthan manufacturing, Telangana HQ, common rejection reasons, what selectors actually look for",
  "prerequisites": "what to do BEFORE applying e.g. DPIIT recognition, Udyam registration",
  "relevance_score": <integer 1-10>,
  "relevance_reason": "why this score specifically for Ultimate Chicken",
  "tags": ["tag1", "tag2"],
  "source_url": "{url}"
}}

SCORING: 10=food+early-stage+student+Telangana/Rajasthan, 7-8=food startup or student startup, 5-6=general startup scheme, 3-4=tangential, 1-2=poor fit.

If no grants found, return [].
Return ONLY the JSON array, no other text."""


def _extract_json(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return []


def _enrich_item(client: OpenAI, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = raw.get("content", "")[:8000]
    if not content.strip():
        return []

    prompt = EXTRACTION_PROMPT.format(
        company_profile=COMPANY_PROFILE,
        source_name=raw.get("source_name", "Unknown"),
        url=raw.get("url", ""),
        title=raw.get("title", ""),
        content=content,
    )

    try:
        resp = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4096,
        )
        grants = _extract_json(resp.choices[0].message.content or "")
        for g in grants:
            if not g.get("source_url"):
                g["source_url"] = raw.get("url", "")
            g["source_platform"] = raw.get("platform", "unknown")
            g["source_category"] = raw.get("category", "unknown")
        return grants
    except Exception as e:
        print(f"    ✗ {raw.get('url', '?')}: {e}")
        return []


def enrich_grants(raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    all_grants = []
    for item in tqdm(raw_items, desc="    Enriching (llama3.1:8b)", ncols=80):
        grants = _enrich_item(client, item)
        all_grants.extend(grants)
    return all_grants
