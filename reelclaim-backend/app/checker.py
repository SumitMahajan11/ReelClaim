import os
import re
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Any, Dict, Union
from difflib import SequenceMatcher
import google.generativeai as genai
from dotenv import load_dotenv

from app.models import (
    Claim,
    SiteFact,
    ClaimVerdict,
    ScoreBreakdown,
    CheckResponse,
    VerdictType,
    ConfidenceTier,
    ClaimCategory,
    is_transient_error
)
from app.sources.base import Fact

from app.security import check_for_prompt_injection

load_dotenv()


SYSTEM_PROMPT_FILE = Path(__file__).parent / "prompts" / "claim_verification_system.txt"
USER_PROMPT_FILE = Path(__file__).parent / "prompts" / "claim_verification_user.txt"

CATEGORY_ALIASES = {
    "price": ["price", "discount", "refund", "terms", "other"],
    "discount": ["discount", "price", "terms", "other"],
    "refund": ["refund", "terms", "price", "other"],
    "certificate": ["certificate", "terms", "faq", "other"],
    "eligibility": ["eligibility", "terms", "faq", "other"],
    "deadline": ["deadline", "terms", "faq", "other"],
    "partnership": ["partnership", "faq", "other"],
    "salary": ["salary", "faq", "other"],
    "other": ["other"]
}

def load_verification_system_prompt() -> str:
    """Reads the system prompt file at runtime."""
    if not SYSTEM_PROMPT_FILE.exists():
        legacy_file = Path(__file__).parent / "prompts" / "claim_verification.txt"
        if legacy_file.exists():
            with open(legacy_file, "r", encoding="utf-8") as f:
                return f.read()
        raise FileNotFoundError(f"Verification system prompt not found at {SYSTEM_PROMPT_FILE}")
    with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def load_verification_user_prompt() -> str:
    """Reads the user prompt template file at runtime."""
    if not USER_PROMPT_FILE.exists():
        raise FileNotFoundError(f"Verification user prompt template not found at {USER_PROMPT_FILE}")
    with open(USER_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def clean_json_response(raw_text: str) -> str:
    """Strips markdown code blocks from JSON string."""
    text = raw_text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text

def normalize_text_for_comparison(text: str) -> str:
    """Normalizes text by removing non-alphanumeric chars and lowercasing."""
    return re.sub(r"[^\w\s]", "", text).lower().strip()

CRITICAL_QUALIFIERS = [
    "no questions asked",
    "unconditional",
    "free forever",
    "instant refund",
    "guaranteed job",
    "no degree required",
    "no fees ever",
    "without condition"
]

def is_valid_evidence_text(evidence_text: Optional[str], available_facts: List[Any]) -> bool:
    """
    Calibrated Anti-Hallucination & Embellishment Guardrail:
    Accepts exact substring, normalized substring, or slight paraphrases.
    REJECTS complete fabrications and embellished quotes with unsupported key clauses.
    """
    if not evidence_text or not evidence_text.strip():
        return False

    norm_evidence = normalize_text_for_comparison(evidence_text)
    tokens_ev = set(norm_evidence.split())
    if len(tokens_ev) == 0:
        return False

    # Embellishment check: reject if evidence contains a critical qualifier missing from ALL facts
    evidence_lower = evidence_text.lower()
    for qualifier in CRITICAL_QUALIFIERS:
        if qualifier in evidence_lower:
            if not any(qualifier in getattr(fact, "text", getattr(fact, "content", "")).lower() for fact in available_facts):
                # Critical embellishment detected and missing from source facts!
                return False

    for fact in available_facts:
        fact_text = getattr(fact, "text", getattr(fact, "content", ""))
        raw_fact_lower = fact_text.lower()
        norm_fact = normalize_text_for_comparison(fact_text)
        tokens_fact = set(norm_fact.split())

        # 1. Exact raw or normalized substring
        if evidence_text.strip().lower() in raw_fact_lower or norm_evidence in norm_fact or norm_fact in norm_evidence:
            return True

        # 2. High sequence similarity (ratio > 0.65)
        if SequenceMatcher(None, norm_evidence, norm_fact).ratio() > 0.65:
            return True

        # 3. High token overlap check (>= 75% of evidence words exist in fact)
        if len(tokens_ev) >= 2:
            overlap = len(tokens_ev.intersection(tokens_fact)) / len(tokens_ev)
            if overlap >= 0.70:
                return True

    return False

def get_candidate_facts_for_claim(claim: Claim, all_facts: List[Any]) -> List[Any]:
    """
    Pass 1 (Prioritized Category Filter):
    Gather facts prioritized by category relevance:
    1. Exact category matches
    2. Category alias matches
    3. Cross-reference & WHOIS independent facts (always relevant)
    4. Remaining site facts
    """
    if not all_facts:
        return []

    exact_matches = [f for f in all_facts if getattr(f, "category", "other") == claim.category]
    aliases = CATEGORY_ALIASES.get(claim.category, ["other"])

    seen_ids = {id(f) for f in exact_matches}
    alias_matches = []
    for f in all_facts:
        f_cat = getattr(f, "category", "other")
        if f_cat in aliases and id(f) not in seen_ids:
            alias_matches.append(f)
            seen_ids.add(id(f))

    # Cross-reference and Wayback facts should be considered for general claims
    independent_facts = []
    for f in all_facts:
        source_name = getattr(f, "source_name", "site_crawl")
        if source_name in ["cross_reference", "wayback", "whois"] and id(f) not in seen_ids:
            independent_facts.append(f)
            seen_ids.add(id(f))

    remaining_facts = [f for f in all_facts if id(f) not in seen_ids]

    return exact_matches + alias_matches + independent_facts + remaining_facts

def _evaluate_claim_text(claim_text_to_eval: str, claim: Claim, relevant_facts: List[Any], api_key: Optional[str]) -> Tuple[VerdictType, Optional[str], Optional[str], str]:
    effective_api_key = (api_key.strip() if api_key and api_key.strip() else None) or os.getenv("GEMINI_API_KEY")
    if not effective_api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=effective_api_key)

    system_instruction = load_verification_system_prompt()
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
        generation_config={"response_mime_type": "application/json"}
    )

    facts_formatted = json.dumps([
        {
            "text": getattr(f, "text", getattr(f, "content", "")),
            "source_page": getattr(f, "source_page", getattr(f, "source_name", "site")),
            "source_url": getattr(f, "source_url", getattr(f, "raw_reference", "")),
            "source_name": getattr(f, "source_name", "site_crawl"),
            "category": getattr(f, "category", "other"),
            "is_self_attested": getattr(f, "is_self_attested", True)
        }
        for f in relevant_facts
    ], indent=2)

    current_date_str = datetime.now().strftime("%B %d, %Y")
    user_template = load_verification_user_prompt()
    user_prompt = user_template.replace("{claim_text}", claim_text_to_eval)\
                               .replace("{category}", claim.category)\
                               .replace("{current_date}", current_date_str)\
                               .replace("{filtered_facts}", facts_formatted)

    max_attempts = 3
    raw_data = None
    for attempt in range(max_attempts):
        try:
            response = model.generate_content(user_prompt)

            raw_text = response.text or "{}"
            clean_json = clean_json_response(raw_text)
            raw_data = json.loads(clean_json)
            break
        except Exception as e:
            if is_transient_error(e) and attempt < max_attempts - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            clean_err = re.sub(r'AIza[A-Za-z0-9_\-]{30,60}', '[REDACTED]', str(e))
            return ("not_found", None, None, f"Verification service unavailable: {clean_err}")

    if not raw_data:
        return ("not_found", None, None, "Empty response from verification model.")

    verdict_val: VerdictType = raw_data.get("verdict", "not_found")
    evidence_text: Optional[str] = raw_data.get("evidence_text")
    source_url: Optional[str] = raw_data.get("source_url")
    reasoning: str = raw_data.get("reasoning", "Evaluated based on gathered evidence.")

    # Pass 3: Calibrated Evidence Verification (Anti-Hallucination & Embellishment Filter)
    if verdict_val != "not_found" and evidence_text:
        valid = is_valid_evidence_text(evidence_text, relevant_facts)
        if not valid:
            verdict_val = "not_found"
            evidence_text = None
            source_url = None
            reasoning = "Evidence quotation provided by verification model was rejected (hallucinated or embellished with unsupported clauses)."

    if verdict_val == "not_found":
        evidence_text = None
        source_url = None

    return verdict_val, evidence_text, source_url, reasoning

def verify_single_claim(claim: Claim, all_facts: List[Any], api_key: Optional[str] = None) -> ClaimVerdict:
    """
    Multi-pass claim verification across all gathered evidence sources:
    Pass 1: Gather facts via category + alias matching.
    Pass 2: LLM reasoning for verdict generation using system_instruction and untrusted data tags.
    Pass 3: Calibrated programmatic evidence verification.
    """
    relevant_facts = get_candidate_facts_for_claim(claim, all_facts)

    if not relevant_facts:
        return ClaimVerdict(
            claim_text=claim.text,
            category=claim.category,
            source_type=claim.source_type,
            verdict="not_found",
            evidence_text=None,
            source_url=None,
            reasoning=f"No facts found under category '{claim.category}' or its aliases across any evidence source.",
            is_self_attested=True,
            evidence_source=None,
            trust_weight=0.0
        )

    # Sanity check facts for potential prompt injection attempts
    for fact in relevant_facts:
        f_text = getattr(fact, "text", getattr(fact, "content", ""))
        f_url = getattr(fact, "source_url", getattr(fact, "raw_reference", "unknown"))
        check_for_prompt_injection(f_text, source_identifier=f"fact from {f_url}")

    # Pass 2: LLM Reasoning & Qualifier Verification
    claim_text_to_eval = claim.core_text if claim.core_text else claim.text
    verdict_val, evidence_text, source_url, reasoning = _evaluate_claim_text(claim_text_to_eval, claim, relevant_facts, api_key)

    if verdict_val == "confirmed" and claim.qualifiers:
        worst_q_verdict = "confirmed"
        worst_q_qualifier = None
        worst_q_evidence = None
        worst_q_source = None
        
        for qualifier in claim.qualifiers:
            q_verdict, q_evidence, q_source, q_reasoning = _evaluate_claim_text(qualifier, claim, relevant_facts, api_key)
            
            if q_verdict == "contradicted":
                worst_q_verdict = "contradicted"
                worst_q_qualifier = qualifier
                worst_q_evidence = q_evidence
                worst_q_source = q_source
                break
            elif q_verdict in ["not_found", "partial"] and worst_q_verdict == "confirmed":
                worst_q_verdict = "partial"
                worst_q_qualifier = qualifier
                worst_q_evidence = q_evidence
                worst_q_source = q_source
                
        if worst_q_verdict == "contradicted":
            verdict_val = "contradicted"
            evidence_text = worst_q_evidence if worst_q_evidence else evidence_text
            source_url = worst_q_source if worst_q_source else source_url
            reasoning = f"Core claim confirmed, but qualifier '{worst_q_qualifier}' was contradicted."
        elif worst_q_verdict == "partial":
            verdict_val = "partial"
            # Keep original core evidence_text and source_url
            reasoning = f"Core claim confirmed, but no evidence found for '{worst_q_qualifier}' condition."

    # Identify matching fact and its source attribution
    is_self_attested = True
    evidence_source = None
    trust_weight = 0.5

    if verdict_val != "not_found" and evidence_text:
        for fact in relevant_facts:
            f_text = getattr(fact, "text", getattr(fact, "content", ""))
            norm_fact = normalize_text_for_comparison(f_text)
            norm_ev = normalize_text_for_comparison(evidence_text)
            if (
                evidence_text.strip().lower() in f_text.lower()
                or norm_ev in norm_fact
                or norm_fact in norm_ev
                or SequenceMatcher(None, norm_ev, norm_fact).ratio() > 0.65
            ):
                is_self_attested = getattr(fact, "is_self_attested", True)
                evidence_source = getattr(fact, "source_name", "site_crawl")
                trust_weight = getattr(fact, "trust_weight", 0.5)
                if not source_url:
                    source_url = getattr(fact, "source_url", getattr(fact, "raw_reference", None))
                break

    return ClaimVerdict(
        claim_text=claim.text,
        category=claim.category,
        source_type=claim.source_type,
        verdict=verdict_val,
        evidence_text=evidence_text,
        source_url=source_url,
        reasoning=reasoning,
        is_self_attested=is_self_attested,
        evidence_source=evidence_source,
        trust_weight=trust_weight
    )

def calculate_confidence_tier(
    verdicts: List[ClaimVerdict],
    all_facts: Optional[List[Any]] = None
) -> Tuple[ConfidenceTier, str, str, ScoreBreakdown]:
    """
    Calculates the confidence tier over evaluated claims and synthesizes a source-grounded 'why' explanation:
    - INSUFFICIENT_EVIDENCE: If 0 claims are addressed by site/source facts (all not_found).
    - CONTRADICTED: If one or more claims are contradicted by site facts, legal terms, or independent reviews.
    - VERIFIED: If claims are confirmed (0 contradicted) AND at least one confirmed claim
      is corroborated by an independent, non-self-attested 3rd-party source (e.g. CrossReferenceSource).
    - LIKELY_TRUE: If claims are confirmed/partial with 0 contradictions, but ALL evidence
      is self-attested by the promoter's own site crawl.
    """
    total_claims = len(verdicts)
    confirmed_count = sum(1 for v in verdicts if v.verdict == "confirmed")
    partial_count = sum(1 for v in verdicts if v.verdict == "partial")
    contradicted_count = sum(1 for v in verdicts if v.verdict == "contradicted")
    not_found_count = sum(1 for v in verdicts if v.verdict == "not_found")
    addressed_claims = confirmed_count + partial_count + contradicted_count

    breakdown = ScoreBreakdown(
        confirmed_count=confirmed_count,
        partial_count=partial_count,
        contradicted_count=contradicted_count,
        not_found_count=not_found_count,
        addressed_claims=addressed_claims,
        total_claims=total_claims
    )

    if total_claims == 0 or addressed_claims == 0:
        return (
            "INSUFFICIENT_EVIDENCE",
            "unverified_no_data",
            f"Insufficient Evidence: None of the {total_claims} reel claims were addressed by crawled evidence.",
            breakdown
        )

    if addressed_claims < total_claims:
        coverage_status = "partially_verified"
    else:
        coverage_status = "verified"

    parts = []
    if confirmed_count > 0:
        parts.append(f"{confirmed_count} confirmed")
    if contradicted_count > 0:
        parts.append(f"{contradicted_count} contradicted")
    if partial_count > 0:
        parts.append(f"{partial_count} partial")
    if not_found_count > 0:
        parts.append(f"{not_found_count} unaddressed")

    # Inspect sources that provided evidence
    agreeing_sources = {v.evidence_source for v in verdicts if v.verdict == "confirmed" and v.evidence_source}
    disagreeing_sources = {v.evidence_source for v in verdicts if v.verdict == "contradicted" and v.evidence_source}

    # Extract WHOIS domain age metadata if available
    whois_note = ""
    if all_facts:
        whois_facts = [f for f in all_facts if getattr(f, "source_name", "") == "whois"]
        if whois_facts:
            meta = getattr(whois_facts[0], "metadata", {})
            age_days = meta.get("domain_age_days")
            if age_days is not None:
                if age_days < 30:
                    whois_note = f"; domain is brand new ({age_days} days old)"
                elif age_days >= 730:
                    whois_note = f"; domain registered {age_days // 365} years ago"

    # 1. Contradictions take immediate precedence
    if contradicted_count > 0:
        confidence_tier: ConfidenceTier = "CONTRADICTED"
        source_str = "independent sources" if "cross_reference" in disagreeing_sources else "published site terms"
        summary_label = f"Contradicted: {', '.join(parts)} out of {total_claims} claims contradicted by {source_str}{whois_note}."
        return confidence_tier, coverage_status, summary_label, breakdown

    # 2. Check for independent (non-self-attested) corroboration
    has_non_self_attested_confirmation = any(
        v.verdict == "confirmed" and not getattr(v, "is_self_attested", True)
        for v in verdicts
    )

    if confirmed_count > 0 and has_non_self_attested_confirmation:
        confidence_tier = "VERIFIED"
        source_names = ", ".join(filter(None, agreeing_sources)) or "independent review & site sources"
        summary_label = f"Verified: {', '.join(parts)} out of {total_claims} claims corroborated by {source_names}{whois_note}."
    else:
        confidence_tier = "LIKELY_TRUE"
        summary_label = f"Likely True: {', '.join(parts)} out of {total_claims} claims confirmed via promoter site self-attestation{whois_note}."

    return confidence_tier, coverage_status, summary_label, breakdown

# Backward compatibility alias
calculate_trust_score = calculate_confidence_tier

def cross_check_claims(
    claims: List[Claim],
    site_facts: Optional[List[Any]] = None,
    facts: Optional[List[Any]] = None,
    api_key: Optional[str] = None
) -> CheckResponse:
    """
    Executes multi-source cross-checking for a list of claims against site/source facts.
    Returns CheckResponse with verdicts, confidence tier, coverage status, and source breakdown.
    Supports BYOK per-request api_key.
    """
    combined_facts: List[Any] = []
    if facts:
        combined_facts.extend(facts)
    if site_facts:
        combined_facts.extend(site_facts)

    verdicts: List[ClaimVerdict] = []

    for claim in claims:
        verdict = verify_single_claim(claim, combined_facts, api_key=api_key)
        verdicts.append(verdict)
        time.sleep(1.0)

    confidence_tier, coverage_status, summary_label, breakdown = calculate_confidence_tier(verdicts, all_facts=combined_facts)

    # Compute source breakdown counts
    source_counts: Dict[str, int] = {}
    for f in combined_facts:
        src = getattr(f, "source_name", "site_crawl")
        source_counts[src] = source_counts.get(src, 0) + 1

    return CheckResponse(
        confidence_tier=confidence_tier,
        coverage_status=coverage_status,
        summary_label=summary_label,
        score_breakdown=breakdown,
        verdicts=verdicts,
        source_breakdown=source_counts
    )
