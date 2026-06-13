# ==================================================
# PROJECT SETTINGS
# ==================================================

MODEL_NAME = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.7
TOP_RESULTS = 5

DATASET_FILE_PATH = "storage/All_Projects_Formatted.xlsx"
INPUT_JSON_FILE_PATH = "input_projects.json"
OUTPUT_JSON_FILE_PATH = "similarity_results.json"

JSON_INDENT = 2
JSON_ENSURE_ASCII = False
JSON_ENCODING = "utf-8"
PROJECTS_WRAPPER_KEY = "projects"

OUTPUT_INPUT_TEXT_KEY = "input_text"
OUTPUT_SIMILAR_PROJECTS_KEY = "similar_projects"
OUTPUT_PROJECT_KEY = "project"
OUTPUT_SCORE_KEY = "score"
OUTPUT_EXPECTED_PROJECT_KEY = "expected_project"
OUTPUT_INPUT_PROJECT_PREFIX = "Input_Project_"
SCORE_DECIMAL_PLACES = 3

PROJECT_NAME_COLUMN = "project_name"
DESCRIPTION_COLUMN = "description"
INPUT_TEXT_COLUMN = "input_text"
EXPECTED_PROJECT_COLUMN = "expected_project"
SCORE_COLUMN = "score"

PROJECT_NAME_CANDIDATES = [
    "Project Name",
    "اسم المشروع",
]

DESCRIPTION_CANDIDATES = [
    "Description",
    "وصف المشروع\n(150-200) كلمة",
]

INPUT_PROJECT_NAME_CANDIDATES = [
    "Project Name",
    "project_name",
    "project",
]

INPUT_DESCRIPTION_CANDIDATES = [
    "Description",
    "description",
]

EXPECTED_PROJECT_CANDIDATES = [
    "Expected Project",
    "expected_project",
    "expected",
]


# ==================================================
# IMPORTS
# ==================================================

import json
import logging
import os
import re
import sys

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


# ==================================================
# TEXT CLEANING FUNCTIONS
# ==================================================

def clean_text(text: str) -> str:
    """
    Clean one text value.

    Input:
        text: Any value that should be used as text.

    Output:
        A string with line breaks removed and repeated spaces reduced.
    """
    if text is None:
        value = ""
    else:
        value = str(text)

    value = value.replace("\r", " ")
    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    value = value.strip()

    return value


def build_project_text(project_name: str, description: str) -> str:
    """
    Join the project name and description into one text.
    """
    clean_project_name = clean_text(project_name)
    clean_description = clean_text(description)

    if clean_project_name and clean_description:
        text = f"{clean_project_name}. {clean_description}"
    elif clean_project_name:
        text = clean_project_name
    else:
        text = clean_description

    return text


def build_input_text_column(df: pd.DataFrame) -> list[str]:
    """
    Build the combined text column for every row in a DataFrame.
    """
    input_texts = []

    for index, row in df.iterrows():
        text = build_project_text(
            row[PROJECT_NAME_COLUMN],
            row[DESCRIPTION_COLUMN],
        )
        input_texts.append(text)

    return input_texts


# ==================================================
# DATA LOADING FUNCTIONS
# ==================================================

def get_project_file_path(path: str) -> str:
    """
    Convert a file path into a full path.
    """
    if os.path.isabs(str(path)):
        full_path = str(path)
    else:
        full_path = os.path.join(BASE_DIR, str(path))

    return full_path


def find_existing_column(df: pd.DataFrame, names: list[str]) -> str:
    """
    Find the first column name that exists in a DataFrame.
    """
    clean_columns = {}

    for column in df.columns:
        clean_name = clean_text(column)
        clean_columns[clean_name] = column

    for name in names:
        if name in df.columns:
            return name

        clean_name = clean_text(name)
        if clean_name in clean_columns:
            return clean_columns[clean_name]

    available_names = []
    for column in df.columns:
        clean_name = clean_text(column)
        available_names.append(clean_name)

    raise KeyError(
        "Could not find any of these columns: "
        f"{names}. Available columns: {available_names}"
    )


def find_optional_column(df: pd.DataFrame, names: list[str]) -> str | None:
    """
    Find an optional column. Return None if it does not exist.
    """
    for name in names:
        if name in df.columns:
            return name

    return None


def load_and_prepare_projects(dataset_path: str = DATASET_FILE_PATH) -> pd.DataFrame:
    """
    Load previous graduation projects from Excel.
    """
    dataset_file = get_project_file_path(dataset_path)
    old_projects = pd.read_excel(dataset_file)

    name_column = find_existing_column(
        old_projects,
        PROJECT_NAME_CANDIDATES,
    )
    desc_column = find_existing_column(
        old_projects,
        DESCRIPTION_CANDIDATES,
    )

    projects = old_projects[[name_column, desc_column]].copy()
    projects.columns = [
        PROJECT_NAME_COLUMN,
        DESCRIPTION_COLUMN,
    ]

    projects[PROJECT_NAME_COLUMN] = (
        projects[PROJECT_NAME_COLUMN].fillna("").map(clean_text)
    )
    projects[DESCRIPTION_COLUMN] = (
        projects[DESCRIPTION_COLUMN].fillna("").map(clean_text)
    )

    projects[INPUT_TEXT_COLUMN] = build_input_text_column(projects)

    has_text = projects[INPUT_TEXT_COLUMN].astype(bool)
    projects = projects[has_text].reset_index(drop=True)

    return projects


def get_json_rows(json_data):
    """
    Convert accepted JSON shapes into a list of project rows.
    """
    if isinstance(json_data, dict):
        has_projects = PROJECTS_WRAPPER_KEY in json_data
        if has_projects and isinstance(json_data[PROJECTS_WRAPPER_KEY], list):
            rows = json_data[PROJECTS_WRAPPER_KEY]
        else:
            rows = [json_data]
    elif isinstance(json_data, list):
        rows = json_data
    else:
        raise ValueError(
            "JSON input must be a project object, a list of projects, "
            "or a {'projects': [...]} wrapper."
        )

    return rows


def load_input_projects_from_json(json_path: str) -> pd.DataFrame:
    """
    Load the new projects from JSON and prepare them for comparison.
    """
    json_file = get_project_file_path(json_path)

    with open(json_file, "r", encoding=JSON_ENCODING) as file:
        json_data = json.load(file)

    rows = get_json_rows(json_data)
    new_projects = pd.DataFrame(rows)

    if new_projects.empty:
        raise ValueError("JSON input file does not contain any projects.")

    name_column = find_existing_column(
        new_projects,
        INPUT_PROJECT_NAME_CANDIDATES,
    )
    desc_column = find_existing_column(
        new_projects,
        INPUT_DESCRIPTION_CANDIDATES,
    )

    input_projects_df = new_projects[[name_column, desc_column]].copy()
    input_projects_df.columns = [
        PROJECT_NAME_COLUMN,
        DESCRIPTION_COLUMN,
    ]

    expected_column = find_optional_column(
        new_projects,
        EXPECTED_PROJECT_CANDIDATES,
    )

    if expected_column is not None:
        input_projects_df[EXPECTED_PROJECT_COLUMN] = new_projects[expected_column]

    input_projects_df[PROJECT_NAME_COLUMN] = (
        input_projects_df[PROJECT_NAME_COLUMN].fillna("").map(clean_text)
    )
    input_projects_df[DESCRIPTION_COLUMN] = (
        input_projects_df[DESCRIPTION_COLUMN].fillna("").map(clean_text)
    )

    if EXPECTED_PROJECT_COLUMN in input_projects_df.columns:
        input_projects_df[EXPECTED_PROJECT_COLUMN] = (
            input_projects_df[EXPECTED_PROJECT_COLUMN].fillna("").map(clean_text)
        )

    input_projects_df[INPUT_TEXT_COLUMN] = build_input_text_column(input_projects_df)

    has_text = input_projects_df[INPUT_TEXT_COLUMN].astype(bool)
    input_projects_df = input_projects_df[has_text].reset_index(drop=True)

    if input_projects_df.empty:
        raise ValueError("All input projects are empty after cleaning.")

    return input_projects_df


# ==================================================
# EMBEDDING MODEL
# ==================================================

class EmbeddingModel:
    """
    Load the SentenceTransformer model and use it to create embeddings.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.model = self.load_model(model_name)

    def load_model(self, model_name: str):
        """
        Try to load the model from the computer first.
        If it is not found, try the normal loading method.
        """
        try:
            model = self._load_model(model_name, local_files_only=True)
            return model
        except Exception:
            pass

        try:
            model = self._load_model(model_name)
            return model
        except Exception as error:
            raise RuntimeError(
                "Could not load the SBERT model. "
                "If this is your first run, connect to the internet once so "
                f"'{model_name}' can be downloaded, then run the script again."
            ) from error

    def _load_model(self, model_name: str, local_files_only: bool = False):
        """
        Load the model while hiding loading messages.
        """
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        with open(os.devnull, "w", encoding=JSON_ENCODING) as hidden_output:
            try:
                sys.stdout = hidden_output
                sys.stderr = hidden_output

                model = SentenceTransformer(
                    model_name,
                    local_files_only=local_files_only,
                )
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        return model

    def encode_texts(self, texts: list[str]):
        """
        Convert many text values into embeddings.
        """
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings

    def encode_single(self, text: str):
        """
        Convert one text value into one embedding.
        """
        embeddings = self.encode_texts([text])
        embedding = embeddings[0]

        return embedding


# ==================================================
# SIMILARITY SEARCH
# ==================================================

def rank_similar_projects(
    text: str,
    projects: pd.DataFrame,
    project_embeddings,
    model: EmbeddingModel,
    threshold: float = SIMILARITY_THRESHOLD,
    top_results: int = TOP_RESULTS,
) -> list[dict]:
    """
    Compare one new project against all previous projects.
    """
    new_embedding = model.encode_single(text)

    scores = cosine_similarity(
        [new_embedding],
        project_embeddings,
    )[0]

    scored_projects = projects.copy()
    scored_projects[SCORE_COLUMN] = scores

    scored_projects = scored_projects.sort_values(
        SCORE_COLUMN,
        ascending=False,
    ).reset_index(drop=True)

    good_matches = scored_projects[scored_projects[SCORE_COLUMN] > threshold]
    best_matches = good_matches.head(top_results)

    if best_matches.empty:
        best_matches = scored_projects.head(1)

    matches = []

    for index, row in best_matches.iterrows():
        score = round(float(row[SCORE_COLUMN]), SCORE_DECIMAL_PLACES)

        match = {
            OUTPUT_PROJECT_KEY: row[PROJECT_NAME_COLUMN],
            OUTPUT_SCORE_KEY: score,
        }

        matches.append(match)

    return matches


class SimilaritySystem:
    """
    Store the project database and search for similar projects.
    """

    def __init__(
        self,
        projects: pd.DataFrame,
        model: EmbeddingModel,
        threshold: float = SIMILARITY_THRESHOLD,
        top_results: int = TOP_RESULTS,
    ):
        self.projects = projects.reset_index(drop=True)
        self.model = model
        self.threshold = threshold
        self.top_results = top_results

        texts = self.projects[INPUT_TEXT_COLUMN].tolist()
        self.project_embeddings = self.model.encode_texts(texts)

    def find_similar_projects(self, input_text: str) -> dict:
        """
        Find the most similar previous projects for one input text.
        """
        matches = rank_similar_projects(
            text=input_text,
            projects=self.projects,
            project_embeddings=self.project_embeddings,
            model=self.model,
            threshold=self.threshold,
            top_results=self.top_results,
        )

        result = {
            OUTPUT_INPUT_TEXT_KEY: input_text,
            OUTPUT_SIMILAR_PROJECTS_KEY: matches,
        }

        return result


def search_similar_projects(
    input_text: str,
    projects: pd.DataFrame,
    model: EmbeddingModel,
    threshold: float = SIMILARITY_THRESHOLD,
    top_results: int = TOP_RESULTS,
) -> dict:
    """
    Helper function for searching with one project only.
    """
    similarity_system = SimilaritySystem(
        projects=projects,
        model=model,
        threshold=threshold,
        top_results=top_results,
    )

    result = similarity_system.find_similar_projects(input_text)

    return result


# ==================================================
# JSON OUTPUT
# ==================================================

def process_input_projects(
    input_projects_df: pd.DataFrame,
    similarity_system: SimilaritySystem,
) -> dict:
    """
    Compare every input project against the old projects database.
    """
    results = {}

    for index, row in input_projects_df.iterrows():
        search_result = similarity_system.find_similar_projects(row[INPUT_TEXT_COLUMN])

        project_result = {
            OUTPUT_INPUT_TEXT_KEY: row[INPUT_TEXT_COLUMN],
            OUTPUT_SIMILAR_PROJECTS_KEY: search_result[
                OUTPUT_SIMILAR_PROJECTS_KEY
            ],
        }

        has_expected = EXPECTED_PROJECT_COLUMN in input_projects_df.columns
        if has_expected and row[EXPECTED_PROJECT_COLUMN]:
            project_result[OUTPUT_EXPECTED_PROJECT_KEY] = row[EXPECTED_PROJECT_COLUMN]

        key = f"{OUTPUT_INPUT_PROJECT_PREFIX}{index + 1}"
        results[key] = project_result

    return results


def results_to_json(results: dict) -> str:
    """
    Convert the results dictionary into formatted JSON text.
    """
    json_text = json.dumps(
        results,
        indent=JSON_INDENT,
        ensure_ascii=JSON_ENSURE_ASCII,
    )

    return json_text


def save_results_to_json(
    results: dict,
    output_path: str = OUTPUT_JSON_FILE_PATH,
) -> None:
    """
    Save the final results to a JSON file.
    """
    output_file = get_project_file_path(output_path)

    with open(output_file, "w", encoding=JSON_ENCODING) as file:
        json.dump(
            results,
            file,
            indent=JSON_INDENT,
            ensure_ascii=JSON_ENSURE_ASCII,
        )


# ==================================================
# MAIN PROGRAM
# ==================================================

def run_similarity_pipeline(
    input_json_path: str,
    dataset_path: str = DATASET_FILE_PATH,
    model_name: str = MODEL_NAME,
    threshold: float = SIMILARITY_THRESHOLD,
    top_results: int = TOP_RESULTS,
) -> dict:
    """
    Run the complete similarity system.
    """
    projects = load_and_prepare_projects(dataset_path)
    input_projects_df = load_input_projects_from_json(input_json_path)
    model = EmbeddingModel(model_name=model_name)

    similarity_system = SimilaritySystem(
        projects=projects,
        model=model,
        threshold=threshold,
        top_results=top_results,
    )

    results = process_input_projects(
        input_projects_df=input_projects_df,
        similarity_system=similarity_system,
    )

    return results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = INPUT_JSON_FILE_PATH

    results = run_similarity_pipeline(input_json_path=input_file)

    save_results_to_json(results)

    print(results_to_json(results))
