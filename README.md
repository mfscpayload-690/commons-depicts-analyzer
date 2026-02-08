# 📊 Commons Depicts Analyzer

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Analyze Wikimedia Commons categories for [depicts (P180)](https://www.wikidata.org/wiki/Property:P180) metadata coverage**

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [API Reference](#api-reference) • [Tech Stack](#tech-stack)

</div>

---

## 📋 Overview

Many Wikimedia Commons files lack structured **depicts (P180)** metadata, which affects discoverability and data quality. This tool helps identify coverage gaps by:

- 🔍 **Fetching** all files from a Commons category
- ✅ **Checking** each file for P180 (depicts) statements  
- 💾 **Storing** results in a local SQLite database
- 📊 **Visualizing** statistics through an interactive web interface

---

## ✨ Features

| Feature               | Description                                                   |
| --------------------- | ------------------------------------------------------------- |
| **Web Interface**     | Clean, Wikipedia-inspired UI with real-time progress updates  |
| **History Dashboard** | View all previously analyzed categories with coverage stats   |
| **Filter & Sort**     | Search, sort by name/coverage/files, filter by coverage level |
| **Dark Mode**         | Wikimedia-style appearance settings with dark theme support   |
| **CLI Mode**          | Command-line interface for scripting and automation           |
| **API Retry Logic**   | Automatic retry with exponential backoff for reliability      |
| **Rate Limiting**     | Built-in request throttling to respect API limits             |

---

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/mfscpayload-690/commons-depicts-analyzer.git
cd commons-depicts-analyzer

# Install dependencies
pip install -r requirements.txt

# Start the server
cd backend
python main.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 💻 Usage

### Web Interface

1. Navigate to `http://localhost:5000`
2. Enter a Commons category name (e.g., "Files from Wiki Loves Earth 2024")
3. Click **Analyze** to start the analysis
4. View results with coverage statistics and file listings
5. Use the **History Dashboard** to view previous analyses

### Command Line

```bash
# Basic analysis
python backend/main.py --category "Category:Cats"

# Output as JSON
python backend/main.py --category "Category:Cats" --json
```

---

## 📡 API Reference

### Endpoints

| Method   | Endpoint                   | Description                     |
| -------- | -------------------------- | ------------------------------- |
| `POST`   | `/api/analyze`             | Analyze a category              |
| `GET`    | `/api/results/<category>`  | Get cached results              |
| `GET`    | `/api/history`             | List all analyzed categories    |
| `GET`    | `/api/verify/<category>`   | Verify database records         |
| `DELETE` | `/api/category/<category>` | Delete a category from database |

### Example Request

```bash
# Analyze a category
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"category": "Category:Cats"}'

# Get history
curl http://localhost:5000/api/history
```

### Response Format

```json
{
  "category": "Category:Cats",
  "statistics": {
    "total": 150,
    "with_depicts": 82,
    "without_depicts": 68,
    "coverage_percent": 54.67
  },
  "files": [...]
}
```

---

## 🏗️ Project Structure

```
commons-depicts-analyzer/
├── backend/
│   ├── main.py          # Flask server + CLI entry point
│   ├── api.py           # Wikimedia API interactions
│   ├── database.py      # SQLite database operations
│   └── check_db.py      # Database verification utility
├── frontend/
│   ├── index.html       # Web interface
│   ├── style.css        # Wikipedia-inspired styling
│   └── script.js        # Frontend logic
├── data/
│   └── depicts.db       # SQLite database (auto-created)
├── requirements.txt     # Python dependencies
└── README.md
```

---

## 🛠️ Tech Stack

| Layer        | Technology                          |
| ------------ | ----------------------------------- |
| **Backend**  | Python 3, Flask, Flask-CORS         |
| **Database** | SQLite                              |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript     |
| **APIs**     | MediaWiki Commons API, Wikidata API |
| **Icons**    | Font Awesome 6                      |

---

## 🔧 Configuration

The application uses sensible defaults. Key settings in `api.py`:

| Setting            | Default | Description                    |
| ------------------ | ------- | ------------------------------ |
| `MAX_RETRIES`      | 3       | API request retry attempts     |
| `RATE_LIMIT_DELAY` | 0.1s    | Minimum delay between requests |
| `API_TIMEOUT`      | 90s     | Request timeout                |

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

<div align="center">

Built for the **Wikimedia Technical Workshop at THARANG 2K26**

[![Wikimedia Commons](https://img.shields.io/badge/Wikimedia-Commons-006699?style=flat-square&logo=wikimedia-commons)](https://commons.wikimedia.org)
[![Wikidata](https://img.shields.io/badge/Wikidata-006699?style=flat-square&logo=wikidata)](https://www.wikidata.org)

</div>

---

## 👥 Team

### Development

| Name            | Role      | GitHub                                                                                                                                  |
| --------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Aravind Lal** | Developer | [![GitHub](https://img.shields.io/badge/-mfscpayload--690-181717?style=flat-square&logo=github)](https://github.com/mfscpayload-690)    |
| **Abhishek H**  | Developer | [![GitHub](https://img.shields.io/badge/-unknownguyoffline-181717?style=flat-square&logo=github)](https://github.com/unknownguyoffline) |

### Ideation & Documentation

| Name               | Role          | GitHub                                                                                                                    |
| ------------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Aaromal V**      | Documentation | [![GitHub](https://img.shields.io/badge/-Aaromal665-181717?style=flat-square&logo=github)](https://github.com/Aaromal665) |
| **Sreeram S Nair** | Documentation | [![GitHub](https://img.shields.io/badge/-Aaromal665-181717?style=flat-square&logo=github)](https://github.com/Aaromal665) |

---

<div align="center">

**[⬆ Back to Top](#-commons-depicts-analyzer)**

</div>
