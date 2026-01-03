import os
import io
import requests
import pandas as pd


def load_dataframe_from_path(path: str) -> pd.DataFrame:
    """
    Load a pandas DataFrame from a local file path or a remote HTTP(S) URL.

    The function supports CSV and Excel files. Remote URLs are always treated
    as CSV files. Local files are loaded based on their file extension.

    - CSV files are read using UTF-8 with BOM support.
    - Excel files (.xls, .xlsx) are read using the openpyxl engine.
    - All NaN values are converted to None for downstream compatibility.

    Args:
        path (str): Local filesystem path or HTTP(S) URL to a CSV or Excel file.

    Returns:
        pd.DataFrame: Loaded DataFrame with NaN values replaced by None.

    Raises:
        FileNotFoundError: If the local file path does not exist.
        ValueError: If the file extension is not supported.
        requests.HTTPError: If the HTTP request fails.
        pandas.errors.ParserError: If the file content cannot be parsed.
    """
    if path.startswith("http://") or path.startswith("https://"):
        resp = requests.get(path)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), encoding="utf-8-sig")
    else:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        if path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(path, engine="openpyxl")
        elif path.lower().endswith(".csv"):
            df = pd.read_csv(path, encoding="utf-8-sig")
        else:
            raise ValueError("Unsupported file type")
    df = df.where(pd.notnull(df), None)
    return df
