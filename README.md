# Salesforce + Tubular Merge Tool

This tool merges Salesforce opportunity exports with Tubular CSV exports using **YouTube channel ID** as the join key.  
It does **not** require the Tubular API — just CSV exports.

## Setup

```bash
git clone https://github.com/YOUR_ORG/sf-tubular-merge.git
cd sf-tubular-merge
pip install -r requirements.txt
```

## Input Files

- **opps.csv**: Salesforce export (include Account.Name, etc.)
- **tubular.csv**: Tubular export (include channel_id + metrics)
- **channel_map.csv**: Optional map if opps lacks channel_id

## Usage

```bash
python merge_no_api.py --opps opps.csv --metrics tubular.csv --out merged.csv
```

With map:

```bash
python merge_no_api.py --opps opps.csv --map channel_map.csv --metrics tubular.csv --out merged.csv
```

With custom header mapping:

```bash
python merge_no_api.py --opps opps.csv --map channel_map.csv --metrics tubular.csv --metrics-cols channel_id:Channel ID,views_30d:Views (30d),audience_size:Subscribers --out merged.csv
```

## Interactive UI

Launch the Streamlit workspace to upload CSV exports and download the merged output without
using the command line:

```bash
streamlit run streamlit_app.py
```

The app previews your inputs, highlights how many opportunities matched Tubular data, and lets
you download the merged CSV directly from the browser.

## Output

Produces **merged.csv** with Salesforce Opps + Tubular metrics.
