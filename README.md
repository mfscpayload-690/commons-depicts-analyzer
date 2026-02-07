# Wikimedia Commons Depicts Analyzer

This project analyzes Wikimedia Commons categories to identify depicts (P180) metadata and highlight files that are missing depicts information.

## Overview
Wikimedia Commons files often lack structured depicts metadata, which affects discoverability and data quality.  
This tool retrieves files from a Commons category, checks for depicts (P180) statements, stores the results, and presents useful statistics.

## Features
- Fetch files from a Wikimedia Commons category
- Detect depicts (P180) metadata using MediaWiki APIs
- Store results in a local SQLite database
- List files with and without depicts metadata
- Provide summary statistics for metadata completeness

## Tech Stack
- Backend: Python
- Database: SQLite
- Frontend: HTML, CSS, JavaScript
- APIs: MediaWiki Commons API, Wikidata

## Status
This project is under active development as part of the Wikimedia Technical Workshop at THARANG 2K26.

## License
MIT License
