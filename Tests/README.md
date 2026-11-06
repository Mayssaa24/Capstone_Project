#AI-Powered Waste Sorting & Recycling Assistant
#Flask app: take or upload a photo → Hugging Face classifier → local recycling rules (Dortmund) → AI coach tips → results saved to MySQL → live charts and trends.

## 1. Team Overview 
## Team and Responsibilities

| Name | Overall role | 1. OOP classes | 2. Stream processing | 3. Flask and MySQL | 4. Errors and tests |
|---|---|---|---|---|---|
| **Manjeet (Classifier)** | Identifies the item in the uploaded photo using a Hugging Face model. | Classes that check the photo and run the model behind one interface (`ImagePreprocessor`, `BaseClassifier`, `ClassifierService`). | Pipeline that drops unsure results, maps labels to materials and keeps the best few (`ConfidenceFilter` \| `LabelNormalizer` \| `TopKLimiter`). | Photo upload route `/api/scan`: validates the image, runs the model, returns the result. | Error classes and handler for bad images and model failures; 57 tests. |
| **Deepika (Rules and Database)** | Decides which bin the item goes in and stores every scan. | Classes for the recycling rules and for saving scans (`RuleSet`, `RulesEngine`, `Database`, `ScanRepository`). | Pipeline that turns results into decisions, adds a lane code and saves them (`DecisionMapper` \| `RoutingCodeAssigner` \| `ScanRecorder`). | SQLAlchemy models and the MySQL connection that save and read scans. | Error classes and handlers for invalid rules and database failures; 43 tests. |
| **Divya (Dashboard)** | Turns saved scans into charts and trends, and built the single page. | Classes that calculate the statistics and build the chart data (`ScanAnalytics`, `ChartBuilder`, `DashboardService`). | Pipeline that filters scans by region and date and counts them per day (`RegionFilter` \| `DateRangeFilter` \| `DailyAggregator`). | `/api/dashboard` route and the single page with the photo buttons and charts. | Error class and handler for the dashboard; 35 tests. |
| **Mayassa (AI Coach)** | Writes the tips and fun fact, with offline tips if the AI is down. | Classes that ask the AI for advice or use offline tips (`PromptBuilder`, `OpenAICoach`, `OfflineCoach`, `CoachService`). | Pipeline that builds the prompt, gets advice and cleans the tips (`PromptStage` \| `AdviceStage` \| `TipCleaner` \| `TipLimiter`). | Connects the KI:connect AI to the scan response, with an offline fallback. | Error class and handler for an unavailable AI, plus the fallback; 40 tests. |

**Shared by everyone:** Connecting the four subsystems, the shared error structure, the README, the UML diagrams and the video.

## Explanation video
``` 
https://drive.google.com/file/d/1Y955B8ukOM_IEihDlNcIvEC2vYu5zHQ_/view?usp=sharing
```

## Testing each subsystem

Run from the project folder (the one containing `app` and `tests`):

```powershell
cd D:\Downloads\waste_sorting_final2\waste_sorting
```

### Dashboard
```powershell
python -m app.dashboard.analytics "sqlite:///waste_sorting.db" Dortmund
```

### Coach
```powershell
python -m app.coach.coach "glass bottle" glass Dortmund
```

### Classifier
```powershell
python -m app.classifier.classifier_oop "C:\path\to\image.jpg"
```

### Rules and database
```powershell
python -m app.rules.database "sqlite:///waste_sorting.db"
python -m app.rules.database "sqlite:///waste_sorting.db" Dortmund
```

## Running the tests

Run all commands from the project folder (the one containing `app` and `tests`):

```powershell
cd D:\Downloads\waste_sorting_final2\waste_sorting
```

### All tests

```powershell
python -m pytest -v
```

### Each subsystem

```powershell

python -m pytest tests/test_classifier.py -v

python -m pytest tests/test_rules_database.py -v
python -m pytest tests/test_dashboard.py -v
python -m pytest tests/test_coach.py -v
```

### Tests by category

```powershell
python -m pytest -m unit -v
python -m pytest -m integration -v
python -m pytest -m functional -v
python -m pytest -m regression -v
```

python -m pytest -m unit --cov=app --cov-report=term-missing

### Test coverage

Run the unit tests with coverage (needs `pytest-cov`):

```powershell
python -m pytest -m unit --cov=app --cov-report=term-missing
```

The report lists, for each file, the number of statements, how many were missed, the coverage percentage, and the line numbers no test reached.

To measure coverage across all tests:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```
## Error Handling

All error classes are in `errors.py`. Every subsystem has its own exception classes and its own handler class, so a problem in one subsystem is reported with a clear message and never crashes the page.

### How it works
- `WasteSortingError` is the base class for every exception. It stores a message, a details dictionary, an HTTP status code and the name of the subsystem.
- `SubsystemErrorHandler` is the base class for the handlers. It logs the error and returns it as JSON.
- `register_error_handlers(app)` attaches the five subsystem handlers to the Flask app. It also handles unknown URLs (404), files that are too large (413) and unexpected errors (500).
- Every error is returned in the same JSON format:

```json
{"error": {"code": "invalid_image", "subsystem": "classifier",
           "message": "The file is not a valid image.", "details": {}}}
```

### Error classes per subsystem

| Subsystem | Handler class | Exceptions | Raised when | Status |
|---|---|---|---|---|
| Classifier | `ClassifierErrorHandler` | `ClassifierError` (base) | Any classifier problem | 500 |
| | | `InvalidImageError` | The upload is missing, empty, too large or not an image | 400 |
| | | `ModelLoadError` | The Hugging Face model cannot be loaded | 503 |
| | | `InferenceError` | The model fails while predicting | 500 |
| AI Coach | `CoachErrorHandler` | `CoachError` (base) | Any coach problem | 500 |
| | | `CoachUnavailableError` | No API key, timeout or a bad reply from the AI | 502 |
| Rules | `RulesErrorHandler` | `RulesError` (base) | Any rules problem | 500 |
| | | `InvalidRuleError` | A rule has an empty material, bin or region | 400 |
| Database | `DatabaseErrorHandler` | `StorageError` | A scan cannot be saved or read | 500 |
| Dashboard | `DashboardErrorHandler` | `DashboardError` | An invalid number of days, region, tolerance or date range | 500 |

### Examples
- Uploading a text file to `/api/scan` raises `InvalidImageError`, and the response is status 400 with `"code": "invalid_image"`.
- If the AI coach is unavailable, `CoachService` catches `CoachUnavailableError` and uses the offline coach, so the user still gets tips.
- If MySQL is not reachable, `StorageError` is returned as a JSON error instead of a crash.
