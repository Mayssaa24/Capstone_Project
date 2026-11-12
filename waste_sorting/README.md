# AI-Powered Waste Sorting Assistant

A user takes a photo of an item. An AI model classifies the material, local rules (Dortmund) decide which bin it belongs in, an AI coach gives tips, and a dashboard shows recycling statistics.

---

## 1. Team Overview

| Team member | Subsystem | Implemented classes | Source files |
|---|---|---|---|
| [Manjeet] | Classifier | `WasteImage`, `PredictionResult`, `WasteClassifier`, `ModelEvaluator` | `app/classifier/classifier_oop.py` |
| [Deepika] | Rules and Database | `Rule`, `RuleSet`, `Decision`, `RulesEngine`, `Database`, `ScanRepository` | `app/rules/` |
| [Mayssaa] | AI Coach | `PromptBuilder`, `CoachAdvice`, `BaseCoach`, `OfflineCoach`, `OpenAICoach`, `CoachService` | `app/coach/` |
| [Divya] | Dashboard | `ScanAnalytics`, `TrendCalculator`, `ChartBuilder`, `DashboardService` | `app/dashboard/` |


## 2. System Design

### 2.1 Overall flow

```mermaid
flowchart TD
    U[User uploads an item photo]

    U --> P[Image Preprocessor]
    P --> CS[Classifier Service]
    CS --> B[Classifier Backend]
    B --> CR[Classification Result]

    CR --> RE[Rules Engine]
    RS[Rule Set] --> RE
    RE --> D[Waste Disposal Decision]

    D --> CO[AI Coach Service]
    CO --> CA[Coach Advice]

    D --> SR[Scan Recorder]
    SR --> DB[(Database)]

    DB --> REP[Scan Repository]
    REP --> DS[Dashboard Service]

    DS --> SA[Scan Analytics]
    DS --> TC[Trend Calculator]
    DS --> CB[Chart Builder]

    CA --> OUTPUT[Application Response]
    D --> OUTPUT
    CB --> OUTPUT
```

### 2.2 Classifier subsystem

```mermaid
classDiagram
    class BaseClassifier {
        <<abstract>>
        -name
        -ready
        +name
        +is_ready
        +ensure_ready()
        +initialize()*
        +predict(image)*
    }

    class HuggingFaceClassifier {
        -top_k
        +initialize()
        +predict(image)
    }

    class ClipZeroShotClassifier {
        +initialize()
        +predict(image)
    }

    class SigLIP2Classifier {
        +initialize()
        +predict(image)
    }

    class ClassificationResult {
        -label
        -confidence
        -material
        +label
        +confidence
        +material
        +to_dict()
    }

    class ImagePreprocessor {
        -max_bytes
        -max_side
        +initialize()
        +prepare(data)
    }

    class ClassifierService {
        -backend
        -preprocessor
        -min_confidence
        +backend
        +min_confidence
        +build_pipeline()
        +classify(data)
    }

    class WasteImage {
        -image_path
        +get_image_path()
        +set_image_path(image_path)
        +load_image()
    }

    class PredictionResult {
        -label
        -confidence
        +get_label()
        +set_label(label)
        +get_confidence()
        +set_confidence(confidence)
    }

    class WasteClassifier {
        -model_name
        -processor
        -model
        +get_model_name()
        +set_model_name(model_name)
        +initialize_model()
        +classify(waste_image)
    }

    class ModelEvaluator {
        -actual_labels
        -predicted_labels
        +get_actual_labels()
        +set_actual_labels(labels)
        +get_predicted_labels()
        +set_predicted_labels(labels)
        +add_prediction(actual_label, predicted_label)
        +reset()
        +evaluate()
    }

    BaseClassifier <|-- HuggingFaceClassifier
    BaseClassifier <|-- ClipZeroShotClassifier
    BaseClassifier <|-- SigLIP2Classifier

    ClassifierService --> BaseClassifier : uses backend
    ClassifierService --> ImagePreprocessor : preprocesses images
    ClassifierService ..> ClassificationResult : produces results

    SigLIP2Classifier ..> WasteClassifier : delegates classification to
    WasteClassifier --> WasteImage : receives image
    WasteClassifier ..> PredictionResult : creates result

    ModelEvaluator ..> PredictionResult : evaluates label values
```

### 2.3 Rules and Database subsystem

```mermaid
classDiagram
    class Rule {
        -material
        -bin_name
        -recyclable
        -instructions
        +material
        +bin_name
        +recyclable
        +instructions
    }

    class RuleSet {
        -region
        -rules
        +region
        +load_defaults()
        +add_rule(rule)
        +get_rule(material)
        +materials()
    }

    class Decision {
        +label
        +confidence
        +rule
        +region
        +material
        +bin_name
        +recyclable
        +instructions
        +to_dict()
    }

    class RulesEngine {
        -ruleset
        +ruleset
        +region
        +decide(result)
    }

    class Database {
        -url
        -engine
        -sessions
        +url
        +initialize()
        +create_tables()
        +session()
    }

    class Scan {
        +id
        +created_at
        +label
        +material
        +bin_name
        +recyclable
        +confidence
        +region
        +to_dict()
    }

    class ScanRepository {
        -db
        +database
        +add(decision)
        +list_scans(region)
        +count()
    }

    class RoutedDecision {
        -decision
        -lane_code
        +decision
        +lane_code
        +to_dict()
    }

    class DecisionMapper {
        -engine
        +engine
        +process(stream)
    }

    class RoutingCodeAssigner {
        -codes
        -fallback
        +codes
        +fallback
        +initialize(codes, fallback)
        +code_for(material)
        +process(stream)
    }

    class ScanRecorder {
        -repository
        +repository
        +process(stream)
    }

    RuleSet o-- Rule : contains rules
    RulesEngine --> RuleSet : uses
    RulesEngine ..> Decision : creates
    Decision --> Rule : contains selected rule

    ScanRepository --> Database : uses
    ScanRepository ..> Scan : stores and retrieves
    ScanRepository ..> Decision : stores decision data

    DecisionMapper --> RulesEngine : uses
    DecisionMapper ..> RoutedDecision : creates
    RoutingCodeAssigner ..> RoutedDecision : assigns routing code
    ScanRecorder --> ScanRepository : records decisions
```

### 2.4 AI Coach subsystem

```mermaid
classDiagram
    class CoachAdvice {
        +headline
        +tips
        +fun_fact
        +source
        +to_dict()
    }

    class PromptBuilder {
        -region
        -language
        +region
        +language
        +build(decision)
    }

    class BaseCoach {
        <<abstract>>
        -prompts
        +prompts
        +advise(decision)*
    }

    class OfflineCoach {
        +FACTS
        +advise(decision)
    }

    class OpenAICoach {
        -api_key
        -model
        +model
        +advise(decision)
    }

    class CoachService {
        -primary
        -fallback
        +primary
        +advise(decision)
    }

    BaseCoach <|-- OfflineCoach
    BaseCoach <|-- OpenAICoach

    BaseCoach --> PromptBuilder : uses
    CoachService --> BaseCoach : primary coach
    CoachService --> BaseCoach : fallback coach

    OfflineCoach ..> CoachAdvice : creates
    OpenAICoach ..> CoachAdvice : creates
```


### 2.5 Dashboard subsystem

```mermaid
classDiagram
    class ScanAnalytics {
        -scans
        +scans
        +initialize()
        +total()
        +recycling_rate()
        +average_confidence()
        +count_by(attribute)
        +daily_counts(days, today)
    }

    class TrendCalculator {
        -tolerance
        +tolerance
        +initialize()
        +direction(series)
    }

    class ChartBuilder {
        -default_color
        -palette
        +default_color
        +palette
        +initialize()
        +material_chart(counts)
        +bin_chart(counts)
        +trend_chart(daily)
    }

    class DashboardService {
        -repository
        -region
        -days
        +repository
        +region
        +days
        +initialize()
        +build(today)
    }

    class ScanRepository {
        +list_scans(region)
    }

    DashboardService --> ScanRepository : reads scan records
    DashboardService ..> ScanAnalytics : creates
    DashboardService ..> TrendCalculator : initializes and uses
    DashboardService ..> ChartBuilder : initializes and uses
```

## Run it 

## How to run

### Option A: Docker 

**Requirements:** Docker Desktop (running) and Git. Internet is needed on the first start, because the classifier model is downloaded.

```powershell
git clone https://github.com/DIVYA-1527/Capstone-Project.git](https://github.com/Mayssaa24/Capstone_Project/tree/main/waste_sorting
cd Capstone-Project
docker compose up --build
```

Open **http://localhost:5000**. The first start takes a few minutes.

Docker starts two containers: a MySQL 8 database (`db`) and the Flask app (`web`). The app waits until the database is ready, and the tables are created automatically on start. No `.env` file and no manual database setup are needed.

To stop: press `Ctrl+C`, then run `docker compose down`. To also delete the database data, run `docker compose down -v`.

**AI coach with KI:connect (optional).** Without a key, the coach automatically uses the offline tips. To use KI:connect:

```powershell
copy .env.example .env
```

Enter your key in `.env` (`KICONNECT_API_KEY=...`) and run `docker compose up --build` again.

The database credentials in `docker-compose.yaml` are demo values for the local Docker setup only.

### Tests

Run the tests in a temporary container (the app doesn't need to be running):

```powershell
docker compose run --rm web python -m pytest -v
```

If the app is already running in the background (`docker compose up -d`), you can also use:

```powershell
docker compose exec web python -m pytest -v
```

Tests by category and with coverage:

```powershell
docker compose run --rm web python -m pytest -m unit -v
docker compose run --rm web python -m pytest -m integration -v
docker compose run --rm web python -m pytest -m functional -v
docker compose run --rm web python -m pytest -m regression -v
docker compose run --rm web python -m pytest --cov=app --cov-report=term-missing
```

### Without Docker

Use the commands below from the project folder, with the virtual environment active.

### Option B: Run locally without Docker (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# then edit DATABASE_URL and KICONNECT_API_KEY in .env
python run.py               # http://127.0.0.1:5000
```

**MySQL:** run `CREATE DATABASE waste_sorting CHARACTER SET utf8mb4;`, create a user, and set `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/waste_sorting`. Tables are created on start. For a quick test without MySQL you can use SQLite: `DATABASE_URL=sqlite:///waste_sorting.db`.

Without `KICONNECT_API_KEY` the coach automatically uses the offline tips. Backends: `clip` (default), `huggingface`, `siglip2` (set `CLASSIFIER_BACKEND`). The tests use stubs, so they need no model download and no network.

The default backend is `clip` (Hugging Face `openai/clip-vit-base-patch32`, zero-shot, 9 waste descriptions). `huggingface` uses `HF_MODEL`. If `torch` has no wheel for your Python version yet, create the venv with Python 3.12 or 3.13.

Optional: drop your own `app/static/background.jpg` for the page background. Camera access in browsers needs `localhost` or HTTPS.

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
