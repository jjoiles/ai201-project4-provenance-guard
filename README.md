# Provenance Guard

Provenance Guard is an AI-assisted content provenance system that analyzes submitted text and estimates whether the content is likely human-written, likely AI-generated, or uncertain.

The project focuses on transparency rather than presenting AI detection as definitive proof. It combines multiple detection signals, generates a confidence score, produces a transparency label, records decisions in an audit log, supports creator appeals, and protects the submission endpoint with rate limiting.

---

## Architecture Overview

A submission moves through the system using the following process:

1. A user submits text along with a `creator_id` to the `/submit` endpoint.
2. The API validates that the required information is present.
3. The submitted text is evaluated using two detection signals:
   - an LLM-based score
   - a stylometric score
4. The two signals are combined to determine an attribution result and confidence score.
5. The system assigns one of three classifications:
   - `likely_ai`
   - `likely_human`
   - `uncertain`
6. A transparency label is generated explaining the classification.
7. The result, confidence score, signal scores, creator ID, content ID, status, and timestamp are recorded in the audit log.
8. The API returns the classification and transparency information to the user.
9. If the creator disagrees with the result, an appeal can be submitted through the `/appeal` endpoint.
10. The appeal is added to the audit history and the content status changes to `under_review`.

The overall path is:

`Submission -> Validation -> Detection Signals -> Confidence/Attribution -> Transparency Label -> Audit Log -> Response`

If an appeal is necessary:

`Classification -> Creator Appeal -> Under Review -> Audit Log`

---

## Detection Signals

Provenance Guard uses two signals instead of relying on a single detector.

### 1. LLM Score

The LLM-based signal analyzes characteristics of the submitted text and returns a score representing how strongly the content resembles AI-generated writing.

This signal was selected because a language model can examine characteristics that are difficult to capture using simple rules, including structure, phrasing, consistency, and other linguistic patterns.

However, an LLM score is not proof of authorship. Human writers may produce highly structured text, while AI-generated text can be prompted to imitate informal human writing.

### 2. Stylometric Score

The stylometric signal examines writing characteristics such as sentence structure, variation, punctuation, and other stylistic patterns.

This provides a second signal that does not depend entirely on the LLM's judgment.

Stylometry also has limitations. Formal human writing can appear highly structured, while carefully prompted AI-generated writing may contain irregularities normally associated with human writing.

### Why Use Multiple Signals?

Neither signal can reliably determine authorship by itself. Combining them allows the system to recognize situations where the signals agree and, equally importantly, situations where they disagree.

When the evidence is mixed, Provenance Guard returns an `uncertain` result instead of forcing the content into an AI or human category.

---

## Confidence Scoring

The system combines the LLM and stylometric signals when determining the final attribution and confidence.

The confidence value should not be interpreted as mathematical proof that a particular person or AI system created the content. It represents the strength of the detection evidence available to Provenance Guard.

Testing showed why this distinction is important.

### Example 1 – Stronger AI Signal but Mixed Evidence

A formal AI-style test submission produced:

```text
LLM score: 0.70
Stylometric score: 0.32
Attribution: uncertain
```

Although the LLM signal was relatively high at `0.70`, the stylometric signal was much lower at `0.32`.

Because the detectors did not provide sufficiently consistent evidence, the system returned an uncertain classification instead of automatically labeling the submission as AI-generated.

This demonstrates why the project uses multiple signals rather than treating a single detector score as definitive.

### Example 2 – Lower Confidence / Likely Human

A more informal human-style submission produced:

```text
LLM score: 0.15
Stylometric score: 0.42
Confidence: 0.258
Attribution: likely_human
```

The much lower LLM score contributed to the system classifying the content as likely human-written.

### Additional Validation Example

Another test produced:

```text
LLM score: 0.55
Stylometric score: 0.48
Confidence: 0.522
Attribution: uncertain
```

The signals were near the middle of the range, so the system appropriately avoided making a strong authorship claim.

These examples demonstrate that the confidence mechanism responds differently to different writing samples and that mixed evidence can result in an uncertain classification.

---

## Transparency Labels

The system provides a human-readable transparency label instead of returning only a numeric score.

There are three possible label variants.

### High-Confidence AI / Likely AI-Generated

```text
Likely AI-Generated: Our analysis found strong indicators that this content was AI-generated. This classification is based on multiple detection signals and is not a definitive determination of authorship.
```

### Human / Likely Human-Written

```text
Likely Human-Written: Our analysis found strong indicators that this content was written by a human. This classification is based on multiple detection signals and is not a definitive determination of authorship.
```

### Uncertain

```text
Uncertain: Our analysis found mixed indicators and cannot confidently determine whether this content was human-written or AI-generated.
```

The wording intentionally avoids claiming certainty because AI-content detection can produce false positives and false negatives.

---

## Rate Limiting

The `/submit` endpoint is protected with rate limiting.

Rate limiting was included for two reasons:

1. It prevents a single user or client from repeatedly sending large numbers of requests in a short period.
2. It reduces unnecessary calls to the external model service and helps control resource usage.

The selected limits allow normal testing and usage while preventing rapid automated submission attempts.

The rate limiter was tested by sending repeated requests to the endpoint. Once the allowed number of requests was exceeded, the API returned:

```text
429
```

with the response:

```text
Rate limit exceeded
Please wait before submitting more content.
```

This confirmed that the rate-limiting protection was functioning correctly.

---

## Audit Log

Provenance Guard maintains an audit trail so that classification decisions can be reviewed later.

Each classification record includes information such as:

- content ID
- creator ID
- attribution
- confidence
- LLM score
- stylometric score
- status
- timestamp
- appeal reasoning, when applicable

The following entries are examples generated during testing.

### Audit Entry 1

```json
{
  "attribution": "uncertain",
  "confidence": 0.558,
  "content_id": "447aba41-70d6-461c-abfa-0700cae1bb7f",
  "creator_id": "test-ai",
  "llm_score": 0.65,
  "status": "classified",
  "stylometric_score": 0.42,
  "timestamp": "2026-10-06T01:49:44.026042+00:00"
}
```

### Audit Entry 2

```json
{
  "attribution": "likely_human",
  "confidence": 0.258,
  "content_id": "c778eca5-efeb-4ce3-a92a-e2876c55dd29",
  "creator_id": "test-human",
  "llm_score": 0.15,
  "status": "classified",
  "stylometric_score": 0.42,
  "timestamp": "2026-10-06T01:51:28.653822+00:00"
}
```

### Audit Entry 3 – Appealed Submission

```json
{
  "appeal_reasoning": "I wrote this content myself and believe the classification should be reviewed.",
  "attribution": "uncertain",
  "confidence": 0.522,
  "content_id": "ed0aa416-d714-4710-bcc7-57fbd0ae147b",
  "creator_id": "test-borderline-2",
  "llm_score": 0.55,
  "status": "under_review",
  "stylometric_score": 0.48,
  "timestamp": "2026-10-06T01:54:04.976493+00:00"
}
```

The third example demonstrates the appeal process. After the appeal was submitted, the content was changed to `under_review`, and the creator's reasoning was preserved in the audit history.

The complete testing log is stored in:

`audit_log.json`

---

## Appeal Process

Creators can challenge a classification through the `/appeal` endpoint.

An appeal includes:

- the `content_id`
- the creator's reasoning

For example:

```text
I wrote this content myself and believe the classification should be reviewed.
```

After the appeal is received, the system returns:

```text
Appeal received successfully.
```

and changes the status to:

```text
under_review
```

This feature is important because automated AI-content detection should not be treated as unquestionable evidence.

---

## Known Limitations

A major limitation of the system is that formal human writing may resemble AI-generated writing.

For example, academic essays, technical reports, professional communications, and other highly structured human writing may contain consistent sentence structure and polished language that an AI detector associates with generated content.

The opposite problem can also occur. AI-generated content can be intentionally prompted to include slang, grammatical inconsistencies, short sentences, personal language, or other characteristics associated with human writing.

Testing demonstrated this limitation directly. One formal AI-style test received an LLM score of `0.70`, but its stylometric score was only `0.32`. The system therefore returned `uncertain`.

This is why Provenance Guard uses cautious labels such as `likely_human`, `likely_ai`, and `uncertain` rather than claiming to determine authorship with certainty.

---

## Spec Reflection

### How the Specification Helped

The specification helped define the system as more than a basic AI detector. In particular, the requirements for transparency labels, confidence scoring, audit logging, rate limiting, and appeals encouraged the project to consider how an AI detection system affects the people whose content is being evaluated.

The appeal requirement was especially useful because it introduced a human-review path rather than treating an automated classification as final.

### How My Implementation Diverged

The implementation uses a relatively lightweight combination of an LLM signal and a stylometric signal rather than a production-grade provenance infrastructure or specialized trained detection model.

This decision kept the project small enough to implement and test within the assignment while still demonstrating the required architecture and responsible-AI concepts.

A production implementation would require substantially more validation data, calibrated thresholds, security controls, persistent storage, authentication, and evaluation across different writing populations.

---

## AI Usage

AI tools were used as development assistance during this project.

### Instance 1 – API Structure and Debugging

I directed AI to help me structure and debug the Flask API, including the submission flow, JSON responses, classification logic, and endpoint behavior.

I did not simply accept the first generated solution. I ran the application locally, tested the endpoints using PowerShell requests, reviewed the returned scores and classifications, and revised the implementation when the behavior did not match the intended project requirements.

### Instance 2 – Detection and Transparency Logic

I used AI assistance while developing the detection and transparency logic, including how the LLM score and stylometric score could contribute to the final classification.

During testing, I revised the approach based on actual outputs. For example, a test produced an LLM score of `0.70` but a stylometric score of `0.32`. Rather than treating the LLM result alone as proof of AI authorship, I retained the uncertain classification because the signals disagreed.

### Instance 3 – Documentation

I used AI to help organize the README and explain the architecture and testing evidence clearly.

I verified the documentation against the actual outputs produced by the application and used the real confidence scores, classifications, audit entries, appeal result, and rate-limit response from my testing rather than presenting invented test results.

---
## Portfolio Walkthrough Video

A short walkthrough demonstrating Provenance Guard working end-to-end, including the submission process, detection signals, transparency labels, audit logging, appeal process, and rate limiting.

**Video Link:** [PASTE YOUR VIDEO LINK HERE]

---
## Running the Project

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file and add the required API key:

```text
GROQ_API_KEY=your_api_key_here
```

The `.env` file is excluded from Git and should never be committed.

### 4. Start the Application

```powershell
python app.py
```

The development server runs locally at:

```text
http://127.0.0.1:5000
```

---

## Project Files

- `app.py` — Contains the Flask application, detection logic, classification process, transparency labels, audit logging, appeal handling, and rate limiting.
- `planning.md` — Documents the project's initial plan and design decisions.
- `audit_log.json` — Contains the audit trail generated during testing.
- `requirements.txt` — Lists the Python dependencies required to run the project.
- `README.md` — Contains the architecture, implementation decisions, testing evidence, limitations, reflection, and usage documentation.

---

## Responsible Use

Provenance Guard is a demonstration project and should not be used as definitive evidence that a person did or did not use artificial intelligence.

AI-content detection is probabilistic and can make mistakes. Classification results should therefore be treated as signals for further review rather than proof of authorship.
