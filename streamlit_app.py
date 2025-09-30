"""Streamlit UI for merging Salesforce opportunities with Tubular metrics."""
from typing import Optional, TYPE_CHECKING

import pandas as pd
import streamlit as st

from merge_no_api import merge_data, parse_colmap

if TYPE_CHECKING:  # pragma: no cover - only for type hints when running tests/mypy
    from streamlit.runtime.uploaded_file_manager import UploadedFile


def _read_uploaded_csv(file: "UploadedFile", label: str) -> Optional[pd.DataFrame]:
    """Load a CSV from an uploaded file object, rewinding the buffer before reading."""

    try:
        file.seek(0)
        return pd.read_csv(file)
    except pd.errors.EmptyDataError:
        st.error(f"{label} appears to be empty. Upload a CSV with data.")
    except Exception as exc:  # pragma: no cover - defensive logging for unexpected errors
        st.error(f"Couldn't read {label}: {exc}")
    return None

st.set_page_config(page_title="Salesforce + Tubular Merge", layout="wide")

st.title("Salesforce ↔ Tubular Merge Workbench")
st.markdown(
    "Use this tool to combine a Salesforce opportunity export with Tubular channel metrics."
)

with st.expander("How it works"):
    st.markdown(
        """
        1. Export your Salesforce opportunities as CSV (include **Account.Name** and, if possible, the
           YouTube channel ID field).
        2. Export the relevant Tubular metrics as CSV. Make sure there is a **channel_id** column or
           provide the mapping in the *Metrics header mapping* field below.
        3. (Optional) Upload a channel map when the opportunity file does not contain a channel ID.
        4. Click **Merge data** to preview and download the combined dataset.
        """
    )

opps_file = st.file_uploader("Salesforce opportunities CSV", type="csv", key="opps")
map_file = st.file_uploader(
    "Channel map CSV (optional)",
    type="csv",
    help="Use when your opportunities do not include a channel_id column. Must contain account_name, channel_id.",
)
metrics_file = st.file_uploader("Tubular metrics CSV", type="csv", key="metrics")

metrics_mapping = st.text_input(
    "Metrics header mapping (optional)",
    value="",
    placeholder="channel_id:Channel ID,views_30d:Views (30d),audience_size:Subscribers",
    help="Provide comma-separated pairs of expected_header:your_csv_header when Tubular columns use different labels.",
)

preview_toggle = st.checkbox("Show input previews", value=False)

opps_df: Optional[pd.DataFrame] = None
map_df: Optional[pd.DataFrame] = None
metrics_df: Optional[pd.DataFrame] = None
colmap = None

if opps_file is not None:
    opps_df = _read_uploaded_csv(opps_file, "Salesforce opportunities CSV")
    if preview_toggle and opps_df is not None:
        st.caption("Opportunities preview")
        st.dataframe(opps_df.head())

if map_file is not None:
    map_df = _read_uploaded_csv(map_file, "Channel map CSV")
    if preview_toggle and map_df is not None:
        st.caption("Channel map preview")
        st.dataframe(map_df.head())

if metrics_file is not None:
    metrics_df = _read_uploaded_csv(metrics_file, "Tubular metrics CSV")
    if preview_toggle and metrics_df is not None:
        st.caption("Tubular metrics preview")
        st.dataframe(metrics_df.head())

if metrics_mapping:
    try:
        colmap = parse_colmap(metrics_mapping)
    except ValueError as exc:
        st.error(str(exc))
        colmap = None

merge_button_disabled = opps_df is None or metrics_df is None or (metrics_mapping and colmap is None)

merge_clicked = st.button("Merge data", disabled=merge_button_disabled)

if merge_clicked:
    if opps_df is None or metrics_df is None:
        st.error("Upload both the Salesforce opportunities file and the Tubular metrics file.")
    else:
        try:
            merged = merge_data(opps_df, metrics_df, map_df=map_df, metrics_colmap=colmap)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(
                f"Merged {len(merged)} opportunities using channel column "
                f"`{merged.attrs.get('channel_column', 'channel_id')}`."
            )

            metrics_missing = merged["channel_name"].isna().sum() if "channel_name" in merged.columns else 0
            map_used = merged.attrs.get("map_used", False)

            info_cols = st.columns(3)
            info_cols[0].metric("Total rows", len(merged))
            info_cols[1].metric("Missing Tubular matches", metrics_missing)
            info_cols[2].metric("Used channel map", "Yes" if map_used else "No")

            st.dataframe(merged.head(100))

            csv_bytes = merged.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download merged CSV",
                data=csv_bytes,
                file_name="merged.csv",
                mime="text/csv",
            )
