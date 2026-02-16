# Commons Depicts Analyzer

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Analyze Wikimedia Commons categories for [depicts (P180)](https://www.wikidata.org/wiki/Property:P180) metadata coverage.**

[Overview](#overview) • [Features](#features) • [Installation](#installation) • [Security](#security) • [API Reference](#api-reference)

</div>

---

## Overview

Structured metadata is critical for the discoverability and reusability of media on Wikimedia Commons. The **Commons Depicts Analyzer** is a specialized tool designed to audit files within a specific category, identifying those that lack "depicts" (P180) statements. It provides a robust backend for data retrieval and analysis, coupled with an interactive frontend for visualization and reporting.

This application is built with a focus on **data integrity**, **user privacy**, and **security**, employing production-grade authentication and session management standards.

---

## Features

- **Categorical Analysis**: Systematically fetches and audits all files within a specified Commons category.
- **Coverage Visualization**: Real-time statistical analysis of metadata coverage with interactive charts.
- **OAuth 2.0 Authentication**: Secure integration with Wikimedia accounts for authenticated operations.
- **Suggestions Engine**: Suggests relevant Wikidata items for files based on title analysis and context.
- **Interactive Dashboard**: Sortable and filterable results interfaces with pagination support.
- **Progress Tracking**: Real-time progress monitoring with job cancellation support for long-running analyses.
- **Export Capabilities**: Export analysis results in CSV or JSON formats for further processing.
- **Customizable Interface**: Adjustable text size, width, and color themes (including dark mode - beta).
- **Responsive Design**: Mobile-friendly interface optimized for various screen sizes.
- **Batch Operations**: Add depicts statements to multiple files efficiently.

---

## Architecture

The application follows a modular architecture:

### Backend
- **Core**: Python 3.8+ with Flask.
- **Security**: Server-side session management (`Flask-Session`), CSRF protection, and strictly enforced rate limiting (`Flask-Limiter`).
- **Database**: SQLite for lightweight, reliable data persistence with connection pooling for improved performance.
- **Performance**: Multi-threaded batch processing using `ThreadPoolExecutor` for efficient parallel operations.
- **API Integration**: Direct interaction with MediaWiki and Wikidata APIs.

### Frontend
- **Framework**: Semantic HTML5 and CSS3 (custom design system).
- **Interactivity**: Vanilla JavaScript (ES6+) for performant client-side logic.
- **Visualization**: Chart.js for interactive statistical charts and graphs.
- **Design**: Wikipedia-inspired aesthetic with high contrast and accessibility focus.

---

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- A Wikimedia account (for OAuth configuration)

### Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/mfscpayload-690/commons-depicts-analyzer.git
   cd commons-depicts-analyzer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure OAuth (Required for editing features)**
   
   **Option A: Automated Setup (Recommended)**
   ```bash
   python setup_oauth.py
   ```
   The script will guide you through:
   - Registering an OAuth application with Wikimedia
   - Setting your Client ID and Secret
   - Generating a secure Flask secret key
   - Creating your `.env` file automatically

   **Option B: Manual Setup**
   
   a. Register an OAuth application:
      - Visit: https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose/oauth2
      - Application name: `Commons Depicts Analyzer (Development)`
      - Callback URL: `http://localhost:5000/auth/callback`
      - Grants: Check **"Basic rights"** and **"Edit structured data"**
      - Copy your **Client ID** and **Client Secret**
   
   b. Create a `.env` file in the project root:
      ```bash
      cp .env.example .env
      ```
   
   c. Edit `.env` and add your credentials:
      ```env
      OAUTH_CLIENT_ID=your_client_id_here
      OAUTH_CLIENT_SECRET=your_client_secret_here
      OAUTH_CALLBACK_URL=http://localhost:5000/auth/callback
      FLASK_SECRET_KEY=your_generated_secret_key_here
      ```
      
      Generate a Flask secret key:
      ```bash
      python -c "import secrets; print(secrets.token_hex(32))"
      ```

4. **Run the application**
   ```bash
   python backend/main.py
   ```

The application will be accessible at `http://localhost:5000`.

> **Note**: OAuth is only required if you want to **add depicts statements** through the UI. The analysis features work without OAuth.

---

## Security

This project adheres to strict security standards to protect user data and maintain service integrity.

### Authentication & Sessions
- **Server-Side Sessions**: User sessions are stored securely on the server filesystem, not in client-side cookies.
- **OAuth 2.0**: Standard flow for secure third-party authentication with Wikimedia.
- **Token Handling**: Access tokens are encrypted and handled exclusively by the backend.

### Protection Measures
- **Rate Limiting**: API endpoints are protected against abuse using token bucket algorithms.
- **CSRF Protection**: State-changing requests require cryptographic tokens (Double Submit Cookie pattern).
- **Input Sanitization**: All user inputs are strictly validated against whitelists to prevent injection attacks.
- **Security Headers**: Responses include strictly configured CSP, HSTS, and X-Frame-Options headers.

---

## API Reference

The backend exposes a RESTful API for automation and integration.

### Core Endpoints

| Method | Endpoint                  | Description                                          |
| :----- | :------------------------ | :--------------------------------------------------- |
| `POST` | `/api/analyze`            | Initiates analysis for a specific category.          |
| `GET`  | `/api/results/<category>` | Retrieves cached analysis results.                   |
| `GET`  | `/api/history`            | Lists all previously analyzed categories.            |
| `POST` | `/api/add-depicts`        | **(Auth Required)** Adds a P180 statement to a file. |

### Progress & Job Management

| Method | Endpoint                 | Description                                      |
| :----- | :----------------------- | :----------------------------------------------- |
| `GET`  | `/api/progress/<job_id>` | Get progress status of a background analysis job.|
| `POST` | `/api/cancel/<job_id>`   | Cancel a currently running analysis job.         |

### Category & File Operations

| Method   | Endpoint                       | Description                                         |
| :------- | :----------------------------- | :-------------------------------------------------- |
| `GET`    | `/api/suggest`                 | Suggest Commons categories by prefix (autocomplete).|
| `GET`    | `/api/verify/<category>`       | Verify if a category exists on Wikimedia Commons.   |
| `DELETE` | `/api/category/<category>`     | Delete cached analysis data for a category.         |
| `GET`    | `/api/export/<category>`       | Export analysis results in CSV format.              |
| `GET`    | `/api/fileinfo/<file_title>`   | Get detailed information about a specific file.     |
| `GET`    | `/api/suggests/<file_title>`   | Get Wikidata item suggestions for a specific file.  |

### Authentication Endpoints

| Method | Endpoint       | Description                                            |
| :----- | :------------- | :----------------------------------------------------- |
| `GET`  | `/auth/status` | Returns current authentication state and user context. |
| `GET`  | `/auth/login`  | Initiates the OAuth handshake.                         |
| `GET`  | `/auth/logout` | Terminates the session and revokes tokens.             |

---

## Contributing

Contributions are welcome. Please ensure that any pull requests verify against the security test suite before submission.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/SecureFeature`)
3. Commit your changes (`git commit -m 'feat: Add SecureFeature'`)
4. Push to the branch (`git push origin feature/SecureFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

Developed for the **Wikimedia Technical Workshop at THARANG 2K26**.

### Development Team

| Name            | Role           | GitHub                                                     |
| :-------------- | :------------- | :--------------------------------------------------------- |
| **Aravind Lal** | Core Developer | [@mfscpayload-690](https://github.com/mfscpayload-690)     |
| **Abhishek H**  | Core Developer | [@unknownguyoffline](https://github.com/unknownguyoffline) |

### Documentation

| Name               | Role          | GitHub                                               |
| :----------------- | :------------ | :--------------------------------------------------- |
| **Aaromal V**      | Documentation | [@Aaromal665](https://github.com/Aaromal665)         |
| **Sreeram S Nair** | Documentation | [@SreeramSNair-7](https://github.com/SreeramSNair-7) |
