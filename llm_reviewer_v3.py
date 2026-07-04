"""
POLIS LLM Reviewer v3.0
Scores events against five behavioural dimensions.
Replaces theory classification entirely.
Run: python3 llm_reviewer_v3.py
"""
import hashlib
import json
import os
import sys
import uuid
import urllib.request
import time
from datetime import datetime

# Force stdout to UTF-8 - terminal may default to latin-1 on older macOS
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DATASET_FILE = "polis_lse_dataset.json"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

DIMENSION_PROMPT = """You are a behavioural analyst for POLIS - the Public Leadership Observation and Insight System.

Your job is to score a single presidential leadership signal event against five behavioural dimensions.

You are NOT interpreting leadership quality.
You are NOT assigning leadership theories.
You are measuring observable behavioural signals only.

THE FIVE DIMENSIONS:

1. ACCOUNTABILITY
Does this event show the president enforcing or submitting to institutional oversight?
Signals: anti-corruption actions, judicial enforcement, audit responses, transparency actions, prosecutions of officials

2. RESPONSIVENESS
Does this event show action following stated priorities or public needs?
Signals: policy implementation, welfare actions, crisis response, citizen-directed resource allocation

3. STEWARDSHIP
Does this event show investment in long-term public capability?
Signals: institutional reform, infrastructure, capacity building, legislative strengthening, public service investment

4. INSTITUTIONAL INTEGRITY
Is authority being exercised through formal institutions or bypassing them?
High score = through institutions. Low score = bypassing them.
Signals: parliamentary routing, judicial independence respected, executive decrees bypassing process, procedural compliance

5. INCLUSION
Does this event show accommodation of diverse actors and voices?
Signals: consultations, dialogues, opposition engagement, community forums, coalition behaviour

SCORING RULES:
- Score each dimension 0.0 to 1.0
- Score ONLY dimensions this event provides direct observable evidence for
- null = no observable evidence for this dimension in this event text
- 0.0 = clear evidence of absence or violation of this dimension
- 1.0 = clear strong positive evidence for this dimension
- Assign confidence as: high, medium, or low based on signal clarity
- high = signal is explicit and unambiguous
- medium = signal is present but requires inference
- low = signal is weak or indirect
- rationale = one sentence only, describing the primary observable signal

RESPOND ONLY WITH VALID JSON. No explanation. No markdown fences.
Example:
{"accountability": {"score": 0.8, "confidence": "high"}, "responsiveness": {"score": null, "confidence": null}, "stewardship": {"score": null, "confidence": null}, "institutional_integrity": {"score": 0.6, "confidence": "medium"}, "inclusion": {"score": null, "confidence": null}, "rationale": "President signs anti-corruption bill through parliamentary process"}"""


def score_event(event):
    evidence = event.get("evidence", "")
    country  = event.get("country", "")
    domain   = event.get("domain", "")
    action   = event.get("action_type", "")

    prompt = f"""{DIMENSION_PROMPT}

Score this event:

Country: {country}
Domain: {domain}
Action type: {action}
Evidence: {evidence}"""

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
      try:
        payload = json.dumps({
            "model": "claude-sonnet-4-5",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         API_KEY,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text   = result["content"][0]["text"].strip()
            text   = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)

            # FIX 3: Strict schema validation
            # Normalise all null-like values to Python None
            # Reject scores outside 0.0-1.0 range
            VALID_CONFIDENCE = {"high", "medium", "low", None}
            dims = ["accountability", "responsiveness", "stewardship",
                    "institutional_integrity", "inclusion"]
            for d in dims:
                if d not in parsed:
                    parsed[d] = {"score": None, "confidence": None}

                # Normalise score
                raw_score = parsed[d].get("score")
                if raw_score in ("", "null", "none", "None") or raw_score is None:
                    parsed[d]["score"] = None
                else:
                    try:
                        s = float(raw_score)
                        parsed[d]["score"] = round(max(0.0, min(1.0, s)), 3)
                    except (TypeError, ValueError):
                        parsed[d]["score"] = None

                # Normalise confidence
                raw_conf = parsed[d].get("confidence")
                if isinstance(raw_conf, str):
                    raw_conf = raw_conf.lower().strip()
                if raw_conf not in VALID_CONFIDENCE:
                    parsed[d]["confidence"] = None
                else:
                    parsed[d]["confidence"] = raw_conf

            return {
                "dimensions":       {d: parsed[d] for d in dims},
                "rationale":        parsed.get("rationale", ""),
                "needs_llm_review": False,
            }

      except Exception as e:
        err = str(e).encode("ascii", errors="replace").decode("ascii")
        if attempt < MAX_RETRIES:
            print("  LLM error (attempt {}/{}): {} -- retrying...".format(
                attempt, MAX_RETRIES, err))
            time.sleep(1.5 * attempt)
        else:
            print("  LLM error (final): " + err)
            return None


def run_scoring():
    # Scoring provenance — frozen per run for reproducibility
    MODEL_VERSION   = "claude-sonnet-4-5"
    SCORING_DATE    = datetime.utcnow().strftime("%Y-%m-%d")
    SCORING_RUN_ID  = str(uuid.uuid4())[:8]
    PROMPT_VERSION  = hashlib.sha256(
        DIMENSION_PROMPT.encode("utf-8")
    ).hexdigest()[:8]
    print("Scoring run:         " + SCORING_RUN_ID)
    print("Model:               " + MODEL_VERSION)
    print("Prompt version:      " + PROMPT_VERSION)
    print("Date:                " + SCORING_DATE)
    print("")

    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("Run: export ANTHROPIC_API_KEY=your_key_here")
        return

    with open(DATASET_FILE, "r") as f:
        raw = json.load(f)

    # Support both flat array (legacy) and metadata-wrapped structure
    if isinstance(raw, dict) and "events" in raw:
        metadata = raw.get("metadata", {})
        data = raw["events"]
    else:
        metadata = {}
        data = raw

    # FIX 1: Assign stable event_id to any event that lacks one
    # sha256(evidence + country) — deterministic, collision-resistant for this scale
    changed_ids = 0
    for e in data:
        if e.get("is_leadership_event") and "event_id" not in e:
            raw = (e.get("evidence", "") + e.get("country", "")).encode("utf-8")
            e["event_id"] = hashlib.sha256(raw).hexdigest()[:16]
            changed_ids += 1
    if changed_ids:
        print("Assigned event_id to {} events".format(changed_ids))


    DIMS = ["accountability","responsiveness","stewardship",
            "institutional_integrity","inclusion"]

    def has_real_score(e):
        return any(
            e.get("dimensions",{}).get(d,{}).get("score") is not None
            for d in DIMS
        )

    # Score all leadership events that lack dimension vectors
    to_score = [
        e for e in data
        if e.get("is_leadership_event")
        and not has_real_score(e)
    ]

    # Also re-score events still carrying old theory labels as primary output
    already_scored = len([e for e in data
                          if e.get("is_leadership_event")
                          and has_real_score(e)])

    print("=" * 55)
    print("POLIS DIMENSION SCORER v3.0")
    print("=" * 55)
    print("Total events:        " + str(len(data)))
    print("Already scored:      " + str(already_scored))
    print("To score:            " + str(len(to_score)))
    print("")

    if not to_score:
        print("All events already scored.")
        _print_summary(data)
        return

    updated = 0
    failed  = 0

    for i, event in enumerate(to_score):
        evidence = event.get("evidence", "")[:60].encode(
            "ascii", errors="replace").decode("ascii")
        country  = event.get("country", "?")
        print("[{}/{}] {} | {}".format(i + 1, len(to_score), country, evidence))

        result = score_event(event)

        if result:
            # FIX 2: Match by event_id — stable and unambiguous
            event_id = event.get("event_id")
            matched = False
            for e in data:
                if e.get("event_id") == event_id:
                    e["dimensions"]       = result["dimensions"]
                    e["rationale"]        = result["rationale"]
                    e["needs_llm_review"] = False
                    e["needs_scoring"]    = False
                    e["model_version"]    = MODEL_VERSION
                    e["scoring_date"]     = SCORING_DATE
                    e["scoring_run_id"]   = SCORING_RUN_ID
                    e["prompt_version"]   = PROMPT_VERSION
                    matched = True
                    break
            if not matched:
                # Fallback to evidence+country if id missing (legacy events)
                for e in data:
                    if (e.get("evidence") == event.get("evidence")
                            and e.get("country") == event.get("country")):
                        e["dimensions"]       = result["dimensions"]
                        e["rationale"]        = result["rationale"]
                        e["needs_llm_review"] = False
                        break

            # Print dimension scores concisely
            dims = result["dimensions"]
            scored = {k: v["score"] for k, v in dims.items()
                      if v["score"] is not None}
            print("  -> " + " | ".join(
                "{}: {:.2f}".format(k[:4], v)
                for k, v in scored.items()
            ))
            updated += 1
        else:
            failed += 1

        time.sleep(0.4)

    # Save — preserve metadata wrapper
    with open(DATASET_FILE, "w") as f:
        if metadata:
            json.dump({"metadata": metadata, "events": data}, f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)

    print("")
    print("=" * 55)
    print("SCORED:              " + str(updated))
    print("FAILED:              " + str(failed))
    print("")
    _print_summary(data)


def _print_summary(data):
    events = [e for e in data
              if e.get("is_leadership_event") and "dimensions" in e]

    if not events:
        print("No scored events yet.")
        return

    dims = ["accountability", "responsiveness", "stewardship",
            "institutional_integrity", "inclusion"]

    print("DIMENSION AVERAGES (scored events only):")
    for d in dims:
        scores = [e["dimensions"][d]["score"]
                  for e in events
                  if e.get("dimensions", {}).get(d, {}).get("score") is not None]
        if scores:
            avg = sum(scores) / len(scores)
            coverage = len(scores)
            bar = "#" * int(avg * 30)
            print("  {:<22} {:.2f}  n={}  {}".format(d, avg, coverage, bar))
        else:
            print("  {:<22} no data".format(d))


if __name__ == "__main__":
    run_scoring()
