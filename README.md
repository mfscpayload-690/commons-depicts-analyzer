# Wikimedia Commons Depicts Analyzer

Analyze Wikimedia Commons categories to identify files with and without [depicts (P180)](https://www.wikidata.org/wiki/Property:P180) metadata.

## Overview

Many Wikimedia Commons files lack structured depicts metadata, which affects discoverability and data quality. This tool:

- Fetches all files from a Commons category
- Checks each file for P180 (depicts) statements
- Stores results in a local SQLite database
- Provides statistics and file listings via a web interface

## Quick Start

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/commons-depicts-analyzer.git
cd commons-depicts-analyzer

# Install dependencies
pip install -r requirements.txt

# Start the server
cd backend
python main.py
```

Open <http://localhost:5000> in your browser.

### CLI Usage

```bash
python backend/main.py --category "Category:Example Category"

# Output as JSON
python backend/main.py --category "Category:Example Category" --json
```

## Project Structure

```
commons-depicts-analyzer/
├── backend/
│   ├── main.py          # Flask server + CLI
│   ├── api.py           # MediaWiki API functions
│   └── database.py      # SQLite operations
├── frontend/
│   ├── index.html       # Web interface
│   ├── style.css        # Wikipedia-style styling
│   └── script.js        # Frontend logic
├── data/
│   └── depicts.db       # SQLite database (auto-created)
├── requirements.txt
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Analyze a category. Body: `{"category": "..."}` |
| GET | `/api/results/<category>` | Get cached results for a category |

## Tech Stack

- **Backend**: Python 3, Flask, requests
- **Database**: SQLite
- **Frontend**: HTML, CSS, vanilla JavaScript
- **APIs**: MediaWiki Commons API, Wikidata API

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

Built for the **Wikimedia Technical Workshop at THARANG 2K26**.
