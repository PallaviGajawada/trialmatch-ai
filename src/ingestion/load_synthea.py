
from pathlib import Path
import pandas as pd


# Folder containing the Synthea CSV files
DATA_DIR = Path("data/patients/synthea")

# Required columns for the first version
REQUIRED_COLUMNS = {
    "patients.csv": ["Id", "BIRTHDATE", "GENDER"],
    "conditions.csv": ["PATIENT", "DESCRIPTION", "START"],
    "observations.csv": ["PATIENT", "DESCRIPTION", "DATE"],
}


def load_synthea_data(data_dir=DATA_DIR):
    """Load and validate the Synthea CSV files."""

    data_dir = Path(data_dir)
    data = {}

    for filename, required_columns in REQUIRED_COLUMNS.items():
        file_path = data_dir / filename

        # Check that the file exists
        if not file_path.exists():
            raise FileNotFoundError(
                f"Missing dataset file: {file_path}"
            )

        # Load the CSV file
        df = pd.read_csv(file_path)

        # Check that required columns exist
        missing_columns = [
            column for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"{filename} is missing columns: "
                f"{missing_columns}"
            )

        data[filename.replace(".csv", "")] = df

    return data


def print_data_report(data):
    """Display basic information about the loaded data."""

    for name, df in data.items():
        print(f"\n--- {name.upper()} ---")
        print("Total records:", len(df))
        print("Total columns:", len(df.columns))
        print("Missing values:", df.isnull().sum().sum())
        print("Column names:", df.columns.tolist())


if __name__ == "__main__":
    try:
        datasets = load_synthea_data()
        print("All datasets loaded successfully!")
        print_data_report(datasets)

    except (FileNotFoundError, ValueError) as error:
        print("Data loading failed:", error)
