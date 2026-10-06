# Provenance Guard

Provenance Guard is a lightweight AI content attribution and transparency system. It analyzes submitted text using two independent detection signals, combines those signals into a confidence score, assigns an attribution result, displays a transparency label, records the decision in a structured audit log, and provides creators with an appeals process.

The goal of this project is not to claim that AI authorship can be determined with certainty. Instead, the system demonstrates how multiple imperfect signals can be combined with uncertainty-aware labels, logging, and an appeals mechanism to create a more responsible attribution workflow.

---

## System Architecture

Provenance Guard is implemented as a Flask API with two primary workflows: content submission and creator appeal.

### Submission Flow

```text
                         Raw Text + Creator ID
                                  |
                                  v
                           POST /submit
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
          LLM-Based Classification     Stylometric Analysis
               (Groq API)                 (Pure Python)
                    |                           |
                    | llm_score                 | stylometric_score
                    +-------------+-------------+
                                  |
                                  v
                         Confidence Scoring
                    60% LLM + 40% Stylometric
                                  |
                                  v
                         Attribution Result
                                  |
                                  v
                         Transparency Label
                                  |
                                  v
                            Audit Log
                                  |
                                  v
                           JSON Response
```

### Appeal Flow

```text
                Content ID + Creator Reasoning
                              |
                              v
                       POST /appeal
                              |
                              v
                   Locate Original Decision
                              |
                              v
                 Status = "under_review"
                              |
                              v
                    Update Audit Log
                              |
                              v
                    Confirmation Response
```

The `/submit` endpoint receives text and a creator identifier. The text is independently analyzed by an LLM-based signal and a stylometric signal. Their scores are combined into a single confidence score, which determines the attribution result and transparency label. The decision is then recorded in the audit log.

The `/appeal` endpoint allows a creator to provide the original content ID and reasoning for an appeal. The associated decision is changed from `classified` to `under_review`, and the appeal is recorded in the audit log.

---

## API Endpoints

### `GET /`

Confirms that the API is running.

Example response:

```json
{
  "message": "Provenance Guard API is running"
}
```

### `POST /submit`

Accepts text for analysis.

Required JSON fields:

```json
{
  "text": "Text to analyze",
  "creator_id": "creator identifier"
}
```

The response includes:

- `content_id`
- `attribution`
- `confidence`
- `label`
- individual detection signals
- `status`

### `POST /appeal`

Allows a creator to appeal an existing classification.

Required JSON fields:

```json
{
  "content_id": "original content ID",
  "creator_reasoning": "Reason the classification should be reviewed"
}
```

### `GET /log`

Returns the structured audit history containing classification and appeal information.

---

## Detection Signal 1: LLM-Based Classification

The first signal uses a language model through the Groq API.

The implementation uses:

```text
openai/gpt-oss-120b
```

The model receives the submitted text and is instructed to estimate the likelihood that the content is AI-generated.

The model must return a score between:

```text
0.0 = strongly human-written
1.0 = strongly AI-generated
```

The response is parsed as JSON and validated so that the resulting score remains between 0.0 and 1.0.

### Why This Signal Was Chosen

A language model can evaluate characteristics that are difficult to represent with a single numerical heuristic, including phrasing, structural consistency, tone, and other broad linguistic patterns.

However, an LLM judgment is not treated as proof of authorship. It is only one signal in the system.

---

## Detection Signal 2: Stylometric Analysis

The second signal is implemented locally in Python and does not use an external model.

It evaluates three measurable properties of the submitted text:

1. Sentence-length variation
2. Vocabulary diversity
3. Punctuation density

Sentence-length variation measures how much sentence lengths differ throughout the text. Vocabulary diversity compares the number of unique words with the total number of words. Punctuation density measures selected punctuation marks relative to the number of words.

The three measurements are converted into AI-likelihood values and combined into one stylometric score.

### Why This Signal Was Chosen

The stylometric signal provides a second source of evidence that is independent of the LLM call. It also makes the system more interpretable because its calculations are based on measurable textual characteristics.

These characteristics are imperfect indicators and should not be interpreted as proof that content was written by either a human or an AI system.

---

## Confidence Scoring

The final confidence score combines the two independent signals.

The formula is:

```text
combined confidence =
(LLM score × 0.60) +
(stylometric score × 0.40)
```

The LLM signal receives a weight of 60% because it can evaluate broader linguistic patterns.

The stylometric signal receives a weight of 40% because it provides useful independent structural evidence but relies on simplified heuristics.

---

## Uncertainty Representation

The combined score is converted into one of three attribution categories.

| Combined Score | Attribution |
|---|---|
| 0.00–0.34 | Likely Human |
| 0.35–0.69 | Uncertain |
| 0.70–1.00 | Likely AI |

The middle range is intentionally broad. AI-content attribution is uncertain, and a system that forces every submission into either "human" or "AI" risks presenting weak evidence as certainty.

---

## Transparency Labels

The system displays one of three transparency labels.

### High-Confidence AI

> **Likely AI-Generated:** Our analysis found strong indicators that this content may have been generated by AI. This classification is based on multiple detection signals and is not a definitive determination of authorship.

### High-Confidence Human

> **Likely Human-Written:** Our analysis found strong indicators that this content was written by a human. This classification is based on multiple detection signals and is not a definitive determination of authorship.

### Uncertain

> **Uncertain:** Our analysis found mixed indicators and cannot confidently determine whether this content was human-written or AI-generated.

The wording intentionally communicates uncertainty instead of presenting the system's output as definitive proof.

---

## Evaluation and Testing

The system was tested with four deliberately different writing samples.

| Test | LLM Score | Stylometric Score | Combined Confidence | Classification |
|---|---:|---:|---:|---|
| AI-style writing | 0.65 | 0.42 | 0.558 | Uncertain |
| Informal human-style writing | 0.15 | 0.42 | 0.258 | Likely Human |
| Formal/borderline writing | 0.25 | 0.34 | 0.286 | Likely Human |
| Borderline mixed-style writing | 0.55 | 0.48 | 0.522 | Uncertain |

These tests demonstrate that the two signals produce different values and that the combined confidence score varies across inputs.

### Example 1: AI-Style Writing

The AI-style test produced:

```text
LLM score:          0.65
Stylometric score: 0.42
Combined score:    0.558
Classification:    Uncertain
```

This result was lower than expected for deliberately AI-style writing. It demonstrates an important limitation: polished or structured text cannot reliably be attributed to AI based only on linguistic characteristics.

Rather than manually changing the result, the system preserved the score and returned the uncertainty label.

### Example 2: Informal Human-Style Writing

The informal human-style test produced:

```text
LLM score:          0.15
Stylometric score: 0.42
Combined score:    0.258
Classification:    Likely Human
```

The LLM signal identified substantially more human-like characteristics in this example, while the stylometric signal remained at 0.42.

This also demonstrates why the system retains both signal scores rather than hiding them behind the combined result.

### Borderline Results

The first borderline test produced a combined confidence of `0.286` and was classified as Likely Human.

The second borderline test produced a combined confidence of `0.522` and was classified as Uncertain.

These results demonstrate that writing style can substantially affect attribution scores and reinforce the need for an uncertainty category.

---

## Appeals Workflow

Creators can appeal classifications they believe are incorrect.

An appeal requires:

```text
content_id
creator_reasoning
```

When an appeal is submitted:

1. The system locates the original classification.
2. The original status changes from `classified` to `under_review`.
3. The creator's reasoning is attached to the classification.
4. A separate appeal event is added to the audit log.
5. The API confirms that the appeal was received.

The system does not automatically reverse a classification. It places the decision under review so that a human reviewer could evaluate it later.

### Appeal Test

An appeal was submitted for the content ID:

```text
ed0aa416-d714-4710-bcc7-57fbd0ae147b
```

with the reasoning:

> I wrote this content myself and believe the classification should be reviewed.

The endpoint successfully returned:

```text
status: under_review
message: Appeal received successfully.
```

The audit log subsequently showed both the updated original classification and a separate appeal event.

---

## Audit Logging

Provenance Guard stores structured decision records in:

```text
audit_log.json
```

Classification records include:

- Content ID
- Creator ID
- Timestamp
- Attribution
- LLM score
- Stylometric score
- Combined confidence
- Review status
- Appeal reasoning when applicable

### Example Audit Entry

```json
{
  "appeal_reasoning": null,
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

The `/log` endpoint was tested after classification and appeal operations. The resulting log contained multiple classification records and the appeal event.

---

## Rate Limiting

The `/submit` endpoint is rate limited using Flask-Limiter.

The configured limits are:

```text
10 submissions per minute
100 submissions per day
```

Rate limiting helps prevent automated abuse, excessive API usage, and unnecessary consumption of the external model service.

The limit was tested by sending repeated requests to `/submit`.

Initial intentionally incomplete requests returned:

```text
400
```

After the request threshold was reached, the server returned:

```text
429
```

with:

```json
{
  "error": "Rate limit exceeded",
  "message": "Please wait before submitting more content."
}
```

This confirms that the endpoint blocks excessive requests.

---

## Error Handling

The API validates incoming requests before attempting classification.

Examples include:

- Missing JSON body → HTTP 400
- Missing `text` → HTTP 400
- Missing `creator_id` → HTTP 400
- Missing appeal information → HTTP 400
- Unknown content ID during appeal → HTTP 404
- Excessive submissions → HTTP 429
- Detection/API failure → HTTP 500

This prevents malformed requests from being processed as valid classifications.

---

## Limitations

Provenance Guard is a demonstration system and should not be used as definitive evidence of authorship.

### False Positives

Highly polished human writing may appear structurally similar to AI-generated writing. Academic, professional, or technical writing may therefore receive an elevated AI-likelihood score.

A false positive could unfairly affect a creator if the result were treated as proof rather than probabilistic evidence.

### False Negatives

AI-generated text that has been substantially edited by a human may appear more human-like to both signals. The system only evaluates the submitted text and does not have access to its complete creation history.

### Stylometric Limitations

Sentence variation, vocabulary diversity, and punctuation usage are not unique indicators of AI generation. Human writers naturally differ in style, education, language background, genre, and editing habits.

### LLM Limitations

The LLM itself cannot know who authored a piece of text. It is making an inference based on patterns in the submitted content.

The AI-style evaluation example illustrates this limitation: text intentionally written in a polished AI-like style received a combined score of only `0.558`, resulting in an Uncertain classification.

### Short Text

Very short submissions provide fewer linguistic features for either signal to evaluate and may therefore produce less meaningful results.

---

## Potential Harm and Mitigation

Incorrect attribution could negatively affect writers, students, employees, journalists, or creators if an automated classification were treated as definitive proof.

The project attempts to reduce this risk through:

- Two independent signals
- A broad uncertainty range
- Transparency labels that avoid claims of certainty
- Preservation of individual signal scores
- Structured audit logging
- An appeals workflow
- Human review rather than automatic reversal of appealed decisions

The system is intended to support review and transparency, not replace human judgment.

---

## Spec Reflection

### How the Specification Helped

Writing the specification before implementation made the relationship between the detection signals, confidence score, transparency labels, audit logging, and appeals workflow explicit before coding began.

The predefined thresholds also made implementation more consistent because classification behavior was decided before test results were observed.

### Where Implementation Diverged

The original plan referenced the Groq model:

```text
meta-llama/llama-4-scout-17b-16e-instruct
```

During implementation, the API returned a model-not-found/access error.

The implementation therefore uses:

```text
openai/gpt-oss-120b
```

The overall signal design remained unchanged: the model receives text and returns an AI-likelihood score between 0.0 and 1.0.

This change was made because the originally planned model was unavailable in the development environment.

---

## AI Tool Usage

AI tools were used during development as an implementation assistant rather than as an unchecked source of final code.

### Instance 1: Flask API Structure

I directed the AI assistant to help implement the Flask application and `/submit` endpoint based on the requirements already defined in `planning.md`.

I tested the endpoint first with placeholder values before connecting it to the Groq detection signal. I then verified the LLM signal independently before integrating it into `/submit`.

### Instance 2: Detection and Confidence Logic

I directed the AI assistant to implement the second stylometric signal and the 60/40 confidence formula from my specification.

I verified the implementation using four deliberately different text samples and retained the actual results even when they differed from expectations.

For example, the deliberately AI-style text received a combined score of `0.558` instead of a high-confidence AI classification. I did not alter the score to force the expected result.

### Instance 3: Production Features

I directed the AI assistant to implement the transparency labels, appeals workflow, audit logging, and rate limiting according to the previously written specification.

I manually tested the appeal workflow and verified that the classification changed to `under_review`. I also tested the rate limiter and confirmed that excessive requests returned HTTP 429.

### Human Verification

All generated implementation assistance was tested locally before being accepted. Test outputs, confidence scores, audit entries, and error responses were observed from the running application rather than fabricated for documentation.

---

## Project Files

```text
ai201-project4-provenance-guard/
│
├── app.py
├── planning.md
├── README.md
├── requirements.txt
├── audit_log.json
├── .env
├── .gitignore
└── .venv/
```

The `.env` file and `.venv` directory should not be committed to GitHub.

---

## Installation

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a `.env` file containing:

```text
GROQ_API_KEY=your_api_key_here
```

Do not commit the `.env` file.

Run the application:

```powershell
python app.py
```

The development server will run locally at:

```text
http://127.0.0.1:5000
```

---

## Dependencies

The project uses:

- Flask
- Flask-Limiter
- Groq Python SDK
- python-dotenv

Python's standard library is also used for JSON handling, UUID generation, regular expressions, statistics, timestamps, and file operations.

---

## Conclusion

Provenance Guard demonstrates that AI-content attribution should be treated as an uncertain inference rather than a definitive authorship test.

By combining multiple detection signals with transparent confidence scoring, uncertainty-aware labels, structured logging, rate limiting, and a creator appeals process, the project emphasizes responsible handling of attribution decisions while acknowledging the technical limitations of AI-detection systems.