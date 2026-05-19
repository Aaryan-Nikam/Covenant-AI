"""
Data parsers for external PII/PHI benchmark datasets.

Responsible for downloading, caching, and normalizing disparate datasets
into a unified `BenchmarkCase` pipeline.
"""

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("ironpass.benchmark.parsers")


@dataclass
class BenchmarkEntity:
    data_type: str
    value: str


@dataclass
class BenchmarkCase:
    id: str
    dataset: str
    input: str
    expected_entities: list[BenchmarkEntity]


class DatasetParser:
    """Base class for dataset parsers."""
    
    def name(self) -> str:
        raise NotImplementedError

    def load(self, limit: int = None) -> list[BenchmarkCase]:
        raise NotImplementedError


class KagglePIIParser(DatasetParser):
    """
    Parses the Kaggle 'pii-detection-removal-from-educational-data' dataset.
    This dataset tests GDPR and SOC2 compliance (names, emails, usernames, IDs, phones).
    
    Warning: Requires Kaggle authentication (~/.kaggle/kaggle.json) and accepting
    the competition rules on Kaggle's website.
    """

    # Maps Kaggle competition labels to Ironpass data_types
    LABEL_MAP = {
        "NAME_STUDENT": "person_name",
        "EMAIL": "email",
        "USERNAME": "api_key",       # We map usernames loosely to api_keys/credentials
        "ID_NUM": "passport",        # Generic ID mapped to passport or ssn (requires custom ruleset if needed)
        "PHONE_NUM": "phone_number",
        "URL_PERSONAL": "url",       # Not currently in core active rulesets, but useful for testing
        "STREET_ADDRESS": "address", # Not currently strictly typed in our core rulesets
    }

    def name(self) -> str:
        return "kaggle_pii"

    def load(self, limit: int = None) -> list[BenchmarkCase]:
        try:
            import kagglehub
        except ImportError:
            logger.error("kagglehub not installed. Run: pip install kagglehub")
            return []

        logger.info("Checking Kaggle credential cache and downloading competition data...")
        try:
            # Downloads to local cache automatically
            path = kagglehub.competition_download("pii-detection-removal-from-educational-data")
        except Exception as e:
            logger.error(
                f"Failed to download from Kaggle: {e}. "
                "Ensure you have accepted the competition rules and have ~/.kaggle/kaggle.json"
            )
            return []

        train_path = os.path.join(path, "train.json")
        if not os.path.exists(train_path):
            logger.error(f"train.json not found in downloaded data: {path}")
            return []

        with open(train_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cases = []
        # Process up to `limit` records
        for i, item in enumerate(data):
            if limit and i >= limit:
                break

            doc_id = str(item["document"])
            tokens = item["tokens"]
            labels = item["labels"]
            trailing_whitespace = item["trailing_whitespace"]

            # Reconstruct full text and extract entities
            current_text = ""
            entities: list[BenchmarkEntity] = []
            
            # Simple BIO parser to extract literal string values
            current_entity_type = None
            current_entity_value = ""

            for token, label, ws in zip(tokens, labels, trailing_whitespace):
                start_char = len(current_text)
                current_text += token
                if ws:
                    current_text += " "
                
                # BIO tag logic
                if label == "O":
                    if current_entity_type:
                        # Close previous entity
                        entities.append(
                            BenchmarkEntity(
                                data_type=self.LABEL_MAP.get(current_entity_type, current_entity_type),
                                value=current_entity_value.strip()
                            )
                        )
                        current_entity_type = None
                        current_entity_value = ""
                elif label.startswith("B-"):
                    if current_entity_type:
                        # Close previous entity
                        entities.append(
                            BenchmarkEntity(
                                data_type=self.LABEL_MAP.get(current_entity_type, current_entity_type),
                                value=current_entity_value.strip()
                            )
                        )
                    current_entity_type = label[2:]
                    current_entity_value = token
                elif label.startswith("I-"):
                    if current_entity_type == label[2:]:
                        if ws:
                            current_entity_value += " " + token
                        else:
                            current_entity_value += token

            if current_entity_type:
                entities.append(
                    BenchmarkEntity(
                        data_type=self.LABEL_MAP.get(current_entity_type, current_entity_type),
                        value=current_entity_value.strip()
                    )
                )

            # Only retain entities that Ironpass natively supports in core rulesets
            supported_entities = [e for e in entities if e.data_type in ["person_name", "email", "phone_number"]]

            cases.append(
                BenchmarkCase(
                    id=f"kaggle_{doc_id}",
                    dataset=self.name(),
                    input=current_text,
                    expected_entities=supported_entities,
                )
            )

        return cases


class HuggingFacePIIParser(DatasetParser):
    """
    Parses 'ai4privacy/pii-masking-200k' dataset from Hugging Face.
    Provides massive scale multi-lingual testing.
    """

    # We map common ai4privacy labels to our internal names
    LABEL_MAP = {
        "CREDITCARD": "credit_card",
        "EMAIL": "email",
        "IBAN": "bank_account",
        "PHONEIMEI": "phone_number",
        "SSN": "ssn",
        "PASSPORT": "passport",
        "FIRSTNAME": "person_name",
        "LASTNAME": "person_name",
        "MIDDLENAME": "person_name",
        "IP": "ip_address",
        "DOB": "date_of_birth",
        "PASSWORD": "password",
    }

    def name(self) -> str:
        return "huggingface_pii"

    def load(self, limit: int = None) -> list[BenchmarkCase]:
        try:
            from datasets import load_dataset
        except ImportError:
            logger.error("datasets not installed. Run: pip install datasets")
            return []

        logger.info("Initializing HuggingFace streaming dataset ai4privacy/pii-masking-200k...")
        try:
            # En-only split for accurate benchmarking without multi-lingual noise initially
            ds = load_dataset("ai4privacy/pii-masking-200k", split="train", streaming=True)
            
            # The dataset has many languages but 'language' feature isn't directly filterable on stream
            # We'll filter inline
        except Exception as e:
            logger.error(f"Failed to load dataset from HuggingFace: {e}")
            return []

        cases = []
        count = 0
        
        for item in ds:
            if limit and count >= limit:
                break
                
            if item.get("language") != "en":
                continue
                
            count += 1
            input_text = item["source_text"]
            
            # privacy_mask is a list of dicts: {'value': ..., 'label': ...}
            raw_entities = item.get("privacy_mask", [])
            
            entities = []
            for ent in raw_entities:
                label = ent["label"]
                mapped_type = self.LABEL_MAP.get(label)
                if mapped_type:
                    entities.append(
                        BenchmarkEntity(
                            data_type=mapped_type,
                            value=ent["value"]
                        )
                    )
            
            cases.append(
                BenchmarkCase(
                    id=f"hf_{item['id']}",
                    dataset=self.name(),
                    input=input_text,
                    expected_entities=entities,
                )
            )

        return cases
