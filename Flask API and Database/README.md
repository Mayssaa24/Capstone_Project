# AI-Powered Waste Sorting Assistant (Flask + SQLite/MySQL)

A simple Flask web application that identifies a waste item from an uploaded photo, tells the user which bin it belongs in, and stores every scan in a SQLite/MySQL database. A dashboard page reads the stored scans back from SQLite/MySQL and shows them as charts.

**GitHub repository:** https://github.com/Mayssaa24/Capstone_Project/tree/Homeassignment003

## 1. Team Overview 
## Team and Responsibilities

| Name | Overall role | 1. OOP classes | 2. Stream processing | 3. Flask and SQLite/MySQL | 4. Errors and tests |
|---|---|---|---|---|---|
| **Manjeet (Classifier)** | Identifies the item in the uploaded photo using a Hugging Face model. | Classes that check the photo and run the model behind one interface (`ImagePreprocessor`, `BaseClassifier`, `ClassifierService`). | Pipeline that drops unsure results, maps labels to materials and keeps the best few (`ConfidenceFilter` \| `LabelNormalizer` \| `TopKLimiter`). | Photo upload route `/api/scan`: validates the image, runs the model, returns the result. | Error classes and handler for bad images and model failures; 57 tests. |
| **Deepika (Rules and Database)** | Decides which bin the item goes in and stores every scan. | Classes for the recycling rules and for saving scans (`RuleSet`, `RulesEngine`, `Database`, `ScanRepository`). | Pipeline that turns results into decisions, adds a lane code and saves them (`DecisionMapper` \| `RoutingCodeAssigner` \| `ScanRecorder`). | SQLAlchemy models and the SQLite/MySQL connection that save and read scans. | Error classes and handlers for invalid rules and database failures; 43 tests. |
| **Divya (Dashboard)** | Turns saved scans into charts and trends, and built the single page. | Classes that calculate the statistics and build the chart data (`ScanAnalytics`, `ChartBuilder`, `DashboardService`). | Pipeline that filters scans by region and date and counts them per day (`RegionFilter` \| `DateRangeFilter` \| `DailyAggregator`). | `/api/dashboard` route and the single page with the photo buttons and charts. | Error class and handler for the dashboard; 35 tests. |
| **Mayassa (AI Coach)** | Writes the tips and fun fact, with offline tips if the AI is down. | Classes that ask the AI for advice or use offline tips (`PromptBuilder`, `OpenAICoach`, `OfflineCoach`, `CoachService`). | Pipeline that builds the prompt, gets advice and cleans the tips (`PromptStage` \| `AdviceStage` \| `TipCleaner` \| `TipLimiter`). | Connects the KI:connect AI to the scan response, with an offline fallback. | Error class and handler for an unavailable AI, plus the fallback; 40 tests. |

**Shared by everyone:** Connecting the four subsystems, the shared error structure, the README, the UML diagrams and the video.


## What the project does

1. The user uploads a photo on the web page.
2. The Flask route `/api/scan` validates the image and classifies it.
3. The result (item, material, bin, region, confidence) is saved to the SQLite/MySQL table `scans`.
4. The route `/api/dashboard` reads the saved scans from SQLite/MySQL and returns totals, charts and the most recent scans, which the page displays.

## Technologies

- Python 3.10+
- Flask (web framework and routes)
- SQLite/MySQL with SQLAlchemy(Database Access Layer)and the PyMySQL driver
- Hugging Face model for the image classification
- HTML, CSS and JavaScript for the single page
  
## Database

The `scans` table is created automatically when the app starts.

| Column | Type | Description |
|---|---|---|
| id | integer, primary key | Scan number |
| created_at | datetime | Time of the scan (UTC) |
| label | varchar(100) | Detected item |
| material | varchar(50) | Material, for example glass |
| bin_name | varchar(100) | Bin for the region |
| recyclable | boolean | Whether it is recyclable |
| confidence | float | Model confidence |
| region | varchar(50) | Region, for example Dortmund |

The UML class diagram of the database is saved outside the "app" folder with the name:"Database_Classdiagram.png"

## Routes

| Method | Route | Description |
|---|---|---|
| GET | `/` | The single page with the upload button and charts |
| POST | `/api/scan` | Upload an image (`multipart/form-data`, field `image`); saves the scan in SQLite/MySQL and returns the result |
| GET | `/api/dashboard` | Reads the scans from SQLite and returns summary numbers, chart data and recent scans as JSON |

The UML class diagram of the routes is saved outside the "app" folder with the name:"Routes_Classdiagram.png"

## Setup from powershell:

1. Clone the repository:

   ```powershell
   git clone https://github.com/Mayssaa24/Capstone_Project/tree/main
   cd "your_repo_path_from_local_folder"/../main
   ```

2. Create a virtual environment and install the packages:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```

3. Create the MySQL database(optional):

   ```sql
   CREATE DATABASE waste_sorting CHARACTER SET utf8mb4;
   ```

4. Copy `.env.example` to `.env` and enter your own values:

   ```
   DATABASE_URL=sqlite:///waste_sorting.db #(Default) or
   DATABASE_URL=mysql+pymysql://user:password@localhost:3306/waste_sorting #(For MySQL)
   KICONNECT_API_KEY=your_key_here
   ```
   The code works with SQLite and MySQL; only theconnection URL differs. SQLite is the default because it needs no installation
   Use `mysql+pymysql://` so SQLAlchemy picks the PyMySQL driver. The API key is optional; without it the app uses offline tips.

## Run

From the project folder:

```powershell
python run.py
```

Open http://127.0.0.1:5000/ in a browser, upload a photo, then check the dashboard. The first run downloads the classifier model, so it needs internet and takes little longer.

## Check the data in SQLite

Run this from the folder that contains `waste_sorting.db`:

```powershell
sqlite3 waste_sorting.db
```

Then, at the `sqlite>` prompt:

```sql
.headers on
.mode column
SELECT * FROM scans;
.quit
```
## Check the data in MySQL
```powershell
mysql -u root -p
```

```sql
USE sorting_desk;
SELECT * FROM scans;
```
Or from the project folder, without opening SQLite/MySQL:

```powershell
python -m app.rules.database "mysql+pymysql://user:password@localhost:3306/waste_sorting"
```

## Troubleshooting

- **`No module named 'MySQLdb'`**: change `mysql://` to `mysql+pymysql://` in `DATABASE_URL`.
- **`Can't connect to MySQL server` / `Access denied`**: check that MySQL is running and that the host, port, user, password and database name are correct.
- **Dashboard shows zero scans**: upload a photo first, or check that the app and the query use the same database.

## Presentation Link
```
https://drive.google.com/file/d/16Pelz-nltjItrN1QjlgAqmban2k1fTb9/view?usp=drive_link
```
