import os
import json
from decimal import Decimal

SMM_FOLDER = "SMM"  # Default folder name for SMM services

def getFoldersAndServices(path=""):
    """Detect subfolders and services inside the SMM folder."""
    full_path = os.path.join(SMM_FOLDER, path)
    folders = []
    services = []

    if not os.path.exists(full_path):
        return [], []

    try:
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isdir(item_path):
                folders.append(item)
            elif item.endswith(".json"):
                service_name = os.path.splitext(item)[0]
                services.append(service_name)
    except Exception as e:
        print(f"Error reading folder {full_path}: {e}")
        return [], []

    return folders, services

def getServiceDetailsByName(service_name, folder_path=""):
    """Return details from a specific service JSON file."""
    file_path = os.path.join(SMM_FOLDER, folder_path, f"{service_name}.json") if folder_path else os.path.join(SMM_FOLDER, f"{service_name}.json")

    if not os.path.exists(file_path):
        print(f"Service file not found: {file_path}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return {
                "service_name": data.get("service_name", service_name),
                "price_per_k": Decimal(str(data.get("price_per_k", "0.00"))),
                "min_order": Decimal(str(data.get("min_order", "1"))),
                "max_order": Decimal(str(data.get("max_order", "1000"))),
                "description": data.get("description", "No description available."),
                "service_id": data.get("service_id", "N/A"),
                "service_api": data.get("service_api", "https://SMMGenie.com/api/v2"),
                "service_key": data.get("service_key", "98c6f5ba5f4a4b7a6bf26a7def1cfa7c")
            }
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON file {file_path}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error reading {file_path}: {e}")
        return None
