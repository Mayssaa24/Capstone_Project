# AI-Powered Waste Sorting Assistant

Home Assignment 1: translating the capstone UML architecture into Object-Oriented Python classes.

A user takes a photo of an item. An AI model classifies the material, local rules (Dortmund) decide which bin it belongs in, an AI coach gives tips, and a dashboard shows recycling statistics.

---

## 1. Team Overview

| Team member | Subsystem | Implemented classes | Source files |
|---|---|---|---|
| [Manjeet] | Classifier | `WasteImage`, `PredictionResult`, `WasteClassifier`, `ModelEvaluator` | `app/classifier/classifier_oop.py` |
| [Deepika] | Rules and Database | `Rule`, `RuleSet`, `Decision`, `RulesEngine`, `Database`, `ScanRepository` | `app/rules/` |
| [Mayssaa] | AI Coach | `PromptBuilder`, `CoachAdvice`, `BaseCoach`, `OfflineCoach`, `OpenAICoach`, `CoachService` | `app/coach/` |
| [Divya] | Dashboard | `ScanAnalytics`, `TrendCalculator`, `ChartBuilder`, `DashboardService` | `app/dashboard/` |

Every class has:

1. **A constructor** (`__init__`) that initialises its state and validates its input.
2. **Initialisation methods** where setup logic applies (for example `WasteClassifier.initialize_model()`, `RuleSet.load_defaults()`, `Database.initialize()`, `ScanAnalytics.initialize()`).
3. **Encapsulation**: private attributes exposed through getters and setters, with validation in the setters. The Classifier classes use explicit `get_...()` / `set_...()` methods; the other subsystems use Python `@property` and `@<name>.setter`.

---

## 2. System Design

### 2.1 Overall flow

```mermaid
flowchart LR
    U[User photo] --> C[Classifier]
    C -->|ClassificationResult| R[Rules and Database]
    R -->|Decision| A[AI Coach]
    R -->|stored scans| D[Dashboard]
    A -->|CoachAdvice| O[JSON response]
    R --> O
    D --> O
```

### 2.2 Classifier subsystem

```mermaid
classDiagram
    class WasteImage {
        -image_path Path
        +get_image_path() str
        +set_image_path(image_path)
        +load_image() Image
    }
    class PredictionResult {
        -label str
        -confidence float
        +get_label() str
        +set_label(label)
        +get_confidence() float
        +set_confidence(confidence)
    }
    class WasteClassifier {
        -model_name str
        -processor
        -model
        +get_model_name() str
        +set_model_name(model_name)
        +initialize_model()
        +classify(waste_image) PredictionResult
    }
    class ModelEvaluator {
        -actual_labels list
        -predicted_labels list
        +get_actual_labels() list
        +set_actual_labels(labels)
        +get_predicted_labels() list
        +set_predicted_labels(labels)
        +add_prediction(actual_label, predicted_label)
        +reset()
        +evaluate() dict
    }
    WasteClassifier ..> WasteImage : loads
    WasteClassifier ..> PredictionResult : creates
    ModelEvaluator ..> PredictionResult : compares labels from
```

### 2.3 Rules and Database subsystem

```mermaid
classDiagram
    class Rule {
        +material str
        +bin_name str
        +recyclable bool
        +instructions str
    }
    class RuleSet {
        +DEFAULTS tuple
        +region str
        +load_defaults()
        +add_rule(rule)
        +get_rule(material) Rule
        +materials() list
    }
    class Decision {
        +material str
        +bin_name str
        +recyclable bool
        +instructions str
        +to_dict() dict
    }
    class RulesEngine {
        +ruleset RuleSet
        +region str
        +decide(result) Decision
    }
    class Database {
        +url str
        +initialize()
        +create_tables()
        +session() Session
    }
    class ScanRepository {
        +database Database
        +add(decision) Scan
        +list_scans(region) list
        +count() int
    }
    class Scan {
        +id int
        +created_at datetime
        +label str
        +material str
        +bin_name str
        +region str
        +to_dict() dict
    }
    RuleSet o-- Rule : contains
    RulesEngine o-- RuleSet : uses
    RulesEngine ..> Decision : creates
    Decision --> Rule : based on
    ScanRepository o-- Database : uses
    ScanRepository ..> Scan : stores
    ScanRepository ..> Decision : saves
```

### 2.4 AI Coach subsystem

```mermaid
classDiagram
    class PromptBuilder {
        +region str
        +language str
        +build(decision) str
    }
    class CoachAdvice {
        +headline str
        +tips list
        +fun_fact str
        +source str
        +to_dict() dict
    }
    class BaseCoach {
        <<abstract>>
        +prompts PromptBuilder
        +advise(decision)* CoachAdvice
    }
    class OfflineCoach {
        +FACTS dict
        +advise(decision) CoachAdvice
    }
    class OpenAICoach {
        +model str
        +advise(decision) CoachAdvice
    }
    class CoachService {
        +primary BaseCoach
        +advise(decision) CoachAdvice
    }
    BaseCoach <|-- OfflineCoach
    BaseCoach <|-- OpenAICoach
    BaseCoach o-- PromptBuilder : uses
    CoachService o-- BaseCoach : primary
    CoachService o-- OfflineCoach : fallback
    BaseCoach ..> CoachAdvice : returns
```

### 2.5 Dashboard subsystem

```mermaid
classDiagram
    class ScanAnalytics {
        +scans list
        +initialize()
        +total() int
        +recycling_rate() float
        +average_confidence() float
        +count_by(attribute) dict
        +daily_counts(days, today) list
    }
    class TrendCalculator {
        +tolerance float
        +initialize()
        +direction(series) str
    }
    class ChartBuilder {
        +default_color str
        +palette dict
        +initialize()
        +material_chart(counts) dict
        +bin_chart(counts) dict
        +trend_chart(daily) dict
    }
    class DashboardService {
        +repository ScanRepository
        +region str
        +days int
        +initialize()
        +build(today) dict
    }
    class ScanRepository {
        <<interface>>
        +list_scans(region) list
    }
    DashboardService o-- ScanAnalytics : creates
    DashboardService o-- TrendCalculator : uses
    DashboardService o-- ChartBuilder : uses
    DashboardService --> ScanRepository : reads scans
```

---

## 3. Presentation Link



## Setup and run

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Open http://127.0.0.1:5000 in a browser.
