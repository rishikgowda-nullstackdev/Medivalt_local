# MediVault Local — The Frozen Interface Contract

> **DO NOT DEVIATE WITHOUT GROUP AGREEMENT.**  
> This contract defines the inter-module interfaces between Person A, Person B, Person C, and Person D for MediVault Local.

---

## 1. Person B: Ingestion (`/ingestion`)
* **Function Signature:**
  ```python
  def process_file(file_path_or_bytes: Union[str, bytes], filename: Optional[str] = None) -> str:
      """
      Extracts text from PDF or TXT, applies HIPAA Safe Harbor regex redaction,
      and returns a single redacted plain-text string.
      """
  ```
* **Input:** A file path (`.pdf` or `.txt`) or file bytes.
* **Output:** A single redacted plain-text string.
  * *Example Input:* `"Patient: John Doe, Phone: 9876543210, Diagnosis: Stage 3 CKD"`
  * *Example Output:* `"Patient: [REDACTED_NAME], Phone: [REDACTED_PHONE], Diagnosis: Stage 3 CKD"`

---

## 2. Person C: AI Engine (`/ai_engine`)
* **Function Signature:**
  ```python
  def analyze(redacted_text: str) -> dict:
      """
      Cross-checks diagnostic history against local SQLite contraindications
      and returns a structured flag dictionary.
      """
  ```
* **Input:** A redacted clinical text string.
* **Output:** JSON object with exact shape:
  ```json
  {
    "flagged": true,
    "reason": "Administration of Ibuprofen is contraindicated due to Stage 3 Chronic Kidney Disease (risk of acute kidney injury).",
    "drug": "Ibuprofen",
    "severity": "CRITICAL"
  }
  ```
  *(If no contraindication is found: `{"flagged": false, "reason": "No adverse interactions detected.", "drug": null}`)*

---

## 3. Person A: Backend API (`/backend`)
* **Endpoint 1: `POST /upload-record`**
  * **Input:** Multipart form-data with key `file` (PDF or TXT)
  * **Output:**
    ```json
    {
      "redacted_text": "Patient: [REDACTED_NAME], Diagnosis: Stage 3 CKD..."
    }
    ```
* **Endpoint 2: `POST /analyze`**
  * **Input:** JSON payload:
    ```json
    {
      "redacted_text": "Patient: [REDACTED_NAME], Diagnosis: Stage 3 CKD..."
    }
    ```
  * **Output:**
    ```json
    {
      "flagged": true,
      "reason": "Administration of Ibuprofen is contraindicated due to Stage 3 CKD.",
      "drug": "Ibuprofen",
      "severity": "CRITICAL"
    }
    ```

---

## 4. Person D: Frontend Dashboard (`/frontend`)
* **Workflow:**
  1. Uploads clinical document $\rightarrow$ Calls `POST /upload-record`
  2. Receives `{ "redacted_text": "..." }` and displays de-identified text
  3. Doctor enters proposed medication or runs check $\rightarrow$ Calls `POST /analyze`
  4. Renders badge: 🔴 **CRITICAL CONTRAINDICATION** or 🟢 **SAFE TO PRESCRIBE**
